# server.py
import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

print("Python ZMQ Server is listening on port 5555...")

while True:
    message = socket.recv_string()
    print(f"Received from MATLAB: {message}")
    socket.send_string(f"Hello MATLAB, got your message: {message}")
