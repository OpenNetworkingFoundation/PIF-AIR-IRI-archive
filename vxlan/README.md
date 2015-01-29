This directory has code for a VXLAN gateway example.

Simplifications

- Physical ports determine the VXLAN interfaces, although 
multiple virtual networks may coexist on a port.
- No outer VLAN tag (for VXLAN encap'd packets)
- Always an inner VLAN tag
- IPv4 only
- Length and checksum fields are ignored for this example

Header instances and types

- Outer Ethernet : ethernet
- Outer IPv4 : ipv4
- Outer UDP : udp
- VXLAN header : vxlan
- Inner Ethernet : ethernet
- Inner IPv4 : ipv4
- Inner TCP : tcp
- Inner UDP : udp

Alternatively, Outer IPv4 may be Outer IPv6 (not implemented yet)

"Outer" always refers to the VXLAN encapsulation headers. "Inner"
always refers to the non-encapsulated addresses.

Rough Architecture

- Ports are either "native" or "encap". 
- Packets on native ports do not have a VXLAN header on ingress;
those on encap ports do have a VXLAN header on ingress.
- Packets on native ports are mapped to a virtual network based
on their VLAN ID. The virtual network is represented by a "vni"
which is the value carried in the VXLAN 
- Packets on encap ports get their VNI from the VXLAN header
- Packets on encap ports are decap'd in the ingress pipeline.
- Native forwarding is done based on Ethernet destination
address and VNI on native and decapsulated packets. This is done
by the "forward" table.
- If a packet is sent to an encap port, it is encapsulated
with a VXLAN header on the egress pipeline.

So the tables:

- Ingress
  - decap: Remove the VXLAN header and save the VNI in metadata. Applied
only on packets from encap ports and done uniformly.
  - resolve_vni: Applied to native packets, determine the VNI based on the
packet's VLAN id.
  - forward: Map the inner Ethernet dest and the VNI to an egress spec

- Egress
  - encap: For packets going to an encap port, apply the proper
VXLAN encapsulation.


  