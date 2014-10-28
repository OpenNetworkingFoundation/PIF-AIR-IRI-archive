#
# THIS IS A WORK IN PROGRESS AND PURELY TENTATIVE
# MAY NOT END UP BEING THE RIGHT ABSTRACTION FOR PROCESSORS IN GENERAL
#


from Queue import Queue
from threading import Thread
from threading import Lock
from threading import Condition

class Processor(object):
    """
    @brief Base class for processor types

    Processors provide a process() method which is called on parsed
    packet instances. The object takes ownership of the packet instance.

    Currently in IRI, only linear layouts of processor instances are
    supported. So a processor object exposes a next_processor member.
    This must be set duing initialization to be the processor object
    that should be called on parsed packet instances to be emitted from
    this processor.

    """

    def __init__(self, name, next_processor=None):
        """
        @param name The name of the processor object
        @param next_processor Instance variable holding the next processor
        """
        self.name = name
        self.next_processor = None

    def process(self, parsed_packet):
        """
        @brief Process method for a processor class
        @param parsed_packet A packet to be processed by this object

        A processor must implement a process method. This is called
        on a parsed packet. The processor "takes ownership" of the
        parsed packet instance. It may replicate the parsed packet,
        queue it for processing in another thread, drop the packet,
        or operate on it in place before passing it to the next
        processor.
        """
        raise AIRImplementation("Super class %s does not implement process"
                                % str(type(self)))

class ThreadedProcessor(Thread, Processor):
    """
    @brief Base class for threaded processor types

    Provides the base class for a processor which supports its own
    thread context for processing and producing packets.

    The threaded_processor.process() function enqueues the passed
    packet into its own queue for processing in its own thread
    context. That is done by the _process() function which must be
    implemented by the super class.

    Because of this decoupling, the consumer of the packets produced
    by this processor must be plumbed. Currently the only support for
    this connectivity is by registering a consumer for packets produced
    by the processor.

    POR: To support more flexible composition of processor
    composition, the plan is to allow the packet to store the 
    "next processor", essentially as metadata.

    @todo The implementation is not really relevant and should probably be removed
    """

    def __init__(self, name, max_queue_size=0):
        """
        @param name The name of the processor object
        @param max_queue_size Queue will block if max_queue_size is reached
        """
        Thread.__init__(self)
        Processor.__init__(self, name)
        self.next_processor = None

        self.max_queue_size = max_queue_size
        self.queue = Queue(max_queue_size)
        self.running = True

    def process(self, parsed_packet):
        """
        @param parsed_packet The packet to process

        See Processor base class. 

        The default behavior is to enqueue the packet passed for processing 
        in this objects thread context

        May be overridden by super class to do a different
        processing model (alternative queuing)
        """
        self.queue.put(parsed_packet, block=True, timeout=None)

    def run(self):
        """
        Activity function for class
        """
        while True:
            pkt = self.queue.get()
            if self.running:
                self._process(pkt)

    def kill(self):
        self.running = False
        self.queue.join()

    def _process(self, parsed_packet):
        """
        Should not be called. The sub class must implement _process()
        """
        raise IriImplementationError("Processor %s: Super class %s " %
            (self.name, str(type(self))) + "of threaded_processor does "
            "not implement _process")
