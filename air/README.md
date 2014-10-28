The AIR Specification
=====================

AIR stands for An Intermediate Representation. It is really a meta-language
mechanism allowing the specification of a set of valid keywords and for
each a set of attributes. There is a default metalanguage specification
in air_meta.yml

An AIR Instance
---------------

An AIR instance is a set of valid YAML input satisfying the constraints
described below.

- The top level keys `air_types`, `air_processors` and `air_attributes`
are required.
  - `air_types`: A list of strings. These are the names recognized by AIR 
as top level type identifiers.
  - `air_attributes`: A mapping from strings in the `air_types` list
to lists of strings. The list gives the set of valid attributes for
that type.
  - `air_processors`: A subset of the `air_types` list. These are the
AIR objects which are recognized as packet processors.
- An **AIR Object** is a top level YAML mapping node which has a key 
named `type`. The value of the `type` attribute must be a string in
`air_types`.
- **Common attributes**: The strings `doc` and `type`. 
- For an AIR object, each attribute must be valid for its type: that is,
occur in the list `air_attributes` for the object's type or be a common
attribute.

Default AIR Types
-----------------

The default AIR types are as follows:

- table: A match+action table description
- header: A header description (list of fields with attributes)
- metadata: Like a header, but specifies metadata
- action: An action description, parameters list and implementation
- parse_state: A parser state, giving extraction and next-state value spec
- parser: A processor object described by a graph specifying the 
transitions between parser states
- control_flow: A graph specifying how to transition between tables 
for a "pipeline"
- traffic_manager: An object to represent queuing, buffering and replication
- processor_layout: A graph describing how processor objects are connected

Processors include parsers, control_flows, and traffic_managers.

These are described in the default metalanguage file `air_meta.yml`.

Non-AIR Object Specifications
---------

An AIR specification may include non-AIR object specifications. These are
recorded in the `external_object_map` member of the AIR instance.

AIR Python Classes
------------------

The primary class for AIR is `AirInstance`. This object accepts a reference
to an AIR input instance and does initial processing and validation of
the input. After validation of the input, each type in `air_type` becomes an
attribute of that instance; it gives a map from names to attribute
dictionaries . Thus, after

`obj = AirInstance(some_input)`

`obj.header` is a map from header names to dictionaries of attributes
for each header. Similarly for `obj.table`, `obj.action`, `obj.metadata`, etc.

The map `obj.processors` is a map from all the processor object names
(parsers, control_flows, traffic_managers) to the attributes for the
respective object.

Note: Currently all processors share a namespace.

