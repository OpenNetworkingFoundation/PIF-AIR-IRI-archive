The IRI Specification
=====================

IRI is an implementation of an AIR virtual switch. It accepts an AIR
switch specification instance and a set of port interface specifications.
It connects to those interfaces and accepts and transmits packets on
those interfaces according to the logic specified in the switch
specification.

Status
------

IRI is a prototype and in development.

IRI is implemented in Python.

Architecture
------------

**The IRI Switch Class**

The top level class in the iri module is Switch. This accepts an AIR
input specification and a dataplane object (see below). It creates an
IRI object from the AIR specification and then polls the dataplane for
packets, passing them to the IRI object. 

The IRI object is passed a transmit wrapper allowing it to transmit
packets.

**The IRI Instance Class**

The top level IRI object inherits from the AIR object and thus has
access to the dictionaries (maps) derived from the YAML switch description.
From this it generates operational instances for each processor object.
Parsers and traffic managers translate directly. The match+action
processor is called a `pipeline` object. Each AIR `control_flow` object
defines the connectivity for a pipeline. In addition, a pipeline uses
the table and action specifications from the AIR description (or, more
accurately, the operational IRI objects derived from the corresponding
AIR objects).

**IRI Processors**

The AIR specification calls out a subclass of top level objects called
_processors_. Conceptually, these objects accept packets for processing,
queuing or replication and produce packets. They are put together by a
_layout_ description (which is specified by AIR).

Currently IRI supports only a list type layout description indicating
the order of processing with no conditional transitions (although any
processor may drop a packet). 

Thus a `processor` object in IRI must implement a `process()` method
and support a `next_processor` data member. The `next_processor` 
member is set to the object whose `process()` function will be called 
for packets being emitted by the current processor. If `next_processor`
is None, the processor will drop all packets.

This leaves only packet transmission. For consistency, IRI defines
a special egress processor object. This provides a `process()`
method (so it can be used as a `next_processor`). This class is 
initialized with the proper transmit function for the data plane.

**Threading and Packet Processing**

IRI supports a very simple threading model. There is an ingress thread
and, normally, one egress thread.

- Packets are passed to the IR instance from the context of the
thread that receives the packet. This is called the ingress thread.
- Packets receive ingress processing (parsing and ingress match+action
in the ingress pipeline) in this same thread context.
- Each traffic manager block has its own thread context. When packets
are passed to the queuing block they are replicated (if necessary) and
queued in the ingress thread context.
- The traffic manager's thread (the egress thread) dequeues each packet 
and executes the egress pipeline on it. At the end of processing by the 
egress pipeline, a transmit wrapper is called (assuming the packet was 
not dropped).

More generally, each traffic manager has its own thread context. That
is the context used for dequeuing a packet and executing the subsequent
(processor) on the packet.

IRI can be modified to support different threading models, for example,
each processor object could execute in its own thread or a processor could
provide a thread pool for processing.

**IRI Classes**

In general, IRI classes are driven by the corresponding AIR classes.
The main additions are the following:

- ParsedPacket: Manages the header and metadata parts of a packet. Starts
with an unparsed packet and has methods:
  - Parse packet data into a header instance
  - Set/get fields in headers and metadata
  - Add/remove headers
  - Replicate the packet
  - Reserialize the packet for transmission
- SimpleQueueManager: A simple queuing/buffering block. This is the 
only traffic manager processor currently supported by IRI.

The IRI additionally defines functional objects for the following
AIR objects:

- Table: A match+action table 
- Header: A header instance that can extract from a data buffer and allows
set/get access to its fields
- Action: Supports an `eval` operation on packets
- Parser: Has `process` method that applies to packets and parses
headers from the packet's original buffer.

- Pipeline: A processor based on a control_flow AIR object. It 
instantiates tables and applies actions to a packets

**The Data Plane**

An IRI switch object is initialized with a data plane object. This object
must provide the following methods:

- `dataplane.poll(timeout)`: Poll the data plane for a receive packet. This
function returns a triple `(port-number, packet, time-stamp)` if a packet
is available.
- `dataplane.send(output_port, packet)`: Transmit the indicated packet out
the given port.
- `dataplane.kill()`: Terminate the data plane thread.

The data plane object is based on the OFTest dataplane implementation, but
should only depend on the above interfaces.

**Table Initialization Specification**

An IRI instance specification may provide a sequence of table entries to be
added during initialization of the switch. These entries are added after the
instance is created and before it begins processing packets. The format of
the specification of these entries is as follows (**format subject to change**):

    table_initialization :
      - <table_name> : # Add the following entry to this table
        match_values : # Match criteria
          <header-or-field-ref> : <value>
          ...
        match_masks : # For ternary matches
          <header-or-field-ref> : <mask-value>
          ...
        priority : <value> # For ternary matches
        action : <action_name>
        action_params :
          <param-name> : <value>
          ...
      ...

If `match_values` are not specified, the entry is added as the default entry.

If a field's match type is ternary and `match_masks` is not specified for that
field, "all ones" is assumed.


**Other Notes**

An IR instance must have an `intrinsic_metadata` definition which includes
an `egress_specification` field. The mapping of a specific value in the 
egress specification is determined by the run time programming

Future: The layout description may be extended to support conditional
transitions. In this case, the connection of processors may be
represented with a graph, just as `parser` and `control_flow` objects.

Currently, in the control flow transition specifications, action=identifier,
the special identifiers "hit", "miss", "always" and "default" are supported.
The values "hit" and "miss" correspond to whether or not a hit occurred in 
the table. The value "always" takes precedence if it is present. The value
"default" will be used if no other transition is specified.
