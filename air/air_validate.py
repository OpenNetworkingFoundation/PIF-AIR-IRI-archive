"""
@file
@brief Validator for AIR

Does semantic validation of the AIR instance
"""

from air.common import *

def air_validate_parser(instance):
    """
    @brief Semantic validation of an AIR instance
    @param instance The AIR instance map
    @returns Boolean, True if instance is valid.

    The instance is assumed to be a syntactically valid instance.
    This routine checks:

        The Parser:
            Each edge connects two declared states

    In so doing, the validator generates additional structures
    and binds them to the IR. These inc
    """
    pass

def air_validate_instance(instance):
    """
    @brief Semantic validation of an AIR instance
    @param instance The AIR instance map
    @returns Boolean, True if instance is valid.

    The instance is assumed to be a syntactically valid instance.
    This routine calls the object specific validators:
        parser
        tables

        The Parser:
            Each edge connects two declared states

    In so doing, the validator generates additional structures
    and binds them to the IR. These inc
    """
    pass


def air_check_object(air_instance, obj_type_name, name, type, 
                     implementation_type=None):
    """
    @brief Check basic AIR characteristics for an object reference
    @param air_instance The top level mapping for the IR
    @param obj_type_name The name of the object to report on error
    @param name The name of the top level object
    @param type The expected AIR type for the object
    @param implementation_type If not None, check impl is present and has type

    TODO Support a set for implementation type
    """

    air_assert(name in air_instance.keys(),
               "%s: %s is not in top level for type %s" % 
               (obj_type_name, name, type))
    air_assert("type" in air_instance[name].keys(), 
               "%s: %s is not an AIR object" % (obj_type_name, name))
    air_assert(air_instance[name]["type"] == type,
               "%s: %s is not the expected type. Got %s, expected %s" %
               (obj_type_name, name, air_instance[name]["type"], type))

    if implementation_type is not None:
        air_assert("format" in air_instance[name].keys(), 
                   "%s: Expected format indication for %s" %
                   (obj_type_name, name))
        air_assert(air_instance[name]["format"] == implementation_type,
                   "%s: implementation format for %s is %s, expected %s" %
                   (obj_type_name, name, air_instance[name]["format"],
                    implementation_type))
        air_assert("implementation" in air_instance[name].keys(), 
                   "%s: Expected implemenation for %s" %
                   (obj_type_name, name))
        air_assert("implementation" in air_instance[name].keys(), 
                   "%s: Expected implemenation for %s" %
                   (obj_type_name, name))

def air_check_header(air_instance, name):
    """
    @brief Validate a reference to an AIR header
    @param air_instance The top level AIR instance map
    @param name The name of the header
    @returns Boolean, True if a valid reference
    """
    if name not in air_instance.keys():
        return False
    if "type" not in air_instance[name].keys():
        return False
    if air_instance[name]["type"] != "header":
        return False
    return True

def air_validate_data_ref(air_instance, name):
    """
    @brief Validate a reference to an AIR field
    @param air_instance The top level AIR instance map
    @param name The reference being checked
    @returns Boolean, True if a valid reference

    Currently only supports header and header.fld
    """
        
    parts = name.split(".")
    if len(parts) == 1:
        return air_check_header(air_instance, parts[0])
    elif len(parts) == 2:
        return air_find_field(air_instance, parts[0], parts[1]) is not None
    return False

