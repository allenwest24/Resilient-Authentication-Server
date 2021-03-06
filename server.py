import os
import sys
import toml
import bcrypt
import socket
import hashlib
import messages_pb2
from io import StringIO
import _thread as thread
from datetime import datetime
from passlib.hash import argon2

# Define global data structures.
block_list = []
invalid_tracker = {}

# Take in the user database via the command line.
if len(sys.argv) >= 2:
    database_location = sys.argv[1]
else:
    database_location = "./users.toml"
database = toml.load(database_location)

# Tally invalid requests by IP.
def tally_invalid(ip):
    global invalid_tracker
    global block_list

    # Grab the time in seconds to timestamp the invalid request.
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    second = now.second
    time = second + (minute * 60) + (hour * 360)

    # Add a tally to this IP on the invalid list.
    if ip in invalid_tracker:
        invalid_tracker[ip].append(time)
    else:
        invalid_tracker[ip] = []
        invalid_tracker[ip].append(time)

    # If this is the 30th offense, block the ip.
    if len(invalid_tracker[ip]) >= 30:
        if time - invalid_tracker[ip][len(invalid_tracker[ip]) - 29] <= 60:
            if ip not in block_list:
                block_list.append(ip)

# Checks the database to authenticate and returns True or False.
def authenticate(username, password, ip):
    global database
    users = database['users']

    # If a username or password were not provided we don't need to check.
    if len(username) == 0 or len(password) == 0:
        return False

    # Find the specified user and pull up the hashed password.
    user_found = False
    for ii in range(len(users)):
        if users[ii]['username'] == username:
            stored_hash = users[ii]['password_hash']
            user_found = True
            break

    # If there was no user by that name the request is invalid.
    if not user_found:
        return False

    # Creating the byte versions of some variables so it just needs to be done once.
    passAsBytes = bytes(password, 'utf-8')
    storedHashAsBytes = bytes(stored_hash, 'utf-8')

    # Checking with supported hash functions to see if any match.
    # SHA256.
    if stored_hash == hashlib.sha256(passAsBytes).hexdigest():
        return True
    # SHA512.
    elif stored_hash == hashlib.sha512(passAsBytes).hexdigest():
        return True
    # bcrypt.
    try:
        if (bcrypt.checkpw(passAsBytes, storedHashAsBytes)):
            return True
    except:
        pass
    # Argon2.
    try:
        argon2.verify(password, stored_hash)
        return True
    except:
        pass

    # If we got here then the password is wrong.
    return False

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
    # Reference the global block list and invalid tracker.
    global block_list
    global invalid_tracker

    # Clear both lists.
    block_list = []
    invalid_tracker = {}

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

    # Determine if the sender ip is on the block list.
    if client_address[0] in block_list:
        ip_blocked = True
    else:
        ip_blocked = False

    # Try to parse, don't authenticate if you can't.
    try:
        msg.ParseFromString(req)

        # If the sender ip is on the block list we honor stop and resetblocklist reqs but ignore expr and close the connection immediatly.
        if ip_blocked and determine_req_type(msg) == 'expr':
            connection.close()
            return

        # Branch off and handle.
        data, code = handle_request_forge_response(msg, client_address[0])
    except:
        # Failure to parse.
        connection.close()
        tally_invalid(client_address[0])
        return

    # Tally if this is an invalid request.
    if data.HasField('expr'):
        if not data.expr.authenticated:
            tally_invalid(client_address[0])

    # Prep and send response.
    data = data.SerializeToString()
    data_length = len(data).to_bytes(2, 'big')
    connection.send(data_length + data)
        
    # If this was a stop request, we need to shut down the server after the response is sent.
    if code == 1:
        os._exit(1)

    connection.close()

# Starts the server and listens on the designated port.
def start_server(ip, port):
    # Open a socket and bind it to the server specifications.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (ip, port)
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
    start_server('0.0.0.0', 13000)

if __name__ == "__main__":
    main()
