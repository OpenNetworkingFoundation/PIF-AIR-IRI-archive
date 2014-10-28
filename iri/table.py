#!/usr/bin/env python
# @file
# @brief Class for a table instance
#
# This is mostly just a container for table entries

import sys
from threading import Condition

from air.air_common import *
from table_entry import TableEntryExact, TableEntryTernary, TableEntryDefault


class Table(object):
    def __init__(self, name, air_table_attrs, action_map):
        """
        @brief Constructor for a table object
        @param name The name of the table to instantiate
        @param air_table_attrs The table attributes from the IRI instance
        @param action_map The map of all action objects for the IRI instance

        Object attributes (internal):
          match_on: Map from field refs to match type
          entries: List of entries in the table (run time added)
        """

        self.name = name
        self.air_table_attrs = air_table_attrs
        self.action_map = action_map

        # The list of table entries
        self.entries = []
        self.default_entry = None # Another table entry

        # Other state for the table
        self.byte_count = 0
        self.packet_count = 0

        # For synchronizing table updates with packet processing
        self.cond_var = Condition()

    def process_packet(self, parsed_packet):
        """
        @brief Process a packet according to the current table and IR state
        @param parsed_packet A parsed packet instance
        @returns A triple (Bool, str, params) where the bool indicates if a
        match was found, str is the name of the action to be applied
        and params are the action parameters from the table entry
        """

        # For now a very simple linear search
        # @todo Support hash lookups for exact matches
        logging.debug("Table %s processing pkt %d" %
                      (self.name, parsed_packet.id))
        hit = False
        action_ref = None
        with self.cond_var:
            for entry in self.entries:
                if entry.check_match(parsed_packet):
                    action_ref = entry.action_ref
                    params = entry.action_params
                    logging.debug("Pkt %d hit" % parsed_packet.id)
                    hit = True
                    self.packet_count += 1
                    self.byte_count += parsed_packet.length()
                    break
            if not hit:
                if self.default_entry:
                    action_ref = self.default_entry.action_ref
                    params = self.default_entry.action_params
                    logging.debug("Pkt %d miss" % parsed_packet.id)

            if action_ref:
                self.action_map[action_ref].eval(parsed_packet, params)

        return (hit, action_ref)

    def add_entry(self, entry):
        """
        @brief Add an entry to the table
        @param entry The entry to add to the table

        If entry is a TableEntryDefault object, then set the default entry
        """
        logging.debug("Adding entry to %s" % self.name)
        # @FIXME: Check entry is proper type for this table
        # @FIXME: Support entry priorities for ternary matching

        if isinstance(entry, TableEntryDefault):
            return self.set_default_entry(entry)

        with self.cond_var:
            self.entries.append(entry)

    def remove_entry(self, entry_ref):
        """
        Remove an entry to the table, by match criteria or entry reference
        """
        logging.debug("Removing entry from %s" % self.name)
        if isinstance(entry_ref, table_entry):
            with self.cond_var:
                self.entries.remove(entry_ref)
        elif isinstance(entry_ref, dict):
            # This is the match criteria used by the entry
            logging.debug("FIXME: table entry remove by match not implemented")
            pass
        else:
            raise IriReferenceError("Unknown entry ref type for entry remove")

    def clear(self, clear_stats=True, clear_default=False):
        """
        Remove all entries from the table
        @param clear_stats If True, set table counters to 0
        @param clear_default If True, clear the default entry too
        """
        logging.debug("Clearing table %s" % self.name)
        with self.cond_var:
            if clear_stats:
                self.packet_count = 0
                self.byte_count = 0
            for entry in self.entries:
                # For now, do nothing
                pass
            self.entries = []
            if clear_default:
                self.default_entry = None

    def hit_stats(self):
        """
        @brief Return table counters
        @returns A pair of integers, byte count and packet count
        """
        return (self.byte_count, self.packet_count)

    def set_default_entry(self, entry):
        air_assert(isinstance(entry, TableEntryDefault))
        with self.cond_var:
            self.default_entry = entry

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)
