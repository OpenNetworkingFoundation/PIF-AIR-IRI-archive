#!/usr/bin/env python
# @file
# @brief Class for a table entry instance

import os
import sys

from air.air_common import *

class TableEntryBase(object):
    """
    @brief Base table entry class
    """
    def __init__(self, action_ref, action_params):
        """
        @param action_ref The name of the action to execute
        @param action_params Map from parameter name to value

        The keys for the action_params match must match those for
        the action referenced
        """
        self.action_ref = action_ref
        self.action_params = action_params

class TableEntryDefault(TableEntryBase):
    """
    Entry object for a default match. Same as TableEntryBase
    """
    pass

class TableEntryExact(TableEntryBase):
    """
    @brief Match entry for exact matching
    """
    def __init__(self, match_values, action_ref, action_params):
        """
        @param match_values A map from match fields to values
        @param action_ref The name of the action to execute
        @param action_params Map from parameter name to value
        """
        TableEntryBase.__init__(self, action_ref, action_params)
        self.match_values = match_values

    def check_match(self, parsed_packet):
        """
        @brief Check if packet matches this entry
        @return (action_name, action_param_map) if match; None otherwise
        """
        for field_name, value in self.match_values.items():
            p_value = parsed_packet.get_field(field_name)
            if p_value is None or p_value != value:
                return None
        return (self.action_ref, self.action_params)

class TableEntryTernary(TableEntryBase):
    """
    @brief General (ternary) match table

    Note that an entry here supports exact match as well; if a mask
    is not specified for a field, then the match is exact.
    """
    def __init__(self, match_values, match_masks, action_ref, action_params,
                 priority):
        """
        @param match_values A map from match fields to values
        @param match_masks A map from match fields to masks for comparing
        @param action_ref The name of the action to execute
        @param action_params Map from parameter name to value
        @param priority The priority of the entry

        Higher numbers are higher priority
        """
        air_assert(match_masks is None or isinstance(match_masks, dict),
                   "Bad mask parameter to table_entry initializer")
        TableEntryBase.__init__(self, action_ref, action_params)
        self.match_masks = match_masks
        self.match_values = match_values
        self.priority = priority


    def check_match(self, parsed_packet):
        """
        @brief Check if packet matches this entry
        @return (action_name, action_param_map) if match; None otherwise
        """
        for field_name, value in self.match_values.items():
            mask = deref_or_none(self.match_masks, field_name)
            p_value = parsed_packet.get_field(field_name)
            if p_value is None:
                return None
            if mask is not None:
                if p_value & mask != value & mask:
                    return None
            else:
                if p_value != value:
                    return None

        return (self.action_ref, self.action_params)

def description_to_entry(entry_desc):
    """
    @brief Generate a TableEntry object from a table entry description
    @param entry_desc The dictionary describing the entry

    If no match present, generate a default entry.

    Otherwise, generate a TableEntryTernary object as it works for all types

        match_values : # Match criteria
          <header-or-field-ref> : <value>
          ...
        match_masks : # For ternary matches
          <header-or-field-ref> : <mask-value>
          ...
        priority : <value> # For ternary matches
        action : <action_name>
        action_params :
          <param-name> : <value>
          ...

    """
    masks = deref_or_none(entry_desc, "match_masks")
    params = deref_or_none(entry_desc, "action_params")
    priority = deref_or_zero(entry_desc, "priority")
    if "match_values" in entry_desc:
        entry = TableEntryTernary(entry_desc["match_values"], masks,
                                  entry_desc["action"], params, priority)
    else:
        # Default entry
        entry = TableEntryDefault(entry_desc["action"],
                                  entry_desc["action_params"])
    return entry

if __name__ == "__main__":

    def transmit_handler(out_port, packet):
        logging.debug("Got call to send packet to %d" % out_port)

    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    from instance import IriInstance
    from parsed_packet import ParsedPacket

    # Set up the unit test IRI instance
    local_dir = os.path.dirname(os.path.abspath(__file__))
    iri = IriInstance("instance", local_dir + "/../unit_test.yml",
                      transmit_handler)

    exact_entry = TableEntryExact({"ethernet.ethertype" : 0x07},
                                  "some_action", {})
    ternary_entry = TableEntryTernary({"ethernet.ethertype" : 0x07},
                                      {"ethernet.ethertype" : 0x07},
                                      "some_action", {}, 17)
    default_entry = TableEntryDefault("some_action", {})

    byte_buf = bytearray(range(100))
    ppkt = ParsedPacket(byte_buf, {})

    air_assert(exact_entry.check_match(ppkt) is None, "Exact non-match")
    air_assert(ternary_entry.check_match(ppkt) is None, "Ternary non-match")

    ppkt.parse_header("ethernet", iri.air_object_map["ethernet"])
    ppkt.set_field("ethernet.ethertype", 0x17)

    match_val = ternary_entry.check_match(ppkt)
    air_assert(match_val is not None, "Ternary should match post set")

    match_val = exact_entry.check_match(ppkt)
    air_assert(match_val is None, "Exact should not match post set")

    
