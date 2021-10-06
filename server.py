import sys
import socket
import messages_pb2
import _thread as thread
from io import StringIO

bind_port = 13000
block_list = []

# Checks the database to authenticate and returns True or False.
def authenticate(username, password):
    return True

# Upon proper authentication, an expression will be ran in an interpreter and the result will be returned.
def execute_expression(expression):
    # Store the old_stdout
    actual_stdout = sys.stdout

    # Create a variable that will act as new stdout.
    out = StringIO()
    sys.stdout = out

    # Now run the expression.
    eval(expression)

    # Fix stdout.
    sys.stdout = actual_stdout
    result = out.getvalue()    
    return result

# Crafts the StopResponse. Server will be stopped elsewhere once response has been sent out.
def stop():
    response = messages_pb2.Response()
    stop_response = messages_pb2.StopResponse()
    response.stop.CopyFrom(stop_response)
    return response

# Resets the block list upon request. Crafts ResetBlockListsResponse.
def reset_block_list():
    # TODO: Possibly re-implement as another file nearby.
    global block_list
    block_list = []

    # Craft the response.
    response = messages_pb2.Response()
    RBLResponse = messages_pb2.ResetBlockListsResponse()
    response.reset.CopyFrom(RBLRResponse)
    return response

# Handles an expression request.
def handle_expression(req):
    # Check if the credentials are valid.
    authenticated = authenticate(req.expr.username, req.expr.password)
    
    # Either way, we will need to craft an ExpressionResponse.
    response = messages_pb2.Response()
    expr_response = messages_pb2.ExpressionResponse()

    # If yes, return positive ExpressionResponse.
    if authenticated:
        expr_response.authenticated = authenticated
        expr_response.result = execute_expression(req.expr.expression)
        print("successful expression request: ", expr_response)
    else:
        expr_response.authenticated = authenticated
        print(response)

    response.expr.CopyFrom(expr_response)
    return response

# Handles an invalid request.
def handle_invalid_req():
    print("That was invalid")

# Outputs the type of request recevied.
def determine_req_type(req):
    if req.HasField('stop'):
        return 'stop'
    elif req.HasField('reset'):
        return 'reset'
    elif req.HasField('expr'):
        return 'expr'
    else:
        return 'invalid'

# Takes in the request sent and returns the appropriate response.
def handle_request_forge_response(req):
    req_type = determine_req_type(req)
    if req_type == 'stop':
        return stop(), 1
    elif req_type == 'reset':
        return reset_block_list(), 2
    elif req_type == 'expr':
        return handle_expression(req), 3

def on_new_client(connection, client_address):
    # Take the frist two bytes of big endian as the recv size for the rest of the message.
    req_size = int.from_bytes(connection.recv(2), 'big')
    print(req_size)

    # Get the actual request and parse it into the protobuf msg.
    req = connection.recv(req_size)
    # TODO: remove print statement.
    msg = messages_pb2.Request()
    msg.ParseFromString(req)
    print(req)
    print(msg)
    #vals = [field.name for field in msg.DESCRIPTOR.fields]
    print(msg.HasField('expr'))
    print(msg.expr.username)

    # Branch off and handle.
    data, code = handle_request_forge_response(msg)
    data = data.SerializeToString()
    data_length = len(data).to_bytes(2, 'big')
    connection.send(data_length + data)
    print(data_length + data)
        
    # If this was a stop request, we need to shut down the server after the response is sent.
    if code == 1:
        exit()

    connection.close()

# Starts the server and listens on the designated port.
def start_server(port):
    global bind_port

    bind_port = port

    # Open a socket and bind it to the server specifications.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # TODO: make sure localhost is what we want always or take in input.
    server_address = ('127.0.0.1', bind_port)
    sock.bind(server_address)

    # Listens for a single connection and prints out what it receives.
    # TODO: Allow for multiple connections at once.
    sock.listen(5)
    while True:
        # Accept a new connection on the socket.
        connection, client_address = sock.accept()
        thread.start_new_thread(on_new_client(connection, client_address))

    sock.close()

# Main method.
def main():
    # TODO: Take in port from the command line.
    start_server(13000)
    print(bind_port)

if __name__ == "__main__":
    main()
