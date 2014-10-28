#!/usr/bin/env python
# Simple queuing module

import threading
import sys

from air.air_common import *
from processor import ThreadedProcessor

class SimpleQueueManager(ThreadedProcessor):
    """
    @brief Manage a bunch of queues, support replication
    @param name The name of the TM object
    @param air_traffic_manager_attrs The  AIR TM attributes
    @param port_count The number of ports to support
    @param next_processor The next packet processor function to call

    This simple queue manager uses the threading of ThreadedProcessor
    to provide post-dequeue processing to have a thread context (this
    object's context).

    When the process() method is called, the calculation of the
    proper queue in which to submit the packet(s) is made and
    copying, etc, is done in that thread context. Then the queue's
    thread is invoked and does the dequeuing.

    Currently supports only strict priority (max is highest)
    """
    def __init__(self, name, air_traffic_manager_attrs, port_count):
        ThreadedProcessor.__init__(self, name)
        self.port_count = port_count
        self.next_processor = None
        self.q_per_port = air_traffic_manager_attrs["queues_per_port"]
        if "max_bytes" in air_traffic_manager_attrs.keys():
            self.max_bytes = air_traffic_manager_attrs["max_bytes"]

        # The map from egress spec to set of ports for multicast
        self.multicast_map = []

        # Threading synchronization
        self.cond_var = threading.Condition()
        self.event = threading.Event()
        self.running = True

        # Set up the queues as simple lists
        self.queues = []
        for port in range(port_count):
            self.queues.append([])
            for q_idx in range(self.q_per_port):
                self.queues[port].append([])

        for port in range(port_count):
            self.queues.append([]) # Queues for port p_idx
            for queue in range(self.q_per_port):
                self.queues[port].append([])  # Empty queue for q_idx
        self.discipline = "strict"

    def map_egress_spec(self, egress_spec):
        """
        @brief Implements egress spec semantics.

        0xffffffff : Drop packet
        MSB clear  : queue in top 15 bits, port in lower 16 bits
        MSB set    : Lower 16 bits is MC index (TODO)

        If egress spec is not set, drop packet
        """

        if egress_spec is None:
            return []

        if egress_spec == 0xffffffff:
            return []
        elif egress_spec & 0x10000000 == 0: # Unicast w/ port in lower 16 b
            return [(egress_spec & 0xffff, (egress_spec >> 16) & 0xffff)]
        else:
            mc_idx = egress_spec & 0xffff
            if mc_idx in self.multicast_map.keys():
                return self.multicast_map[mc_idx]
        return []

    def process(self, parsed_packet):
        """
        Accept the parsed_packet for processing

        The egress is determined by using 
        intrinsic_metadata.egress_specification:
          is_drop_spec() : Packet to be dropped
          get_unicast_spec() : If not None, a pair giving (port, queue)
          get_multicast_spec() : If not None, an array of pairs (port, queue)
        """
        egr_spec = parsed_packet.get_field(
            "intrinsic_metadata.egress_specification")
        if egr_spec is None:
            logging.debug("Did not find egress_spec for pkt %d" %
                          parsed_packet.id)
            return
        dest_ports = self.map_egress_spec(egr_spec)
        logging.debug("Queue %s: got pkt %d; egr 0x%x. dest %s", self.name, 
                      parsed_packet.id, egr_spec, str(dest_ports))

        for idx, (port, queue) in enumerate(dest_ports):
            if idx + 1 == len(dest_ports):
                replicant = parsed_packet
            else:
                replicant = parse_packet.replicate()
            with self.cond_var:
                logging.debug("Enqueuing packet %d in %d.%d" %
                              (parsed_packet.id, port, queue))

                self.queues[port][queue].append(replicant)
                self.event.set()

    def run(self):
        last_port = 0
        while self.running:
            # Wait on notification from process()
            self.event.wait()
            if not self.running:
                break

            # Process packets until none left
            while True:
                packet = None
                with self.cond_var:
                    # Determine the next queue to service
                    # Round robin on ports, strict priority
                    # @TODO support other disciplines
                    logging.debug("Queue %s awake" % self.name)
                    for port_idx in range(self.port_count):
                        if packet:
                            break
                        port = (port_idx + last_port + 1) % self.port_count
                        for queue in reversed(range(self.q_per_port)):
                            if len(self.queues[port][queue]) > 0:
                                logging.debug("Dequeue from %d.%d" % 
                                              (port, queue))
                                packet = self.queues[port][queue].pop(0)
                                packet.set_field(
                                    "intrinsic_metadata.egress_port", port)
                                last_port = port
                                break
                if packet:
                    logging.debug("%s dequeued pkt %d" % (self.name, packet.id))
                    if self.next_processor is not None:
                        self.next_processor.process(packet)
                else:
                    break

            # @TODO Should this be done with self.cond_var?
            self.event.clear()

        logging.debug("Exiting tm %s" % self.name)

    def kill(self):
        """
        @brief Terminate the thread

        Sets running to False and notifies event
        """
        self.running = False
        self.event.set()

    def set_discipline(self, discipline):
        """
        @brief Set the queuing discipline
        @param discipline Must be "strict"
        """
        if discipline != "strict":
            logging.error("TM %s: Only strict priority supported" % self.name)
        self.discipline = discipline

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filename=sys.argv[1])
    logging.info("RUNNING MODULE: %s" % __file__)

    global test_packets
    test_packets = 0
    def test_processor(packet):
        logging.debug("Test process packet called on %d" % packet.id)
        global test_packets
        test_packets += 1

    from parsed_packet import ParsedPacket

    tm_attrs = {
        "type" : "traffic_manager",
        "doc" : "The central traffic manager",
        "queues_per_port" : 8,
        "dequeue_discipline" : "strict"
    }

    tm = SimpleQueueManager("tm", tm_attrs, 10)
    tm.next_processor = test_processor

