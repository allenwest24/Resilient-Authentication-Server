# Authentication

## The goals of this project were:

    1. Implement a network service that provides password authentication
    2. Defend the service against denial-of-service attacks
    3. Defend the service against online password guessing attacks

## Service Specification:
service will implement a simple protocol using protobuf v3 messages. In this protocol, each message is preceded by a two-byte, big-endian integer giving the length of the following protobuf message. Each TCP connection only supports one message exchange. The protocol is as shown below.
