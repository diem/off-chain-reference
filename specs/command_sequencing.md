# Command Sequencing

The low-level Off-Chain protocol allows two VASPs to sequence request-responses for commands originating from either VASP, in order to maintain a consistent database of shared objects. Sequencing a command requires both VAPSs to confirm it is valid, as well as its sequence in relation to other commands operating upon the same objects.  Since commands may operate upon multiple objects, a command only succeeds if the command is able to be applied to every dependent object - ensuring atomicity of the command and consistency of the objects. Both VASPs in a channel can asynchronously attempt to initiate and execute commands on shared objects. The purpose of the command sequencing protocols is to ensure that such concurrent requests are applied in the same sequence at both VASPs to ensure that the state of shared objects remains consistent. All commands upon shared objects which are exchanged between pairs of VASPs are sequenced relative to the prior state of each shared object in the command.


## Object Versioning

When either VASP creates a request, they assign a `_creates_version` to the object being created or mutated.  This string must be a unique random string between this pair of VASPs and is used to represent the version of the item created. These should be at least 16 bytes long and encoded to string in hexadecimal notation using characters in the range[A-Za-z0-9].  Upon every mutation of an object, this string must be updated to a new unique value.

To maintain relative ordering of commands on objects, every creation or mutation of an object must also specify the `_dependencies`.  The value in this field must match a version previously specified by the `_creates_versions` parameter on a prior command and indicates the version being mutated (or in the case of a new object being created which depends on no previous objects, the `_dependencies` list may be empty).  Each version may only be mutated once - because once it has been mutated, a new version is created to represent the latest state of the object. This results in what is essentially a per-object sequencing.


## Protocol Server and Client Roles

In each channel, one VASP takes the role of a _protocol server_ and the other the role of a _protocol client_ for the purposes of simplifying shared object locking / state management. Note that these roles are distinct to the HTTP client/server -- and both VASPs act as an HTTP server and client to listen and respond to requests.

Who is the protocol server and who is the client VASP is determined by comparing their binary on-chain Address strings (we call those the _binary address_. The following rules are used to determine which entity serves as which party: The last bit of VASP A’s parent binary address _w_ (where `w = addr[15] & 0x1`) is XOR’d with the last bit in VASP B’s parent binary address _x_.  This results in either 0 or 1.
If the result is 0, the lexicographically lower parent address is used as the server side.
If the result is 1, the lexicographically higher parent address is used as the server side. Lexicographic ordering determines which binary address is higher by comparing byte positions one by one, and returning the address with the first higher byte.

To avoid excessive locking and intermediate state management during API requests, by convention the _server_ acts as the source of truth for the state of an object.  In practice, this means that when the _server_ wishes to update state of an object, it writes the update directly to its database and then transmits the command.  When a _client_ wishes to update state of an object, it sends the command and then updates its database after receipt of confirmation from the _server_.  This avoids locking of objects during remote calls to the other VASP and state management due to the potential of dropped network connections.  Instead, upon dropped connections, each side must replay the request. 

## Example

To demonstrate how this protects against concurrent requests on objects, let us assume a mock database in the following format:

| version | object_id | object_type |
|-------	    |-----------	|-----------	|

We now create our 4 payments and our database now contains:


| version 	    | object_id 	| object_type 	| 
|-------	    |-----------	|-----------	|
| a | 1 | payment |
| b | 2 | payment |
| c | 3 | payment |
| d | 4 | payment |

There are some updates to the payments so that their versions get changed, so we now have a database containing:

| version 	    | object_id 	| object_type 	| 
|-------	    |-----------	|-----------	|
| e | 1 | payment |
| f | 2 | payment |
| g | 3 | payment |
| h | 4 | payment |

We now try to create a batch inclusive of payments 1,2,3.  To do so, we grab the object row corresponding to each payment and lock it.  So now we have:

| version 	    | object_id 	| object_type 	| 
|-------	    |-----------	|-----------	|
| e | 1 | payment <locked> |
| f | 2 | payment <locked> |
| g | 3 | payment <locked> |
| h | 4 | payment |
| i | 1 | batch |

As this is happening, a request to batch 2,3,4 arrives.  This request specifies the "_dependencies" of each as f,g,h and says it "creates_versions" 'w' which is the batch version it's trying to create.  Since 2 and 3 are locked, this request waits on those locks and nothing yet happens.

We go back to batch 'i' which is still in progress and holding the locks on the payments.  It updates each payment object in the payment table to say that they are in batch 1.  Then it unlocks the payments.

Now batch 2 gets the locks on the payments 2,3,4.  It then goes and reads the payment objects for those and sees that they already have a batch ID on them, so they can't be included in another batch.

So in effect, the version/dependencies work as a per-item sequence number. 


Next: [Travel Rule Data Exchange](travel_rule_data_exchange.md)

Previous: [Basic Building Blocks](basic_building_blocks.md)
