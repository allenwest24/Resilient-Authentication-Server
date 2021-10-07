import os
import sys
import socket
import messages_pb2
import _thread as thread
from io import StringIO

# Define global variables.
block_list = []
invalid_tracker = {}

# Tally invalid requests by IP.
def tally_invalid(ip):
    global invalid_tracker
    global block_list

    if ip in invalid_tracker:
        invalid_tracker[ip] += 1
    else:
        invalid_tracker[ip] = 1

    # TODO: Determine what to do when an IP is on the block list.
    if invalid_tracker[ip] >= 30:
        if ip not in block_list:
            block_list.append(ip)
            print(block_list)
    print(invalid_tracker)

# Checks the database to authenticate and returns True or False.
# TODO: Check against the actual database. To include tallying for invalid requests.
def authenticate(username, password, ip):
    # Does not contain a username or password.
    if len(username) == 0 or  len(password) == 0:
        #tally_invalid(ip)
        return False
    return True

# Upon proper authentication, an expression will be ran in an interpreter and the result will be returned.
def execute_expression(expression):
    # Store the old_stdout.
    actual_stdout = sys.stdout

    # Create a variable that will act as new stdout.
    out = StringIO()
    sys.stdout = out

    # Now run the expression.
    try:
        eval(expression)

        # Fix stdout.
        sys.stdout = actual_stdout
        result = out.getvalue()
    except:
        # Fix stdout.
        sys.stdout = actual_stdout
        result = "error" 

    return result

# Crafts the StopResponse. Server will be stopped elsewhere once response has been sent out.
def stop():
    response = messages_pb2.Response()
    stop_response = messages_pb2.StopResponse()
    response.stop.CopyFrom(stop_response)
    return response

# Resets the block list upon request. Crafts ResetBlockListsResponse.
def reset_block_list():
    # Reference the global block list.
    global block_list
    block_list = []

    # Craft the response.
    response = messages_pb2.Response()
    RBLResponse = messages_pb2.ResetBlockListsResponse()
    response.reset.CopyFrom(RBLResponse)
    
    return response

# Handles an expression request.
def handle_expression(req, ip):
    # Check if the credentials are valid.
    authenticated = authenticate(req.expr.username, req.expr.password, ip)
    
    # Either way, we will need to craft an ExpressionResponse.
    response = messages_pb2.Response()
    expr_response = messages_pb2.ExpressionResponse()

    # If yes, return positive ExpressionResponse.
    if authenticated:
        expr_response.authenticated = authenticated
        result = execute_expression(req.expr.expression)
        
        # If there was a problem executing the expression, this is an invalid message.
        if result == 'error':
            tally_invalid(ip)
            expr_response.authenticated = False
        # Otherwise, we want the result.
        else:
            expr_response.result = result
    # If not, reply as such.
    else:
        expr_response.authenticated = authenticated

    response.expr.CopyFrom(expr_response)
    return response

# Determine which type of request this is.
def determine_req_type(req):
    if req.HasField('stop'):
        return 'stop'
    elif req.HasField('reset'):
        return 'reset'
    elif req.HasField('expr'):
        return 'expr'

# Takes in the request sent and returns the appropriate response.
def handle_request_forge_response(req, ip):
    req_type = determine_req_type(req)
    if req_type == 'stop':
        return stop(), 1
    elif req_type == 'reset':
        return reset_block_list(), 2
    elif req_type == 'expr':
        return handle_expression(req, ip), 3

# After a thread has been designated for a connection, do the work.
def handle_client_req(connection, client_address):
    # Take the frist two bytes of big endian as the recv size for the rest of the message.
    req_size = int.from_bytes(connection.recv(2), 'big')

    # Get the actual request and parse it into the protobuf msg.
    req = connection.recv(req_size)
    msg = messages_pb2.Request()
    try:
        msg.ParseFromString(req)
        print(msg)

        # Branch off and handle.
        data, code = handle_request_forge_response(msg, client_address[0])
    except:
        # Failure to parse.
        tally_invalid(client_address[0])
        response = messages_pb2.Response()
        expr_response = messages_pb2.ExpressionResponse()
        expr_response.authenticated = False
        response.expr.CopyFrom(expr_response)
        data = response
        code = 0

    data = data.SerializeToString()
    data_length = len(data).to_bytes(2, 'big')
    connection.send(data_length + data)
        
    # If this was a stop request, we need to shut down the server after the response is sent.
    if code == 1:
        os._exit(1)

    connection.close()

# Starts the server and listens on the designated port.
def start_server(ip, port):
    server_ip = ip
    bind_port = port

    # Open a socket and bind it to the server specifications.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # TODO: make sure localhost is what we want always or take in input.
    server_address = ('127.0.0.1', bind_port)
    sock.bind(server_address)

    # Listens for a single connection and prints out what it receives.
    sock.listen(5)
    while True:
        # Accept a new connection on the socket.
        connection, client_address = sock.accept()
        thread.start_new_thread(handle_client_req, (connection, client_address))

    sock.close()

# Main method.
def main():
    # TODO: Take in port from the command line.
    start_server('127.0.0.1', 13000)

if __name__ == "__main__":
    main()
