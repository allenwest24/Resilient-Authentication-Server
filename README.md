# Authentication

## Overall Purpose:

    1. Implementation of a network service that provides password authentication
    2. Defends the service against denial-of-service attacks
    3. Defends the service against online password guessing attacks

## Service Specification:
Implements a simple protocol using protobuf v3 messages. In this protocol, each message is preceded by a two-byte, big-endian integer giving the length of the following protobuf message. Each TCP connection only supports one message exchange. The protocol is as shown below.

    C -> S : u16(|Request|) * Request
    S -> C : u16(|Response|) * Response
    
The messages themselves are devined in messages.proto

The protocol runs on port 13000/tcp. StopRequest is a meta-request; upon reception, the server immediately terminates. ResetBlockListsRequest is also a meta-request; upon reception, the server immediately expunges all block list entries.

The application protocol consists of ExpressionRequest and ExpressionResponse exchanges; think of the service as a trivial example of outsourced computation. The server implements user authentication by checking usernames and passwords against a provided database. The database consists of a TOML document that contains an array of user objects with username and password_hash keys. Password hashes follow PHC string format. This server supports the following hash algorithms.


    - SHA-256
    - SHA-512
    - bcrypt
    - Argon2
    
An example user database is provided in users.toml.

On successful authentication, the authenticated field is set to true in the response. The server also provides the result of evaluating the Python expression contained in the request’s expression field in the response’s result field. If authentication failed, authenticated is set to false in the response and result is undefined.

Expression evaluation is implemented by executing a Python interpreter on the expression. The result is the captured output of the evaluation (stdout only).

## Defending Against Attacks:
The service implements defenses against denial-of-service and password guessing attacks.
    
    - The server provides concurrent service for at least many clients through the use of multithreading.
    - The server identifies clients that send more than 30 invalid requests within the span of 60 seconds to the service, 
    and permanently blocks those source IP addresses. Invalid requests are those that fail to parse, that do not contain 
    a required field such as a username or password, that contain an invalid password, that contain an invalid expression, 
    or have any other feature that prevents a successful response.
