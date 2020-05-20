# Command Sequencing

The low-level Off-Chain protocol allows two VASPs to sequence request-responses for commands originating from either VASP, in order to maintain a consistent database of shared objects. Sequencing a command requires both VAPSs to confirm it is valid, as well as its sequence in relation to other commands.  Both VASPs in a channel can asynchronously attempt to initiate and execute commands on shared objects. The purpose of the command sequencing protocols is to ensure that such concurrent requests are applied in the same sequence at both VASPs to ensure that the state of shared objects remains consistent.


## Protocol Server and Client roles

In each channel one VASP takes the role of a _protocol server_ and the other the role of a _protocol client_ for the purposes of sequencing commands into a joint command sequence. Note that these roles are distinct to the HTTP client/server -- and both VASPs act as an HTTP server and client to listen and respond to requests.

Who is the protocol server and who is the client VASP is determined by comparing their binary on-chain Address strings (we call those the _binary address_. The following rules are used to determine which entity serves as which party: The last bit of VASP A’s parent binary address _w_ (where `w = addr[15] & 0x1`) is XOR’d with the last bit in VASP B’s parent binary address _x_.  This results in either 0 or 1.
If the result is 0, the lexicographically lower parent address is used as the server side.
If the result is 1, the lexicographically higher parent address is used as the server side. Lexicographic ordering determines which binary address is higher by comparing byte positions one by one, and returning the address with the first higher byte.

By convention the _server_ always determines the sequence of a request in the joint command sequence. When the server creates a `CommandRequestObject` it already assigns it a `command_seq` in the joint sequence of commands. When it responds to requests from the client, its `CommandResponseObject` contains a `command_seq` for the request into the joint command sequence. The protocol client never assigns a `command_seq`, but includes one provided by the protocol server in its responses.

Next: [Travel Rule Data Exchange](travel_rule_data_exchange.md)

Previous: [Basic Building Blocks](basic_building_blocks.md)
