#!/usr/bin/env python
#
# @file
# @brief Class for a pipeline instance
#
# A pipeline is a collection of tables and a control flow graph.
# A pipeline is initialized with the control flow graph and the IRI 
# maps for tables and actions
#
# TBD: MULTIPLE REFERENCES TO A TABLE ACROSS DIFF PIPELINES
# TBD: How are default ops out of a table managed: queue? egress?...

import os
import sys
import logging
import pydot
import table

from air.air_common import *

from processor import Processor
from iri_exception import *

class Pipeline(Processor):
    """
    @brief Class for a pipeline object
    @param name The name of the control flow AIR object
    @param air_control_flow_attrs The attributes of the control_flow AIR object
    for the pipeline
    @param table_map The map of IRI table objects
    @param action_map The map of IRI action objects
    @param first_table_name The first table in the pipeline

    Manages a group of tables and the control flow between them

    Attributes:  
    * first_table_name Start with this table by default
    """
    def __init__(self, name, air_control_flow_attrs, table_map, action_map):
        self.name = name
        self.air_control_flow_attrs = air_control_flow_attrs
        self.table_map = table_map
        self.action_map = action_map
        self.implementation = air_control_flow_attrs["implementation"]

        self.graph = pydot.graph_from_dot_data(self.implementation)
        self.graph.set_name("control_flow_" + name)

        self.transitions = {} # Map from table name to transition map
        self.first_table_name = None

        # Some of this should move to the validator
        logging.debug("Processing control graph for " + self.graph.get_name())
        for edge in self.graph.get_edge_list():
            src_table = edge.get_source()
            dst_table = edge.get_destination()
            logging.debug("Pipeline src: %s. dst: %s. attrs: %s" %
                          (str(src_table), str(dst_table),
                           str(edge.get_attributes())))

            # Add source and dest tables to transitions if not there.
            if not src_table in self.transitions.keys():
                air_check(src_table in self.table_map.keys(), IriReferenceError)
                self.transitions[src_table] = {}

            # Is it a queue or egress transition? If not, add as table
            if dst_table != "exit_control_flow":
                if not dst_table in self.transitions.keys():
                    self.transitions[dst_table] = {}

            attrs = edge.get_attributes()
            if "action" in attrs:
                act_name = attrs["action"]
                self.transitions[src_table][act_name] = dst_table
                logging.debug("%s to %s on %s" %
                              (src_table, dst_table, attrs["action"]))

        # Find the set of tables that have no incoming edges
        result = self.transitions.keys()
        for src_table in self.transitions.keys():
            for _, dst_table in self.transitions[src_table].items():
                if dst_table in result:
                    result.remove(dst_table)

        # Currently only support a single "first" table
        air_assert(len(result) == 1, "Control flow has %d entry points; " % 
                   len(result) + "should be 1")
        self.first_table_name = result[0]
        logging.info("First table in control_flow %s is %s" % 
                     (name, self.first_table_name))
        
    def process(self, parsed_packet):
        """
        @brief Pass a packet through this control_flow
        @param parsed_packet A parsed packet instance to be processed
        @returns One of "drop", "queue", or "egress"

        May consider deriving first_table_name from packet metadata
        """
        current_table = self.first_table_name

        logging.debug("Pipeline %s on pkt %d" % (self.name, parsed_packet.id))

        current_table_name = self.first_table_name
        while current_table_name != "exit_control_flow":
            air_assert(current_table_name in self.transitions.keys(),
                       "Table %s is not in control_flow" % current_table_name)
            current_table = self.table_map[current_table_name]
            transitions = self.transitions[current_table_name]

            #
            # Execute a table and get back the hit/miss status and
            # and action (name) taken.
            #
            # Special names include "queue" and "egress" for exiting
            # the control_flow.
            #
            # Precedence for hit/miss/action control flow resolution
            #   "Miss" takes precedence if miss and action are both indicated.
            #   Specific action takes precedence over "hit" indication.
            #   Finally, generic "hit" is checked.
            #

            (hit, action) = current_table.process_packet(parsed_packet)
            # @FIXME Apply action to the packet

            current_table_name = "exit_control_flow"
            if "always" in transitions.keys():
                current_table_name = transitions["always"]

            elif not hit:
                if "miss" in transitions.keys():
                    current_table_name = transitions["miss"]
                elif action and action in transitions.keys():
                    current_table_name = transitions[action]

            else: # Hit
                if action in transitions.keys(): 
                    current_table_name = transitions[action]
                elif "hit" in transitions.keys():
                    current_table_name = transitions["hit"]
                elif "default" in transition.keys():
                    current_table_name = transitions["default"]

        logging.debug("Pipeline %s, pkt %d: calling to %s",
                      self.name, parsed_packet.id, self.next_processor.name)

        self.next_processor.process(parsed_packet)

################################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    def transmit_packet(out_port, packet):
        pass

    from instance import IriInstance
    from parsed_packet import ParsedPacket

    # Create IRI config from unit_test
    local_dir = os.path.dirname(os.path.abspath(__file__))
    iri = IriInstance("instance", local_dir + "/../unit_test.yml",
                      transmit_packet)

    # Instantiate the ingress_flow pipe
    pipe = iri.iri_pipeline["ingress_flow"]

    # Create a packet object
    byte_buf = bytearray(range(100))
    ppkt = ParsedPacket(byte_buf, {})

