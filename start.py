#!/usr/bin/env python
#
# Simple top level script to invoke an IR instance, optionally
# load a run time configuration and optionally load a run time
# control function.

import argparse
import os
import time
import sys
import yaml
import logging
import air
import iri
import signal

from oftest.dataplane import DataPlane

def start_dataplane(args):
    """
    @brief Start up the dataplane and attach port interfaces
    @param args The command line arguments

    The args parameter contains the interface descriptions for ports
    """
    
    logging.info("Starting dataplane")
    dataplane = DataPlane()

    port_idx = 1
    for port in args.interfaces.split(","):
        logging.info("Adding port %s" % port)
        spec_parts = port.split("@")
        if len(spec_parts) > 1:
            port_num = spec_parts[0]
            port_name = spec_parts[1]
        else:
            port_num = port_idx
            port_name = port
        dataplane.port_add(port, port_num)
        port_idx += 1

    return dataplane

################################################################
#
# Command line arguments
#
################################################################


config_defaults = {
    "interfaces" : "veth0,veth2,veth4,veth6"
}

parser = argparse.ArgumentParser(description='Instantiate an AIR switch',
        usage="%(prog)s source [source ...] [options]")
parser.set_defaults(**config_defaults)
parser.add_argument('sources', metavar='sources', type=str, nargs='+',
                    help='The source file to load')
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose output")
parser.add_argument('-i', '--interfaces', type=str, 
                    help="Specification of port interfaces NOT IMPLEMENTED")
parser.add_argument('--run_for', type=int,
                    help="Run for this many seconds before exit", default=0)
parser.add_argument('--dp_verbose', action='store_true',
                    help="Set dataplane verbose high")

# @todo: Add platform + full VPI support for dataplane port specs
# @todo: Allow specifying the AIR metalanguage file as (special) input

args = parser.parse_args()

args.port_count = 4
args.queues_per_port = 4

if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

logging.info("Creating IRI switch instance")

if args.run_for > 0:
    logging.info("Running for %d seconds", args.run_for)
    
if len(args.sources) < 1:
    error("Currently must specify at least 1 source file on command line")

# Remove python's signal handler which raises KeyboardError. Exiting from an
# exception waits for all threads to terminate which might not happen.
signal.signal(signal.SIGINT, signal.SIG_DFL)

dataplane = start_dataplane(args)

# But turn down dataplane verbose unless signaled
if not args.dp_verbose:
    dataplane.logger.setLevel(logging.INFO)

ir = iri.Switch("ichiban", args.sources, dataplane)

# TODO: Enter a monitor
count = 0
while 1:
    count += 1
    time.sleep(1)
    if args.run_for > 0:
        if count > args.run_for:
            break

logging.info("Terminating switch")
ir.kill()
ir.join()
