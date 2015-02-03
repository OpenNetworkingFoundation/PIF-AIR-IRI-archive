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

class ParserStateTransition(object):
    """
    @brief Holds and manages the transition information for a parser state

    @param value_map Map from specific values to next parser states
    @param all_value_sets Map from name to reference for all value sets
    @param in_value_sets Map from value_set name to next state for
    select values in the given value set
    @param not_in_value_sets Map from value_set name to next state for
    select values not in the given value set

    The primary interface is the function next_state: Given a select_value
    for a packet, and assuming the state machine is in "this" state,
    return the next parser state
    """

    def __init__(self, src_state_name, all_edges, all_value_sets):
        """
        @brief Create an parse state for the given source state
        @param src_state_name Name of this state
        @param all_edges The dot graph object for all edges in the parser
        @param all_value_sets The map of references for all value sets

        Iterates thru the parser edges and processes those that have
        "this" (src_state_name) as the source.
        """
        self.name = src_state_name
        self.default = None
        self.value_map = {}
        self.all_value_sets = all_value_sets
        self.in_value_sets = {}
        self.not_in_value_sets = {}

        for edge in all_edges:
            if src_state_name == edge.get_source():
                self._add_edge(edge)

    def next_state(self, select_value):
        """
        @brief Given the select value, return the next state

        This implements the priority of the state transition
        decision. Specific values are used first, then value sets
        (in no particular order) then negative value sets (in
        no particular order). If none of those match, then a
        default state is returned (which may be None).
        """

        if select_value is None:
            return self.default

        # Is specific value specified in 
        if select_value in self.value_map.keys():
            return self.value_map[select_value]

        # Not a specific value, check value sets and negations of same
        for value_set, next_state in self.in_value_sets.items():
            if select_value in value_set:
                return next_state

        for value_set, next_state in self.not_in_value_sets.items():
            if select_value not in value_set:
                return next_state

        # Check for default value
        return self.default

    def _add_edge(self, edge):
        """
        Create a new edge (transition) and fill it in with next state
        and condition
        """

        # @TODO: Make the "condition" for the edge more generic
        attrs = edge.get_attributes()
        next_state = edge.get_destination()

        # First, is an explicit value given for the transition?
        if "value" in attrs:
            val_str = attrs["value"].strip("'\"")
            value = int(val_str, 0)
            self.value_map[value] = next_state

            logging.debug("Parser transition: %s to %s, equal to 0x%x (%d)" %
                          (self.name, next_state, value, value))
            return
            
        # Is a "in_value_set" given for the transition?
        if "in_value_set" in attrs:
            set_name = attrs["in_value_set"].strip("'\"")
            if not set_name in self.all_value_sets.keys():
                raise IriReferenceError("Parser: unknown value set %s" 
                                            % set_name)
            # assert set_name not in self.in_value_sets
            self.in_value_sets[set_name] = next_state
            logging.debug("Parser transition: %s to %s, value in set %s" %
                          (self.name, next_state, set_name))
            return

        # Is a "not_in_value_set" given for the transition?
        if "not_in_value_set" in attrs:
            set_name = attrs["not_in_value_set"].strip("'\"")
            if not set_name in self.all_value_sets.keys():
                raise IriReferenceError("Parser: unknown value set %s" 
                                            % set_name)
            # assert set_name not in self.not_in_value_sets
            self.not_in_value_sets[set_name] = next_state
            logging.debug("Parser transition: %s to %s, value not in set %s" %
                          (self.name, next_state, set_name))
            return

        else: # Default state
            logging.debug("Parser transition: %s to %s, default" %
                          (self.name, next_state))
            self.default = next_state
            
class Parser(Processor):
    """
    @brief A parser object
    @param name The name of the parser
    @param air_parser_attrs The attributes from the AIR description
    @param parser_states The map for all parser states
    @param headers The map for all header instances
    @param value_sets The map for all value sets

    @todo Support explicit error indications
    @todo Should we just pass the IRI instance object in for init?
    """
    def __init__(self, name, air_parser_attrs, all_parser_states,
                 headers, all_value_sets):
        logging.info("Creating parser " + name)

        self.name = name
        self.parser_states = all_parser_states
        self.headers = headers
        self.all_value_sets = all_value_sets
        self.air_parser_attrs = air_parser_attrs
        self.implementation = air_parser_attrs["implementation"]

        self.graph = pydot.graph_from_dot_data(self.implementation)
        self.graph.set_name("parser_" + name)

        self.transitions = {} # Map from parse state name to transition map
        self.first_state_name = air_parser_attrs["start_state"]
        self.default_return_value = "drop" 

        # Some of this should move to the validator
        logging.debug("Processing parse graph for " + self.graph.get_name())
        all_edges = self.graph.get_edge_list()
        for state_name in all_parser_states:
            self.transitions[state_name] = ParserStateTransition(
                state_name, all_edges, all_value_sets)
                
    def process(self, parsed_packet, state=None):
        """
        @brief Apply this parser to the given packet
        @param parsed_packet The packet to parse, a parsed packet instance
        @param state The parse state to start at

        The parsed packet object tracks the "current offest", etc.

        @TODO Support explicit transitions to control flows.
        """

        air_check(isinstance(parsed_packet, ParsedPacket), IriParamError)

        drop_packet = False # @todo Not implemented yet

        logging.debug("Parser: pkt id %d" % parsed_packet.id)
        state_name = self.first_state_name
        while state_name:
            logging.debug("Parser: In state %s" % state_name)
            state_attrs = self.parser_states[state_name]
            transitions = self.transitions[state_name]
            next_state = None
            select_value = None

            if "extracts" in state_attrs.keys():
                for hdr_name in state_attrs["extracts"]:
                    logging.debug("Parser: extract %s" % hdr_name)
                    parsed_packet.parse_header(hdr_name, 
                                               self.headers[hdr_name])
            if "select_value" in state_attrs.keys():
                # @todo Use eval in combination with field value subs
                fld_ref = state_attrs["select_value"][0]
                select_value = parsed_packet.get_field(fld_ref)

            next_state = transitions.next_state(select_value)
            logging.debug("Parser trans from %s to %s on value %s" %
                          (state_name, str(next_state), str(select_value)))
            state_name = next_state

        if not drop_packet and self.next_processor is not None:
            logging.debug("Parser %s, pkt %d: Next processor %s" %
                          (self.name, parsed_packet.id,
                           self.next_processor.name))
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

    # Test cases for unit test input
    byte_buf = bytearray(range(100))
    ppkt = ParsedPacket(byte_buf, {})
    parser.process(ppkt)

    if "ethernet" in iri.header.keys():
        air_assert(ppkt.header_length == 14, "Did not parser ether hdr")
        air_assert("ethernet" in ppkt.header_map.keys(),
                   "Did not parser ether hdr")
        air_assert(ppkt.get_field("ethernet"),
                   "Failed ethernet header valid check")
        air_assert(not ppkt.get_field("foo"),
                   "Failed negative foo header valid check")

    byte_buf[12] = 0x81
    byte_buf[13] = 0
    ppkt = ParsedPacket(byte_buf, {})
    parser.process(ppkt)
    if "ethernet" in iri.header.keys():
        air_assert("ethernet" in ppkt.header_map.keys(),
                   "Did not parser ether hdr")
        air_assert(ppkt.get_field("ethernet"),
                   "Failed ethernet header valid check")
        if "vlan_tag_outer" in iri.header.keys():
            air_assert(ppkt.header_length == 18, "Did not parser ether+vlan hdr")
            air_assert("vlan_tag_outer" in ppkt.header_map.keys(), 
                       "Did not parser vlan hdr")

