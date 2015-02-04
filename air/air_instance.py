#!/usr/bin/env python

"""
@file
@brief AIR configuration declaration

Does syntax validation of an AIR configuration instance.
"""

import os
import yaml
from air_common import *
from collections import OrderedDict # Requires Python 2.7

class FileAggregator(object):
    """
    Aggregate a bunch of files into a single string of input.
    Track offsets for each file
    """
    def __init__(self, files=None):
        self.aggregate = ""
        self.offsets = OrderedDict()
        self.total_lines = 0
        if files is not None:
            self.add_file(files)

    def add_file(self, files):
        """
        @brief Add file or files to the aggregator
        @param files A filename or list of filenames to add
        """
        if isinstance(files, list):
            for filename in files:
                self._add_file(filename)
        else:
            self._add_file(files)

    def _add_file(self, filename):
        logging.debug("Adding file %s to aggregate" % filename)
        with open(filename) as f:
            self.offsets[filename] = self.total_lines
            self.aggregate += f.read()
            self.total_lines = len(self.aggregate.split("\n")) - 1

    def absolute_to_file_offset(self, offset):
        """
        @brief Return the (filename, file-offset) for the given offset
        @param offset An absolute offset in self.aggregate
        """

        air_assert(offset <= self.total_lines, "Bad offset reference")
        prev_filename = None
        prev_file_offset = -1
        for filename, file_offset in self.offsets.items():
            if offset < file_offset:
                break # Found the "next" file
            prev_filename = filename
            prev_file_offset = file_offset
        return (prev_filename, offset - prev_file_offset)

    def file_to_absolute_offset(self, filename, file_offset):
        """
        @brief Return the absolute offset for the given file and file_offset
        @param filename The name of the file
        @param file_offset The relative location in filename
        @returns The absolute offset of the line in the aggregate

        Does no error checking
        """
        return self.offsets[filename] + file_offset

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
        self.external_object_map = {}
        self.aggregate_list = [] # List of aggregator objects
        if not air_meta_yaml:
            # Try to load from local file meta.yml
            try:
                local_dir = os.path.dirname(os.path.abspath(__file__))
                air_meta_yaml = open(local_dir + "/air_meta.yml", "r")
            except Exception, e:
                air_fatal_error("Could not open default metalanguage file air_meta.yml: %s" % str(e.args))
        try:
            self.process_yaml(yaml.load(air_meta_yaml))
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
        logging.debug("Added object %s of type %s", name, type)

    def process_external_object(self, name, attrs):
        """
        @brief Process an object not recognized as an AIR object
        @param name The name of the object
        @param attrs The value associated with the object

        External objects are just recorded for classes that inherit from AIR
        """
        self.external_object_map[name] = attrs
        logging.debug("Added external object %s", name)

    def process_yaml(self, input):
        """
        @brief Add YAML content to the AIR instance
        @param input The YAML dict to process
        @returns Boolean, False if error detected
        """

        for key, val in input.items():
            if key in air_meta_keys:
                self.process_meta(key, val)
            elif isinstance(val, dict) and "type" in val.keys():
                self.process_air_object(key, val)
            else:
                self.process_external_object(key, val)

    def add_content(self, input):
        """
        @brief Add content to this AIR instance
        @param input a file object, name of a file to read or list of filenames
        @returns Boolean: False if error detected in content

        If a list of files is given, they are aggregated into one
        chunk of input and processed by yaml as a whole.
        """
        logging.debug("Adding content %s" % str(input))

        if isinstance(input, file):
            input_string = input.read()
        else:
            agg = FileAggregator(input)
            input_string = agg.aggregate
            self.aggregate_list.append(agg)

        yaml_input = yaml.load(input_string)
        logging.debug("Yaml loaded for %s" % str(input))

        try:
            self.process_yaml(yaml_input)
        except AirValidationError, e:
            air_fatal_error("Could not process input files %s: %s" %
                            (str(input), str(e.args)))

# Current test just instantiates an instance
if __name__ == "__main__":
    import sys
    instance = AirInstance()
    if len(sys.argv) > 1:
        instance.add_content(sys.argv[1])

    air_assert(isinstance(instance.header, dict), "No headers attribute")
    air_assert("ethernet" in instance.header.keys(),
               "Expected ethernet in header map")
