#!/usr/bin/env python
#
# @file
# @brief Generate templates for each file in template directory
#

import argparse
import os
import sys
import yaml
import logging
import shutil
import template_utils as tu
from iri.instance import IriInstance
import re

def ignore_file(filename):
    return re.match("^\..*|.*~$|.*\.cache$", filename)

def walk_template_dir(template_dir, output_dir, context):
    """
    Process each template 
    @param template_dir Input dir to walk
    @param output_dir Directory for output

    Each file in template_dir gets put in a corresponding
    sub directory of output_dir
    """

    for dir_name, sub_dir_list, file_list in os.walk(template_dir):
        dest_dir = dir_name.replace(template_dir, output_dir, 1)
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        for fname in file_list:
            if ignore_file(fname):
                continue
            source_file = os.path.relpath(os.path.join(dir_name, fname),
                                          template_dir)
            dest_file = os.path.join(dest_dir, fname)
            logging.info("Processing file %s to %s" %
                         (source_file, dest_file))
            with open(dest_file, "w") as outfile:
                tu.render_template(outfile, source_file,
                                   [template_dir], context)

################################################################

config_defaults = {
    "template_dir" : "templates",
    "output_dir" : "output",
    "clean" : False
}

parser = argparse.ArgumentParser(description='Generate templates',
        usage="%(prog)s source [source ...] [options]")
parser.set_defaults(**config_defaults)
parser.add_argument('sources', metavar='sources', type=str, nargs='+',
                    help='The source file to load')
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output")
parser.add_argument('-t', '--template_dir', type=str, 
                    help="The source directory for templates")
parser.add_argument('-o', '--output_dir', type=str,
                    help="The output directory for generated files")
parser.add_argument('-c', '--clean', action='store_true',
                    help="Remove existing output directory")

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

################################################################
# Create instance
################################################################

instance = IriInstance("TemplateInstance", args.sources, None)

# Create output directory if not present
output_dir = os.path.abspath(args.output_dir)
template_dir = os.path.abspath(args.template_dir)

if not os.path.exists(output_dir):
    os.makedirs(output_dir)
else:
    if args.clean:
        logging.info("Removing %s", output_dir)
        shutil.rmtree(output_dir)
        os.makedirs(output_dir)
    else:
        logging.info("Output dir already exists")

if not os.path.isdir(template_dir):
    logging.error("Can not find template dir %s" % template_dir)
    exit(1)

walk_template_dir(template_dir, output_dir, 
                  {"air_objects" : instance.air_object_map})

    

    
