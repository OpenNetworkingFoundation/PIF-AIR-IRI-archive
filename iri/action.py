#!/usr/bin/env python
# @file
# @brief Action primitive classes

import sys

from air.air_common import *

class PrimitiveAction(object):
    pass

class IriPrimitiveModifyField(PrimitiveAction):
    def __init__(self, args):
        self.name = "ModifyField"
        air_assert(len(args) in [2, 3], "Bad param list for modify_field")
        self.destination = args[0]
        self.source = args[1]
        if len(args) > 2:
            self.mask = args[2]
        else:
            self.mask = None
        logging.debug("Prim action %s. Dst %s. Src %s. Mask %s" %
                      (self.name, self.destination, self.source,
                       str(self.mask)))
        # Verify destination is a field reference
        # Source may be: field ref or field value
        # Verify dest and source are compatible types

    def eval(self, parsed_packet, value_map):
        """
        @brief Apply modify field to the parsed packet
        @param parsed_packet The packet to update
        @param value_map Map from references to values for table params and
        packet data
        """
        # @TODO Support run time reference binding
        # Check if destination is valid for parsed_packet; 
        logging.debug("Applying %s to pkt %d. Values %s" %
                      (self.name, parsed_packet.id, str(value_map)))
        if not self.destination in value_map.keys():
            logging.debug("Dest fld %s not parsed in pkt %d",
                          self.destination, parsed_packet.id)
        if self.mask:
            new_val = (value_map[self.destination] & ~self.mask |
                       value_map[self.source] & self.mask)
        else:
            new_val = value_map[self.source]
        parsed_packet.set_field(self.destination, new_val)

class IriPrimitiveAddHeader(PrimitiveAction):
    def __init__(self, args):
        self.name = "AddHeader"
        air_assert(len(args) == 1, "Bad param list for add_header")
        self.header_ref = args[0]
        # Verify header_ref is valid reference
        logging.debug("Prim action %s. Hdr %s" % (self.name, self.header_ref))

    def eval(self, parsed_packet, value_map):
        """
        @brief Apply add header to the parsed packet
        @param parsed_packet The packet to update
        @param value_map Map from references to values for table params and
        packet data
        """
        logging.debug("Applying %s to pkt %d. Values %s" %
                      (self.name, parsed_packet.id, str(value_map)))
        parsed_packet.add_header(self.header_ref)

class IriPrimitiveRemoveHeader(PrimitiveAction):
    def __init__(self, args):
        self.name = "RemoveHeader"
        air_assert(len(args) == 1, "Bad param list for remove_header")
        self.header_ref = args[0]
        # Verify header_ref is valid reference
        logging.debug("Prim action %s. Hdr %s" % (self.name, self.header_ref))

    def eval(self, parsed_packet, value_map):
        """
        @brief Apply remove header to the parsed packet
        @param parsed_packet The packet to update
        @param value_map Map from references to values for table params and
        packet data
        """
        logging.debug("Applying %s to pkt %d. Values %s" %
                      (self.name, parsed_packet.id, str(value_map)))
        pass
    
class IriPrimitiveAddToField(PrimitiveAction):
    def __init__(self, args):
        self.name = "AddToField"
        air_assert(len(args) == 2, "Bad param list for add_to_field")
        self.field_name = args[0]
        self.value = args[1]
        # @todo Error checking
        if isinstance(self.value, str):
            self.value = int(self.value, 0)
        logging.debug("Prim action %s. Fld %s. Value %s" %
                      (self.name, self.field_name, str(self.value)))


    def eval(self, parsed_packet, value_map):
        """
        @brief Apply add-to-field to the parsed packet
        @param parsed_packet The packet to update
        @param value_map Map from references to values for table params and
        packet data
        """
        logging.debug("Applying %s to pkt %d. Values %s" %
                      (self.name, parsed_packet.id, str(value_map)))
        value = parsed_packet.get_field(self.field_name)
        logging.debug("Old value: %d" % value)
        value += self.value
        value = parsed_packet.set_field(self.field_name, value)

class IriPrimitiveNoOp(PrimitiveAction):
    def __init__(self, args):
        self.name = "NoOp"
        air_assert(len(args) == 0, "Bad param list for no_op")
        logging.debug("Prim action %s" % self.name)

    def eval(self, parsed_packet, value_map):
        logging.debug("Applying %s to pkt %d. Values %s" %
                      (self.name, parsed_packet.id, str(value_map)))
    
# @brief Map from primitive name to class
primitive_action_to_class = {
    "modify_field"   : IriPrimitiveModifyField,
    "add_header"     : IriPrimitiveAddHeader,
    "remove_header"  : IriPrimitiveRemoveHeader,
    "add_to_field"   : IriPrimitiveAddToField,
    "no_op"          : IriPrimitiveNoOp,
}

class Action(object):
    """
    @brief An action object that can be applied by a table

    An action in AIR is a set of calls to primitive actions. The
    parameter values are either bound explicitly in the primitive
    action call or are bound to parameters to the action itself;
    in the latter case they are given values from the table entry
    which matched and invoked the action.
    """
    def __init__(self, name, air_action_attrs):
        self.name = name
        if "parameter_list" in air_action_attrs.keys():
            self.param_list = air_action_attrs["parameter_list"]
        else:
            self.param_list = {}
        self.primitives = []
        self.param_refs = set()

        # Parse the implementation
        prim_calls = air_action_attrs["implementation"].split(";")[:-1]
        for call in prim_calls:
            call = call.replace("\n","").strip()
            prim_name, args = call.split("(", 2)
            air_assert(prim_name in primitive_action_to_class.keys(),
                       "Action %s has unknown primitive: %s" %
                       (name, prim_name))
            params = [prm.strip() for prm in args.strip(" ,)").split(",")]
            self.primitives.append(primitive_action_to_class[prim_name](params))
            for param in params:
                self.param_refs.add(param)

    def eval(self, parsed_packet, action_params):
        """
        Apply this action to a parsed packet instance
        """
        logging.debug("Applying %s to pkt %d" % (self.name, parsed_packet.id))
        air_assert(set(action_params.keys()) == set(self.param_list),
                   "Action %s. Need params %s; got %s" %
                   (self.name, str(self.param_list), str(action_params)))
        # Create a dict with the values to use (parallel semantics)
        values = action_params.copy()
        for ref in self.param_refs:
            if ref in values.keys():
                continue
            value = parsed_packet.get_field(ref)
            if value is not None:
                # May not be a field ref at all
                values[ref] = value

        # Apply each primitive with the value map
        for prim in self.primitives:
            prim.eval(parsed_packet, values)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    import yaml
    act_yaml = """
set_l2_vfi_a :
  type : action
  doc : "Set the VFI in metadata and choose L2 forwarding"
  format : action_set
  parameter_list :
    - vfi_id # infer type
  implementation : >-
    modify_field(route_md.vfi, vfi_id);
"""
    action_map = yaml.load(act_yaml)
    for name, map in action_map.items():
        act = Action(name, map)

