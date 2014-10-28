#!/usr/bin/env python
#
# @file
# @brief The class for a Parser object
#
#

import os
import sys
import logging
import pydot

from air.air_common import *
from iri_exception import *
from parsed_packet import ParsedPacket
from processor import Processor

class Parser(Processor):
    """
    @brief A parser object
    @param name The name of the parser
    @param air_parser_attrs The attributes from the AIR description
    @param state_map The map for all parser states
    @param header_map The map for all header instances

    @todo Support explicit error indications
    """
    def __init__(self, name, air_parser_attrs, state_map, header_map):
        logging.info("Creating parser " + name)

        self.name = name
        self.state_map = state_map
        self.header_map = header_map
        self.air_parser_attrs = air_parser_attrs
        self.implementation = air_parser_attrs["implementation"]

        self.graph = pydot.graph_from_dot_data(self.implementation)
        self.graph.set_name("parser_" + name)

        self.transitions = {} # Map from parse state name to transition map
        self.first_state_name = air_parser_attrs["start_state"]
        self.default_return_value = "drop" 

        # Some of this should move to the validator
        logging.debug("Processing parse graph for " + self.graph.get_name())
        for edge in self.graph.get_edge_list():
            src_state = edge.get_source()
            dst_state = edge.get_destination()
            logging.debug("Parser src: %s. dst: %s. attrs: %s" %
                          (str(src_state), str(dst_state),
                           str(edge.get_attributes())))

            # Add source and dest states to transitions if not there.
            if not src_state in self.transitions.keys():
                air_check(src_state in self.state_map.keys(), IriReferenceError)
                self.transitions[src_state] = {}

            # @todo Support e.g. error state transitions
            if not dst_state in self.transitions.keys():
                air_check(dst_state in self.state_map.keys(), IriReferenceError)
                self.transitions[dst_state] = {}

            attrs = edge.get_attributes()
            if "value" in attrs:
                val_str = attrs["value"].strip("'\"")
                value = int(val_str, 0)
                self.transitions[src_state][value] = dst_state
                logging.debug("%s to %s on 0x%x (%d)" %
                              (src_state, dst_state, value, value))

    def process(self, parsed_packet, state=None):
        """
        @brief Apply this parser to the given packet
        @param parsed_packet The packet to parse
        @param state The parse state to start at

        If the packet is a raw packet, create a new parsed packet instance.

        If offset is not 0, the block between 0 and offset will be added
        to the parse list as a byte-string block.
        """

        air_check(isinstance(parsed_packet, ParsedPacket), IriParamError)

        drop_packet = False # @todo Not implemented yet

        logging.debug("Parser: pkt id %d" % parsed_packet.id)
        state_name = self.first_state_name
        while state_name and state_name in self.transitions.keys():
            logging.debug("Parser: state %s" % state_name)
            state_attrs = self.state_map[state_name]

            # @todo try/except blocks here
            if "extracts" in state_attrs.keys():
                for hdr_name in state_attrs["extracts"]:
                    logging.debug("Parser: extract %s" % hdr_name)
                    parsed_packet.parse_header(hdr_name, 
                                               self.header_map[hdr_name])
            if "select_value" in state_attrs.keys():
                # @todo Use eval in combination with field value subs
                fld_ref = state_attrs["select_value"][0]
                select_value = parsed_packet.get_field(fld_ref)
                if select_value in self.transitions[state_name].keys():
                    state_name = self.transitions[state_name][select_value]
                else:
                    break
            else: # Terminal state
                break

        if not drop_packet and self.next_processor is not None:
            logging.debug("Parser %s, pkt %d: Next state %s", self.name,
                          parsed_packet.id, self.next_processor.name)
            self.next_processor.process(parsed_packet)
        else:
            logging.debug("Parser %s: Dropping pkt %d", self.name,
                          parsed_packet.id)

################################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    def transmit_packet(out_port, packet):
        pass

    from instance import IriInstance
    from parsed_packet import ParsedPacket

    # Create IRI config from unit_test
    if len(sys.argv) > 2:
        unit_test_input = sys.argv[2:]
    else:
        local_dir = os.path.dirname(os.path.abspath(__file__))
        unit_test_input = local_dir + "/../unit_test.yml"
    logging.info("Using input file %s" % unit_test_input)
    iri = IriInstance("instance", unit_test_input, transmit_packet)

    parser = iri.iri_parser["parser"]

    byte_buf = bytearray(range(100))
    ppkt = ParsedPacket(byte_buf, {})
    parser.process(ppkt)
    air_assert(ppkt.header_length == 14, "Did not parser ether hdr")
    air_assert("ethernet" in ppkt.header_map.keys(), "Did not parser ether hdr")

    byte_buf[12] = 0x81
    byte_buf[13] = 0
    ppkt = ParsedPacket(byte_buf, {})
    parser.process(ppkt)
    if "ethernet" in iri.header.keys():
        air_assert("ethernet" in ppkt.header_map.keys(),
                   "Did not parser ether hdr")
        if "vlan_tag_outer" in iri.header.keys():
            air_assert(ppkt.header_length == 18, "Did not parser ether+vlan hdr")
            air_assert("vlan_tag_outer" in ppkt.header_map.keys(), 
                       "Did not parser vlan hdr")

