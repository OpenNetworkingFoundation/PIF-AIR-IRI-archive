#!/usr/bin/env python
#
# Field class implementation

import struct
import array
import sys

from air.air_common import *
from iri_exception import *

def field_width_get(field_name, attrs, field_values, remaining_bits=None):
    """
    @brief Get the width of a field based on current values

    @param field_name The name of the field (for debug messages only)
    @param attrs The attributes from the top level desc
    @param field_values A dict used in eval if width is an expression
    @param remaining_bits Number of bits remaining in header, if known

    @todo Consider changing semantics to return an error (None)
    and do not do the assert here

    If the width calculation is negative, 0 is returned.
    """
    if isinstance(attrs, int):
        return attrs
    if isinstance(attrs, dict):
        air_assert("width" in attrs.keys(), "Bad field attrs; no width")
        return field_width_get(field_name, attrs["width"], field_values)
    # Attempt to evaluate a string expression
    air_assert(isinstance(attrs, str), 
               "Bad field attrs; not int, dict, string")
    try:
        width = eval(attrs, {"__builtins__":None}, field_values)
    except:  # @todo NameError?
        raise IriReferenceError("Bad width expression for %s" + field_name)

    # If calculation is negative, return 0
    if width < 0:
        return 0
    return width

class field_instance(object):
    """
    @brief A field is a value and a map of attributes
    
    @param name The name of the field as it appears in its parent header
    @param attrs Either a dict or an int; if an int, it is the width in bits
    @param width Width in bits of the field
    @param value An optional initial value of the field (host representation)

    Fields of width <= 64 bits are stored as integer values
    Fields of greater width are stored as "B" arrays. width must be 
    divisible by 8.
    """

    # Masks for bit widths <= 8
    BYTE_MASK = [0, 1, 3, 7, 0xf, 0x1f, 0x3f, 0x7f, 0xff]

    def __init__(self, name, attrs, width, value=None):
        self.name = name
        self.attrs = attrs
        self.width = width
        self.value = value

    def extract(self, buf, header_offset, bit_offset):
        """
        @brief Extract the field value from the given header instance

        @param buf A byte array holding the header data
        @param header_offset Start of the header instance in the buf
        @param bit_offset The bit offset into the header where the field starts

        NOTE that bit_offset is the offset from the start of the header, so
        it may be greater than 8.

        @todo Assumes the field does not extend beyond the packet boundary
        """
            
        air_assert(self.width >= 0,
                   "Unknown width when extracting field %s" % self.name)
        byte_offset = header_offset + (bit_offset / 8)
        bit_offset = bit_offset % 8
        width = self.width

        # Easy cases:
        if bit_offset == 0:
            base = byte_offset
            if width == 8:
                self.value = struct.unpack("!B", buf[base:base+1])[0]
                return self.value
            elif width == 16:
                self.value = struct.unpack("!H", buf[base:base+2])[0]
                return self.value
            elif width == 32:
                self.value = struct.unpack("!L", buf[base:base+4])[0]
                return self.value
            elif width == 64:
                self.value = struct.unpack("!Q", buf[base:base+8])[0]
                return self.value
            elif width > 64:
                self.value = bytearray(buf[base: base+width/8])
                return self.value

        air_assert(width < 64, "Bad field width/offset %d, %d for %s" %
                   (width, bit_offset, self.name))
        # Extract bytes into an array
        # Iterate thru the array accumulating value
        # Note that bit offsets are from high order of byte
        bytes_needed = (width + bit_offset + 7) / 8
        low = header_offset + byte_offset
        high = low + bytes_needed
        bytes = bytearray(buf[low:high])
        value = 0
        while width > 0:
            if width + bit_offset <= 8:
                high_bit = 7 - bit_offset
                low_bit = high_bit - width + 1
                val_from_byte = (bytes[0] >> low_bit) & self.BYTE_MASK[width]
                shift = ((width < 8) and width) or 8
                value = (value << shift) + val_from_byte
                break
            else:
                if bit_offset == 0:
                    value = (value << 8) + bytes.pop(0)
                    width -= 8
                else:
                    high_bit = 7 - bit_offset
                    val_from_byte = bytes.pop(0) & self.BYTE_MASK[high_bit + 1]
                    width -= (high_bit + 1)
                    bit_offset = 0
                    shift = ((width < 8) and width) or 8
                    value = (value << shift) + val_from_byte
        self.value = value
        return value

    def update_header_bytes(self, byte_list, bit_offset):
        """
        @brief Update a header (a list of bytes) with the current field value

        @param byte_list A bytearray representing the entire header
        @param bit_offset The bit offset of the field from the start 
        of the header
        """

        air_assert(self.width >= 0,
                   "Unknown field width for %s when updating header"
                   % self.name)

        byte_offset = (bit_offset / 8)
        bit_offset = bit_offset % 8
        width = self.width

        # Easy cases:
        if width == 0:
            return

        # Value is an array of bytes: copy them in 
        if isinstance(self.value, bytearray):
            for idx in range(len(self.value)):
                byte_list[byte_offset + idx] = self.value[idx]
            return

        # Byte boundary and just bytes
        # @todo Assumes big endian in the packet
        value = self.value
        if bit_offset == 0 and width % 8 == 0:
            for idx in reversed(range(width / 8)):
                byte_list[byte_offset + idx] = value & 0xff
                value >>= 8
            return

        # Hard cases: Shift value appropriately and convert to bytes
        # @todo This will have a problem if value << shift overflows
        bytes_needed = (width + bit_offset + 7) / 8

        shift = 8 - ((bit_offset + width) % 8)
        if shift == 8: shift = 0

        value <<= shift

        for idx in range(bytes_needed):
            value_byte = (value >> (8 * (bytes_needed - 1 - idx))) & 0xFF
            #print "  VAL", value_byte, width, bit_offset
            if width + bit_offset <= 8: # Fits in this byte and done
                shift = 8 - (bit_offset + width)
                mask = self.BYTE_MASK[width] << shift
                #print "  MASK", mask, byte_offset
                byte_list[byte_offset + idx] &= ~mask
                byte_list[byte_offset + idx] |= value_byte
                # Should be last entry
                width = 0
            else: # Goes to end of byte
                if bit_offset == 0:  # Covers whole byte
                    # width > 8 by above
                    byte_list[byte_offset + idx] = value_byte
                    width -= 8
                else: # Covers lower bits of byte
                    # width + bit_offset > 8, so goes to end of byte
                    mask = self.BYTE_MASK[8 - bit_offset]
                    byte_list[byte_offset + idx] &= ~mask
                    byte_list[byte_offset + idx] |= value_byte
                    width -= (8 - bit_offset)
                    bit_offset = 0
        
################################################################
#
# Test code
#
################################################################

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    # Testing code for field class
    attrs = 17
    air_assert(field_width_get("fld", attrs, {}) == 17, "Failed field test 1")

    attrs = {"width" : 17}
    air_assert(field_width_get("fld", attrs, {}) == 17, "Failed field test 2")

    attrs = "10 + 7"
    air_assert(field_width_get("fld", attrs, {}) == 17, "Failed field test 3")

    attrs = "x + 7"
    air_assert(field_width_get("fld", attrs, {"x" : 10}) == 17,
               "Failed field test 4")

    attrs = {"width" : "x + 7"}
    air_assert(field_width_get("fld", attrs, {"x" : 10}) == 17,
               "Failed field test 5")

    try:
        field_width_get("fld", "bad string", {})
        air_assert(False, "Failed field test 6")
    except IriReferenceError:
        pass

    # Two VLAN tags w/ IDs 356 and 200; the first has priority 5
    data = struct.pack("BBBBBBBB", 0x81, 0, 0xa1, 0x64, 0x81, 0, 0, 0xc8)

    field = field_instance("fld", {}, 8)
    field.extract(data, 0, 0)
    air_assert(field.value == 0x81,  "Failed field test 7")

    field = field_instance("fld", {}, 16)
    field.extract(data, 0, 0)
    air_assert(field.value == 0x8100,  "Failed field test 7")

    field = field_instance("vid", {}, 12)
    field.extract(data, 0, 20)
    air_assert(field.value == 356,  "Failed field test 8")

    field = field_instance("pcp", {}, 3)
    field.extract(data, 0, 16)
    air_assert(field.value == 5,  "Failed field test 9")

    # @todo Write test cases for fields that are longer byte streams

    values = range(16)
    values.extend([0xaaaaaaaa, 0x55555555, 0xffffffff])

    # Test with all 1 bits as baseline
    for width in range(33):
        for offset in range(32):
            for value in values:
                field = field_instance("f%d_%d" % (width, offset), {}, width)
                value &= ((1 << width) - 1)
                field.value = value
                byte_list = bytearray(8)
                for idx in range(8): byte_list[idx] = 0xff
                #print "START", value, width, offset
                field.update_header_bytes(byte_list, offset)
                #print "    UPDATE", array.array("B", byte_list)
                field.extract(byte_list, 0, offset)
                #print "        EXTRACTED", field.value
                air_assert(field.value == value, 
                           "Failed, all 1s, width %d, offset %d" %
                           (width, offset))

    # Test with all 0 bits as baseline
    for width in range(33):
        for offset in range(32):
            for value in values:
                field = field_instance("f%d_%d" % (width, offset), {}, width)
                value &= ((1 << width) - 1)
                field.value = value
                byte_list = bytearray(8)
                field.update_header_bytes(byte_list, offset)
                field.extract(byte_list, 0, offset)
                air_assert(field.value == value, 
                           "Failed convert case width %d, offset %d" %
                           (width, offset))

