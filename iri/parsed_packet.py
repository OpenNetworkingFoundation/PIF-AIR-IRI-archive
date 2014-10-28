#!/usr/bin/env python
#
# @file
# @brief Class for a parsed packet instance
#

import os
import copy
import sys

from air.air_common import *
from iri_exception import *
from header import HeaderInstance

class ParsedPacket(object):
    """
    @brief Represent a parsed packet instance

    This class represents a parsed packet. It is a critical type
    definition for the IR. The parsed representation consists of:

      * An ordered list of valid headers for the packet
      * For each valid header, the dictionary of field values for the header
      * A dictionary of metadata values associated with the packet
      * The original packet and an offset to the beginning of the payload

    Each parsed packet instance gets a unique integer id.

    A parsed packet may be replicated. The original packet is the "parent"
    of the replicant and the parent ID is kept for debugging purposes.

    A parsed packet is always associated with an original packet (bytearray)
    This is treated as "read-only".

    Individual headers are parsed from the original data buffer by calling 
    the parse_header method. The payload of the packet is the portion that 
    has not been parsed. When the parse_header method is called, values
    are read from the current location of the packet to populate the
    field values for the header. The pointer to the start of the payload
    is updated.

    Headers may be added or removed from the list of valid headers by
    actions. This does not affect the payload, but will affect the length
    of the packet.

    In addition to header types identified by the IR configuration
    description, the header list may include instances of an "opaque block"
    which is a sequence of bytes not parsed further. They will appear
    in the header of the packet when re-serialized for transmission.

    Future enhancement: Support additional parsing of opaque blocks.

    Important interfaces:
      * parse_header(header_name): Add the given header to the list.
      * set_field(field_ref, value): Set the given field if it's valid
      * get_field(field_ref): Return the value of the given field if valid
      * add_header_before/after(header_ref, existing_header): Add new header
        before/after the existing header.

    The list of headers is a ListDict ordered dictionary (see air.common).
    The value is a HeaderInstance object.

    Other instance attributes

      * id: A unique ID (integer) for the packet instance
      * original_packet: The original packet data
      * headers: Ordered map of headers parsed so far
      * header_length: Total length of headers in the packet
      * payload_offset: Pointer to the "rest" of the packet
      * parse_error: None if no error, otherwise an instance of the parse_error

      * TBD next_processor: The next processing element to be applied to pkt

    """
    id_next = 0
    def __init__(self, original_packet, metadata_dict):
        """
        @brief ParsedPacket constructor
        @param original_packet The original packet; read only
        @param metadata_dict The metatdata instances to use when init'ing pkt
        """

        # TODO: Assert original_packet is proper type
        air_check(isinstance(original_packet, bytearray), IriParamError)
        self.original_packet = original_packet

        self.header_map = ListDict() # of HeaderInstance objects
        self.header_length = 0

        # The payload is the unparsed portion of the packet
        self.payload_offset = 0
        self.payload_length = len(original_packet)

        self.id = ParsedPacket.id_next
        ParsedPacket.id_next += 1
        self.parent_id = None

        # Indicates if an error occured when parsing
        self.parse_error = None

        # @TODO Add support for metadata initializers
        self.metadata = {}
        for name, md in metadata_dict.items():
            self.metadata[name] = HeaderInstance(name, md)

        logging.debug("Created packet %d", self.id)

    def parse_header(self, header_name, header_attrs):
        """
        @brief Parse (identify) a header from the packet
        @param header_name The header instance (name) to identify
        @param header_attrs The AIR attributes associated of the header

        The header is taken from the packet payload and offsets
        are updated.
        """
        air_assert(header_attrs["type"] in ["header_stack", "header"],
                   "Parsed packet passed bad header object for parsing")

        # @TODO check for sufficient payload bytes
        if header_attrs["type"] == "header":
            header = HeaderInstance(header_name,
                                    header_attrs,
                                    byte_buffer=self.original_packet,
                                    offset=self.payload_offset)
        else: # Header stack
            # @FIXME
            pass

        self.header_map[header_name] = header
        self.payload_offset += header.length
        self.payload_length -= header.length
        self.header_length += header.length

    def get_field(self, field_ref):
        """
        @brief Get a field from this parsed packet
        @param field_ref Reference to a field of the form hdr_name.fld_name
        """
        try:
            (hdr, fld) = field_ref.split(".")
        except ValueError:
            return None

        if hdr in self.header_map.keys():
            return self.header_map[hdr].get_field(fld)
        if hdr in self.metadata.keys():
            return self.metadata[hdr].get_field(fld)
        logging.debug("Field %s not valid in pkt lookup" % field_ref)
        return None

    def set_field(self, field_ref, field_value):
        """
        @brief Set a field from this parsed packet
        @param field_ref Reference to a field of the form hdr_name.fld_name
        @param field_value A value for the field
        """
        # @FIXME Check for varible width field changing
        logging.debug("Set fld %s to %s" % (field_ref, str(field_value)))
        (hdr, fld) = field_ref.split(".")
        if hdr in self.header_map.keys():
            return self.header_map[hdr].set_field(fld, field_value)
        if hdr in self.metadata.keys():
            return self.metadata[hdr].set_field(fld, field_value)
        logging.debug("Field %s not valid in pkt set_field" % field_ref)
        return None

    def add_header_before(self, header_name, header_attrs, before_header_name):
        """
        @brief Insert the header instance before before_header_name
        @param header_name The name of the header to add
        @param header_attrs The AIR attributes associated of the header
        @param before_header_name The name of the header before which to
        add the new header

        If header_name is already valid for this packet, raise an error
        If before_header_name is not valid for this packet, raise an error
        Can be used to add the first element of a new header stack; use
        header_push to add a new element to an existing stack
        """
        air_check(before_header_name in self.header_map, AIRPacketModException)
        air_check(header_name not in self.header_map, AIRPacketModException)
        header = HeaderInstance(header_name, header_attrs, None)
        self.header_map.insert_before(before_header_name, (header_name, header))
        self.header_length += header.length
        return header.length

    def add_header_after(self, header_name, header_attrs, after_header_name):
        """
        @brief Add the indicated header after after_header_name
        @param header_name The name of the header to add
        @param header_attrs The AIR attributes associated of the header
        @param after_header_name The name of the header after which to
        add the new header

        @returns Length of added header or None if failed.

        If header_name is already valid for this packet, raise an error
        If after_header_name is not valid for this packet, raise an error
        """
        if after_header_name not in self.header_map:
            return None
        if header_name in self.header_map:
            return None
        header = HeaderInstance(header_name, header_attrs, None)
        self.header_map.insert_after(after_header_name, (header_name, header))
        self.header_length += header.length
        return header.length

    def remove_header(self, header_name):
        """
        @brief Remove an instance from the header list
        @param header_name The name of the header to remove

        @returns The length of the header removed of None on error.
        If header_name is a header stack, remove the entire stack.
        """
        # @TODO support header stack

        if header_name not in self.header_map:
            return None

        hdr_len = self.header_map[header_name].length
        self.header_length -= hdr_len
        del self.header_map[header_name]
        return hdr_len

    def parse_skip_byte_block(self, bytes):
        """
        @brief Add a byte block to the parsed fields from start of payload
        @param bytes The number of bytes to consume from the payload

        This consumes bytes from the payload and creates an opaque header.
        """
        air_assert(bytes <= self.payload_length,
                   "Not enough bytes in payload in for parse_skip_byte_block")
        hdr = HeaderInstance("opaque_block", None, 
                             byte_buffer=self.payload,
                             offset=self.payload_offset,
                             length=bytes)
        self.payload_offset += bytes
        self.payload_length -= bytes
        self.header_map[name] = hdr
                    
    def serialize(self):
        """
        Generate a bytearray for the current version of the packet
        """
        pkt = bytearray()
        for hdr_name in self.header_map:
            pkt += self.header_map[hdr_name].serialize()
        payload_start = self.payload_offset
        payload_end = self.payload_offset + self.payload_length
        pkt += self.original_packet[payload_start:payload_end]
        return pkt

    def push_header(self, header_name, back=True):
        """
        @brief Add an element to an existing header stack
        @param header_name The name of the stack to update
        @param back If True, add to the back of the stack; 
        otherwise to the front

        Will raise exception X if the stack is not already present in the
        parsed packet

        Will raise exception X if the stack is already at max length
        """
        pass

    def pop_header(self, header_name, back=True):
        """
        @brief Remove an element from an existing header stack
        @param header_name The name of the stack to update
        @param back If True, remove the last instance (highest index)
        otherwise remove the first instance (lowest index).

        The header stack must already be present in the parsed packet

        If the stack becomes empty, the name is removed from the 
        list of headers in the parsed packet.

        Will raise exception X if the stack is not already present in the
        parsed packet
        """
        pass

    def header_valid(self, header_name):
        """
        @brief Return True if the header is present in the parsed packet
        @param header_name The name of the header instance to check for
        """
        return header_name in self.header_map.keys()

    def header_stack_count(self, header_name):
        """
        @brief Return an integer indicating the number of elements of
        the indicated header stack present in the packet.
        @param header_name The name of the header instance to check for

        Returns 0 if the header stack is not present in the packet instance
        """
        if not header_name in self.header_map.keys():
            return 0
        return self.header_map[header_name].current_count

    def replicate(self):
        """
        Generate a copy of this item suitable for replication processing
        """
        replicant = copy.copy(self)
        # @FIXME Review these
        replicant.headers = copy.deepcopy(self.header_map)
        replicant.metadata = copy.deepcopy(self.metadata)
        self.id = ParsedPacket.id_next
        ParsedPacket.id_next += 1
        replicant.parent_id = self.id

        return replicant

################################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    from instance import IriInstance
    def transmit_packet(out_port, packet):
        pass

    # Create config from unit_test
    local_dir = os.path.dirname(os.path.abspath(__file__))
    iri = IriInstance("instance", local_dir + "/../unit_test.yml",
                      transmit_packet)

    # Create 100 byte packet
    byte_buf = bytearray(range(100))
    ppkt = ParsedPacket(byte_buf, {})
    air_assert(ppkt.payload_length == 100, "Failed parsed pkt length check")
    air_assert(ppkt.payload_offset == 0, "Failed parsed pkt length check")
    air_assert(ppkt.header_length == 0, "Header length not 0 on init")
    
    # Replicate the packet
    repl = ppkt.replicate()
    air_assert(repl.payload_length == 100, "Failed repl pkt length check")
    air_assert(repl.payload_offset == 0, "Failed repl pkt length check")
    air_assert(repl.header_length == 0, "Repl header length not 0 on init")

    # Parse an ethernet header; verify packet updated, replicant not.
    ppkt.parse_header("ethernet", iri.air_object_map["ethernet"])
    air_assert(ppkt.payload_length == 100 - 14, "Parsed pkt length check")
    air_assert(ppkt.payload_offset == 14, "Parsed pkt offset check")
    air_assert(ppkt.header_length == 14, "Header len not 14 after eth add")
    
    air_assert(repl.payload_length == 100, "Repl pkt length check")
    air_assert(repl.payload_offset == 0, "Repl pkt offset check")
    air_assert(repl.header_length == 0, "Repl header len not 0 after eth add")

    # Check set/get unparsed fields
    air_assert(ppkt.get_field("ipv4.version") == None,
               "Unparsed field get should return None")
    air_assert(ppkt.set_field("ipv4.version", 3) == None,
               "Unparsed field set should return None")

    # Check get field ops
    exp_eth_val = 0x0c0d # Expected value; 
    eth_val = ppkt.get_field("ethernet.ethertype")
    air_assert(eth_val == exp_eth_val, 
               "Expected 0x%x for ethtype; got 0x%x" % (exp_eth_val, eth_val))

    exp_mac_val = 0x000102030405 # Expected value; 
    mac_val = ppkt.get_field("ethernet.dst_mac")
    air_assert(mac_val == exp_mac_val, 
               "Expected 0x%x for dst MAC; got 0x%x" % (exp_mac_val, mac_val))

    exp_mac_val = 0x060708090a0b # Expected value; 
    mac_val = ppkt.get_field("ethernet.src_mac")
    air_assert(mac_val == exp_mac_val, 
               "Expected 0x%x for src MAC; got 0x%x" % (exp_mac_val, mac_val))

    # Check set ops
    exp_eth_val = 0x17
    eth_val = ppkt.set_field("ethernet.ethertype", exp_eth_val)
    air_assert(eth_val == exp_eth_val, 
               "Expected 0x%x for ethtype set; got 0x%x" %
               (exp_eth_val, eth_val))
    eth_val = ppkt.get_field("ethernet.ethertype")
    air_assert(eth_val == exp_eth_val, 
               "Expected 0x%x for ethtype after set; got 0x%x" %
               (exp_eth_val, eth_val))

    # Verify MAC unchanged
    exp_mac_val = 0x000102030405 # Expected value; 
    mac_val = ppkt.get_field("ethernet.dst_mac")
    air_assert(mac_val == exp_mac_val, 
               "Expected 0x%x for dst MAC; got 0x%x" % (exp_mac_val, mac_val))

    exp_mac_val = 0x060708090a0b # Expected value; 
    mac_val = ppkt.get_field("ethernet.src_mac")
    air_assert(mac_val == exp_mac_val, 
               "Expected 0x%x for src MAC; got 0x%x" % (exp_mac_val, mac_val))

    # Modify a MAC addr
    exp_mac_val = 0xa0a1a2a3a4a5
    mac_val = ppkt.set_field("ethernet.dst_mac", exp_mac_val)
    air_assert(eth_val == exp_eth_val, 
               "Expected 0x%x for dst MAC set; got 0x%x" %
               (exp_mac_val, mac_val))
    mac_val = ppkt.get_field("ethernet.dst_mac")
    air_assert(mac_val == exp_mac_val, 
               "Expected 0x%x for dst MAC after set; got 0x%x" %
               (exp_mac_val, mac_val))

    eth_val = ppkt.get_field("ethernet.ethertype")
    air_assert(eth_val == exp_eth_val, 
               "Expected 0x%x for ethtype after set; got 0x%x" %
               (exp_eth_val, eth_val))    

    exp_mac_val = 0x060708090a0b # Expected value; 
    mac_val = ppkt.get_field("ethernet.src_mac")
    air_assert(mac_val == exp_mac_val, 
               "Expected 0x%x for src MAC; got 0x%x" % (exp_mac_val, mac_val))

    # Add a header
    air_assert(ppkt.add_header_after("ethernet", iri.header["ethernet"],
                                     "ethernet") is None,
               "Should fail to add existing header ethernet")
    ip_hdr_len = ppkt.add_header_after("ipv4", iri.header["ipv4"], "ethernet")
    air_assert(ip_hdr_len == 20, "Adding ipv4, expected len %d. got %d" % 
               (20, ip_hdr_len))

    # Should not have affected the payload
    air_assert(ppkt.payload_length == 100 - 14, "Parsed pkt length check")
    air_assert(ppkt.payload_offset == 14, "Parsed pkt offset check")
    air_assert(ppkt.header_length == 14 + ip_hdr_len, "hdr len check")

    hdr_len = ppkt.remove_header("ethernet")
    air_assert(hdr_len == 14, "Remove should return header length")

    # Should not have affected the payload
    air_assert(ppkt.payload_length == 100 - 14, "Post remove length check")
    air_assert(ppkt.payload_offset == 14, "Post remove offset check")
    air_assert(ppkt.header_length == ip_hdr_len, "Post remove hdr len")
    
