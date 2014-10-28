#!/usr/bin/env python
#
# Field class implementation

import logging
import sys

from air.air_common import *
from iri_exception import *
from field import field_instance, field_width_get

class HeaderInstance(object):
    """
    @brief Represent a header or header stack instance for a packet

    @todo Support header stacks

    @todo Consider making mutable and immutable versions
    """

    # Constant null header used for uninitialized headers
    # Assume header is at most max packet size of 12K
    MAX_PACKET_BYTES = 12 * 1024
    empty_byte_array = bytearray(MAX_PACKET_BYTES)

    def __init__(self, name, air_header_attrs, byte_buffer=None, 
                 offset=0, length=None):
        """
        @param name The name of the instance
        @param air_header_attrs The header attributes from the IR instance. If None,
        indicates this is an opaque block of bytes with no field structure
        @param byte_buffer A bytearray from a packet 
        @param offset The byte offset in byte_buffer where the header starts
        @param length Force the length when air_header_attrs is None or when length
        is determined externally.
        """

        logging.debug("Adding hdr %s" % name)
        self.name = name
        self.air_header_attrs = air_header_attrs

        self.byte_buffer = byte_buffer
        self.offset = offset # The offset in the buffer where the header starts
        self.length = 0
        self.bit_length = 0

        self.modified = False # Have field values changed?
        self.fields = ListDict()

        # Resolve initial value
        if byte_buffer:
            air_check(isinstance(byte_buffer, bytearray), IriParamError)
        else: # Use all zeros for initial parsing
            self.byte_buffer = HeaderInstance.empty_byte_array

        # Iterate thru fields, getting bit-width of each
        if not air_header_attrs: # Opaque block header
            air_check(length is not None, IriParamError)
            self.length = length
            return

        # @FIXME: 
        # self.is_stack = ("max_depth" in air_header_attrs.keys() and
        #                  air_header_attrs["max_depth"] > 1)

        # Parse header from data
        field_values = {} # Holds integer values for fields for width calc
        bit_offset = 0 # Offset of "current" field in the header

        # Keep track of remaining length of header if already known

        if length:
            remaining_bits = length * 8
        else:
            remaining_bits = None

        # Parse the header according to its IR description
        for field_map in self.air_header_attrs["fields"]:
            for field_name, attrs in field_map.items(): # Just one instance
                # First, get the width in case it depends on the values
                # of other fields already parsed.
                width = field_width_get(field_name, attrs, field_values, 
                                        remaining_bits)
                field = field_instance(field_name, attrs, width)
                field.extract(self.byte_buffer, self.offset, bit_offset)

                bit_offset += width
                if remaining_bits:
                    remaining_bits -= width

                self.fields[field_name] = field
                if isinstance(field.value, int):
                    field_values[field_name] = field.value

        self.bit_length = bit_offset
        self.length = (bit_offset + 7) / 8
        if length and length != self.length:
            logging.warn("Header %s length %d != passed length %d" %
                         (name, self.length, length))

        if self.length != bit_offset / 8:
            logging.info("Added padding to header %s; bit length was %d" %
                         (self.name, bit_offset))

    def length(self):
        """
        Return the length of the header instance in bytes
        """
        return self.length

    def get_field(self, field_name):
        """
        @brief Get the value of a field from the header

        @param field_name The field to look up
        @returns value of the field if valid

        Does no error checking; returns 0 if field is not valid
        """
        if not self.fields or field_name not in self.fields.keys():
            return 0

        return self.fields[field_name].value

    def set_field(self, field_name, value, width=None):
        """
        @brief Set the value of a field in the header
        @param field_name The name of the field to modify
        @param value The value to use.
        @param width (Optional) New width of the field

        @returns The new value of the field
        The value may be an integer or a byte array
        """
        if field_name not in self.fields.keys():
            return None
        if type(value) not in [int, bytearray]:
            return None

        if width:
            if width != field.width:
                logging.debug("Changing header width for %s, fld %s" %
                              (self.name, field_name))
                diff = width - field.width
                self.bit_length += diff
                self.length = (self.bit_offset + 7) / 8
                field.resize(width)
                
        self.fields[field_name].value = value
        self.modified = True
        return value

    def serialize(self):
        """
        @brief Generate a byte array representing the header
        """
        if not self.modified:
            return self.byte_buffer[self.offset:self.offset + self.length]

        # Otherwise, create a byte array with current field values
        byte_list = bytearray(self.length)
        bit_offset = 0
        for field_name, field in self.fields.items():
            field.update_header_bytes(byte_list, bit_offset)
            bit_offset += field.width
        return byte_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)
    hdr_dict = {
        "type" : "header",
        "fields" :
        [
            {"dst_mac" : 48},
            {"src_mac" : 48},
            {"ethertype" : 16}
        ]
    }
    
    header = HeaderInstance("hdr", hdr_dict, bytearray(100))
    air_assert(header.length == 14)

    air_assert(header.get_field("ethertype") == 0, "Failed ethertype get")
    bytes = header.serialize()
    air_assert(bytes == bytearray(14), "Failed serialize 0 bytes")

    header.set_field("ethertype", 0xffff)
    air_assert(header.modified, "Header should be modified")
    bytes = header.serialize()
    expected = bytearray(14)
    expected[12] = 0xff
    expected[13] = 0xff
    air_assert(bytes == expected, "Failed serialize bytes after modify")
