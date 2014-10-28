#!/usr/bin/env python
#
# @file
# @brief Thread instance for IRI switch
#
# The Switch class inherits from Thread. It takes a dataplane object
# and an AIR configuration reference (filename, for example). It loads
# the AIR configuration as an IRI instance. Then it polls the dataplane
# for packets, passing them to the IRI instance.

import argparse
import os
import time
import sys
import yaml
import logging
from instance import IriInstance
from threading import Thread
    
class Switch(Thread):
    """
    @brief An IR switch instance

    """
    def __init__(self, name, input, dataplane):
        """
        @param name The name of the switch instance
        @param input A file or file name with the AIR YAML for the switch
        @param dataplane The OFTest dataplane object

        dataplane must provide
          (port_number, packet_buffer, timestamp) = poll(timeout) 
          send(port_number, packet_buffer)
        """
        Thread.__init__(self)

        logging.info("Starting IRI Switch instance %s" % name)
        self.name = name
        self.input = input
        if isinstance(input, list):
            self.input = " ".join(input)
        self.dataplane = dataplane
        self.killed = False
        self.instance = IriInstance(name, input, dataplane.send)
        self.instance.process_table_init()
        self.instance.enable()

        self.start()

    def run(self):
        """
        @brief The thread runner function

        Poll the data plane for packets. When received, parse and process.

        @todo figure out queue threading
        """
        metadata = self.instance.metadata
        logging.info("IR switch %s running with input %s" % (
            self.name, str(self.input)))
        while not self.killed:
            (port_num, pkt, ts) = self.dataplane.poll(timeout=2)
            if pkt:
                logging.debug("Pkt in port %d. len %d, ts %d" %
                              (port_num, len(pkt), ts))
                self.instance.process_packet(port_num, pkt)

        logging.info("Exiting IR switch %s" % self.name)

    def kill(self):
        self.killed = True
        self.dataplane.kill()
        self.instance.kill()
