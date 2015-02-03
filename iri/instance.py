#!/usr/bin/env python
#
# @file
# @brief The top level IRI configuration object
#
# This holds the Python representation of the YAML top level
# description of the IR instance and provides some basic features
# such as iterators over objects in the instance (by type).
#

import os
import time
import sys
import yaml
import logging

from air.air_instance import AirInstance
from parser import Parser
from air.air_common import *
from pipeline import Pipeline
from parser import Parser
from processor import Processor
from table import Table
from action import Action
from parsed_packet import ParsedPacket
from simple_queue import SimpleQueueManager
import table_entry

def hexify(buf, length):
    return ":".join(["%02x" % c for c in buf])

class IriInstance(AirInstance):
    """
    @brief An Intermediate Representation configuration instance

    @param iri_parser A map from parser name to IRI parser object
    @param iri_action A map from action name to IRI action object
    @param iri_table A map from table name to IRI table object
    @param iri_pipeline A map from control flow name to a pipeline object. 
    This combines control flow with tables and actions
    @param iri_traffic_manager A map from TM name to TM object
    @param disabled Is the switch instance forwarding packets
    @param processors Map from processor name to processor object; these
    include parsers, pipelines and traffic managers.
    @param table_initialization The set of table entries to add during
    initialization 
    

    An IR instance extends the AIR instance and additionally instantiates
    IRI objects with the parameters indicated.

    The IRI instance is also responsible for the layout of the processor
    components (parsers, pipelines and traffic managers). 

    Currently only sequences of processors are supported.

    To support the connection between a processor and "egress" (that is,
    transmitting to a port) an instance also defines a "transmit_processor"
    which is a processor type that connects to the data plane for sending
    packets.

    After the constructor is called with the pointer to the switch
    input and the data plane transmit handler, the process_table_init
    method should be called. Then the enable method can be called.
    """

    def __init__(self, name, input, transmit_handler):
        """
        @brief IriInstance constructor

        @param name The name of the instance
        @param input An object with the YAML description of the IR instance
        @param transmit_handler A function to be called to transmit pkts

        @todo Add support to allow the specification of the AIR instance
        """
        AirInstance.__init__(self)

        self.transmit_handler = transmit_handler
        self.name = name

        self.tm_started = False
        self.disabled = True

        # Add the content to the AIR instance
        self.add_content(input)
        self.port_count = self.air_object_map["layout"]["port_count"]

        # Create the IRI objects: parsers, actinos, tables, pipelines and TMs
        self.iri_value_set = {}
        self.iri_value_map = {}
        self.iri_parser = {}
        self.iri_action = {}
        self.iri_table = {}
        self.iri_pipeline = {}
        self.iri_traffic_manager = {}
        self.processors = {}
        self.transmit_processor = TransmitProcessor(transmit_handler)

        for name, val in self.value_set.items():
            self.iri_value_set[name] = [] # Just use a list

        for name, val in self.value_map.items():
            self.iri_value_map[name] = {} # Just use a dict

        for name, val in self.parser.items():
            self.iri_parser[name] = Parser(name, val, self.parse_state,
                                           self.header, self.value_set)
            self.processors[name] = self.iri_parser[name]
        for name, val in self.action.items():
            self.iri_action[name] = Action(name, val)
        for name, val in self.table.items():
            self.iri_table[name] = Table(name, val, self.iri_action)
        for name, val in self.control_flow.items():
            self.iri_pipeline[name] = Pipeline(name, val, self.iri_table,
                                               self.iri_action)
            self.processors[name] = self.iri_pipeline[name]
        for name, val in self.traffic_manager.items():
            self.iri_traffic_manager[name] = SimpleQueueManager(name, val,
                                                                self.port_count)
            self.processors[name] = self.iri_traffic_manager[name]

        # Plumb the layout
        layout = self.air_object_map["layout"]
        air_assert(layout["format"] == "list", "Unsupported layout: not a list")
        layout_name_list = layout["implementation"]
        air_assert(isinstance(layout_name_list, list), 
                   "Layout implementation is not a list")

        proc_count = len(layout_name_list)
        for idx, processor_name in enumerate(layout_name_list):
            cur_proc = self.processors[processor_name]
            if idx == 0:
                logging.debug("Layout: First processor %s" % cur_proc.name)
                self.first_processor = cur_proc

            if idx < proc_count - 1:
                next_proc = self.processors[layout_name_list[idx + 1]]
                cur_proc.next_processor = next_proc
            else: # Last one connects to transmit processor
                cur_proc.next_processor = self.transmit_processor

            logging.debug("Layout %s to %s" % (cur_proc.name,
                                               cur_proc.next_processor.name))

        # Grab table initialization object if present
        self.table_initialization = {}
        ext_objs = self.external_object_map
        if "table_initialization" in ext_objs.keys():
            self.table_initialization = ext_objs["table_initialization"]

    def process_table_init(self):
        """
        @brief Process any table initialization spec from the IR desc

        The IR specification may provide a set of table initialization
        operations in a "table_initialization" object. This takes the
        form of a sequence of table entry specifications.
        """
        logging.debug("Processing table initialization, %d entries",
                      len(self.table_initialization))

        for init_entry in self.table_initialization:
            for table_name, entry_desc in init_entry.items():
                self.iri_table[table_name].add_entry(
                    table_entry.description_to_entry(entry_desc))

    def enable(self):
        """
        @brief Enable the switch instance

        Start the traffic manager threads and allow packets to enter
        the processor chain
        """
        if not self.tm_started:
            for name, tm in self.iri_traffic_manager.items():
                logging.debug("Starting tm %s" % name)
                tm.start()
            tm_started = True

        logging.debug("Enabling switch %s" % self.name)
        self.disabled = False

    def disable(self):
        """
        @brief Disable the switch instance

        Packets on ingress are discarded while the switch is disabled.

        Traffic manager threads are not stopped.
        """
        logging.debug("Disabling switch %s" % self.name)
        self.disabled = True

    def kill(self):
        """
        """
        if not self.tm_started:
            for name, tm in self.iri_traffic_manager.items():
                logging.debug("Stopping tm %s" % name)
                tm.kill()
                tm.join()
        
    def process_packet(self, in_port, packet):
        """
        @param in_port The ingress port number on which packet arrived
        @param packet A bytearray with the packet data
        """
            
        buf = bytearray(packet)
        for idx in range((len(packet) + 19)/20):
            logging.debug(hexify(buf[20*idx : 20*(idx+1)], 20))

        if self.disabled:
            logging.debug("Switch is disabled; discarding packet")
            return

        parsed_packet = ParsedPacket(buf, self.metadata)
        logging.debug("Processing packet %d from port %d with %s" % 
                      (parsed_packet.id, in_port,
                       self.first_processor.name))
        self.first_processor.process(parsed_packet)

    def dummy_transmit_handler(out_port, packet):
        """
        @brief Transmit handler template for documentation
        @param out_port The port number to which the packet is to be sent
        @param packet A bytearray object holding the packet to transmit
        """
        pass

class TransmitProcessor(Processor):
    """
    @brief Wrapper class to connect processing with transmitting packets
    @param transmit_handler A function that knows how to send a packet to a port
    """
    def __init__(self, transmit_handler):
        self.transmit_handler = transmit_handler
        self.name = "transmit_processor"

    def process(self, parsed_packet):
        """
        @brief Process interface that sends a packet
        @param parsed_packet The packet instance to transmit
        """
        byte_buf = parsed_packet.serialize()
        out_port= parsed_packet.get_field("intrinsic_metadata.egress_port")
        logging.debug("Transmit pkt id %d to %d" % (parsed_packet.id, out_port))
        buf = bytearray(byte_buf)
        for idx in range((len(buf) + 19)/20):
            logging.debug(hexify(buf[20*idx : 20*(idx+1)], 20))

        self.transmit_handler(out_port, byte_buf)

################################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    def transmit_packet(out_port, packet):
        pass

    local_dir = os.path.dirname(os.path.abspath(__file__))
    obj = IriInstance("instance", local_dir + "/../unit_test.yml",
                      transmit_packet)
