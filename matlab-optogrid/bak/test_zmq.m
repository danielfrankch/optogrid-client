

%% Initialize ZMQ connection
py.importlib.import_module('zmq');
context = py.zmq.Context();
socket = context.socket(py.zmq.REQ);
socket.connect('tcp://localhost:5555');  % Changed to inproc transport

%% Test 1: Connect to device
socket.send_string('optogrid.connect = OptoGrid 1');
reply = char(socket.recv_string());
fprintf('Connect reply: %s\n', reply);
pause(2); % Wait for connection

%% Test 2: Enable IMU streaming
socket.send_string('OptoGrid.enableIMU');
reply = char(socket.recv_string());
fprintf('Enable IMU reply: %s\n', reply);
pause(1);

%% Test 3: Send sync markers
for i = 1:1
    socket.send_string(sprintf('OptoGrid.sync = %d', i));
    reply = char(socket.recv_string());
    fprintf('Sync reply %d: %s\n', i, reply);
    pause(0.5);
end

%% Test 4: Program opto settings
socket.send_string('OptoGrid.program');
reply = char(socket.recv_string());
fprintf('Program init reply: %s\n', reply);

% Create and send settings structure
settings = struct();
settings.sequence_length = 1;
settings.led_selection = 33024;    % First 4 LEDs
settings.duration = 1000;       % 1 second
settings.period = 20;         % 2 seconds
settings.pulse_width = 5;     % 100ms
settings.amplitude = 100;       % 100%
settings.pwm_frequency = 50000;  % 1kHz
settings.ramp_up = 0;         % 1000ms
settings.ramp_down = 2000;       % 0ms

socket.send_string(jsonencode(settings));
reply = char(socket.recv_string());
fprintf('Program settings reply: %s\n', reply);
pause(1);

%% Test 5: Send triggers
for i = 1:1
    socket.send_string('OptoGrid.trigger');
    reply = char(socket.recv_string());
    fprintf('Trigger reply %d: %s\n', i, reply);
    pause(1);
end

%% Test 6: Disable IMU
socket.send_string('OptoGrid.disableIMU');
reply = char(socket.recv_string());
fprintf('Disable IMU reply: %s\n', reply);

%% Cleanup
socket.close();
context.term();
fprintf('Test complete!\n');