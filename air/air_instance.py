#!/usr/bin/env python

"""
@file
@brief AIR configuration declaration

Does syntax validation of an AIR configuration instance.
"""

import os
import yaml
from air_common import *

# These are the metalanguage names recognized by AIR
air_meta_keys = ["air_types", "air_attributes", "air_processors"]

class AirInstance(object):
    """
    @brief An AIR configuration object definition

    @param air_types Recognized AIR types
    @param air_attrs Recognized AIR attributes by AIR type
    @param air_processor_types List of types that are to be recognized 
    as processors
    @param air_object_map Map from top level AIR objects to attribute maps
    @param external_object_map Map from non-AIR objects to attribute maps
    @param loaded_files A list of the files that have been loaded.

    Build the Python maps directly derived from the YAML structures.

    An air_instance object has an attribute for each entry in air_types
    which is a map from names to objects of that type; for instance
    header, table, metadata...

    air_instance.header[hdr_name]
    air_instance.parser[parser_name]
    etc
    """

    def __init__(self, air_meta_yaml=None):
        """
        @brief Init the air_instance object
        @param air_meta_yaml The top level definitions (type, attrs) to use

        air_meta_yaml is loaded by yaml.load; so it may be YAML text or
        a file object containing YAML text.

        If air_meta_yaml is not specified, try to open the local file meta.yml.

        """
        self.air_types = []
        self.air_processor_types = []
        self.air_attrs = {}
        self.air_object_map = {}
        self.loaded_files = []
        self.files_to_load = []
        self.external_object_map = {}
        meta_yaml_name = air_meta_yaml
        if not air_meta_yaml:
            # Try to load from local file meta.yml
            try:
                local_dir = os.path.dirname(os.path.abspath(__file__))
                meta_yaml_name = local_dir + "/air_meta.yml"
                air_meta_yaml = open(meta_yaml_name, "r")
            except Exception, e:
                air_fatal_error("Could not open default metalanguage file %s: %s" % (meta_yaml_name, str(e.args)))
        try:
            self.process_yaml(meta_yaml_name, yaml.load(air_meta_yaml))
        except AirValidationError, e:
            air_fatal_error("Could not process top level yaml: " + str(e.args))
        if isinstance(air_meta_yaml, file):
            air_meta_yaml.close()

    def process_meta(self, key, val):
        """
        @brief Process an AIR metalanguage directive
        @param key The top level key
        @param val The value associated with the key

        Supported metalanguage directives are listed in air_meta_keys
        """
        if key == "air_types":
            self.air_types.extend(val)
            # Initialize attributes for type with basics
            for type in val:
                if not type in self.air_attrs.keys():
                    self.air_attrs[type] = ["type", "doc"]
                    # Add a map for objects of this type to the config
                    setattr(self, type, {})
        elif key == "air_attributes":
            for type, attrs in val.items():
                if type not in self.air_types:
                    raise AirValidationError(
                        "Attrs assigned to unknown type: " + type)
                self.air_attrs[type].extend(attrs)
        elif key == "air_processors":
            self.air_processor_types.extend(val)

    def process_air_object(self, name, attrs):
        """
        @brief Process an AIR object declaration
        @param name The name of the object
        @param attrs The value associated with the object
        """
        # For now, just validate
        type = attrs["type"]
        # Check that attrs are all recognized
        for attr, attr_val in attrs.items():
            if attr not in self.air_attrs[type]:
                if True: # To be command line option "strict"
                    raise AirValidationError(
                        "Object '" + name + "' had bad attr: " + attr)
                else:
                    logging.warn("Object '" + name + "' had bad attr: " + attr)

        # Check that required attrs are present; TBD until "required" known
        # for attr in self.air_attrs[type]:
        #     if attr not in attrs.keys():
        #         raise AIRValidationError(
        #             "Object '" + name + "' is missing attr: " + attr)

        # Check if present in top level already
        if name in self.air_object_map.keys():
            # For now, this is an error; may need per-type way to handle
                raise AirValidationError(
                    "Air object '" + name + "' redefined")
        self.air_object_map[name] = attrs

        # Add this to the object set
        type_objs = getattr(self, type)
        type_objs[name] = attrs

    def process_external_object(self, name, attrs):
        """
        @brief Process an object not recognized as an AIR object
        @param name The name of the object
        @param attrs The value associated with the object

        External objects are just recorded for classes that inherit from AIR
        """
        self.external_object_map[name] = attrs

    def process_load_after_files(self, input_ref, list):
        for filename in list:
            # FIXME: Assumes input_ref is a string
            source_dir = os.path.dirname(os.path.abspath(input_ref))
            path_file = os.path.join(source_dir, filename)
            if path_file not in self.loaded_files:
                if path_file not in self.files_to_load:
                    logging.debug("Adding file to load %s" % path_file)
                    self.files_to_load.append(path_file)

    def process_yaml(self, input_ref, yaml_input):
        """
        @brief Add YAML content to the AIR instance
        @param input_ref Reference to where input is from
        @param yaml_input The YAML dict to process
        @returns Boolean, False if error detected
        """

        logging.info("Processing: " + input_ref)
        for key, val in yaml_input.items():
            if key in air_meta_keys:
                self.process_meta(key, val)
            elif key == "load_after_files":
                self.process_load_after_files(input_ref, val)
            elif isinstance(val, dict) and "type" in val.keys():
                self.process_air_object(key, val)
            else:
                self.process_external_object(key, val)

    def add_content(self, input):
        """
        @brief Add content to this AIR instance
        @param input a file object or the name of a file to read
        @returns Boolean: False if error detected in content
        """
        logging.debug("Adding content %s" % str(input))
        if isinstance(input, list):
            for filename in input:
                self.add_content(filename)
            return

        if isinstance(input, str):
            logging.info("Opening AIR input file: " + input)
            try:
                input_file = open(input, "r")
            except IOError as e:
                air_fatal_error("Could not open file: " + input)
        elif isinstance(input, file):
            input_file = input
        else:
            air_fatal_error("Cannot interpret AIR configuration for switch init")
        yaml_input = yaml.load(input_file)
        input_file.close()
        try:
            self.process_yaml(input, yaml_input)
        except AirValidationError, e:
            air_fatal_error("Could not process input file: " + str(e.args))

        logging.debug("Marking %s as loaded" % str(input))
        self.loaded_files.append(input)
        if input in self.files_to_load:
            self.files_to_load.remove(input)

        while len(self.files_to_load) > 0:
            self.add_content(self.files_to_load[0])

# Current test just instantiates an instance
if __name__ == "__main__":
    import sys
    instance = AirInstance()
    if len(sys.argv) > 1:
        instance.add_content(sys.argv[1])

    air_assert(isinstance(instance.header, dict), "No headers attribute")
    air_assert("ethernet" in instance.header.keys(),
               "Expected ethernet in header map")
