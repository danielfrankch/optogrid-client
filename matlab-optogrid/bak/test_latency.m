% MATLAB latency test
import zmq.core.*
context = zmq.Context();
socket = context.socket(zmq.REQ);
socket.connect('tcp://localhost:5555');

n_trials = 100;
latencies = zeros(n_trials, 1);

for i = 1:n_trials
    tic;
    socket.send_string('OptoGrid.trigger');
    reply = char(socket.recv_string());
    latencies(i) = toc * 1000; % Convert to milliseconds
end

% Display results
fprintf('Average latency: %.3f ms\n', mean(latencies));
fprintf('Min latency: %.3f ms\n', min(latencies));
fprintf('Max latency: %.3f ms\n', max(latencies));
fprintf('Std dev: %.3f ms\n', std(latencies));

% Cleanup
socket.close();
context.term();