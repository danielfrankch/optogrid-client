% filepath: /Users/danielmac/repos/OptoGrid/Python Client/matlab-optogrid/optogrid.m
classdef optogrid < handle
    properties
        DeviceName = "OptoGrid 1"
        OptoSetting = struct(...
            'sequence_length', 1, ...
            'led_selection', 33024, ...
            'duration', 1000, ...
            'period', 20, ...
            'pulse_width', 5, ...
            'amplitude', 100, ...
            'pwm_frequency', 50000, ...
            'ramp_up', 0, ...
            'ramp_down', 2000)
        BatteryReading = []
        ZMQSocket = "tcp://localhost:5555"
        context
        socket
    end

    methods
        function start(obj)
            py.importlib.import_module('zmq');
            obj.context = py.zmq.Context();
            obj.socket = obj.context.socket(py.zmq.REQ);
            obj.socket.connect(char(obj.ZMQSocket));
            obj.socket.setsockopt(py.zmq.RCVTIMEO, int32(10000)); % 10s timeout in ms
        end

        function success = connect(obj)
            success = 0;
            for attempt = 1:3
                obj.socket.send_string(sprintf('optogrid.connect = %s', obj.DeviceName));
                try
                    reply = char(obj.socket.recv_string());
                catch
                    reply = '';
                end
                if contains(reply, sprintf('%s Connected', obj.DeviceName))
                    success = 1;
                    return;
                end
            end
        end

        function success = enableIMU(obj)
            obj.socket.send_string(sprintf('optogrid.enableIMU'));
            try
                reply = char(obj.socket.recv_string());
            catch
                reply = '';
            end
            if contains(reply, 'IMU enabled, and logging started')
                success = 1;
            else
                success = 0;
            end
        end

        function success = disableIMU(obj)
            obj.socket.send_string(sprintf('optogrid.disableIMU'));
            try
                reply = char(obj.socket.recv_string());
            catch
                reply = '';
            end
            if contains(reply, 'IMU disabled, and logging stopped')
                success = 1;
            else
                success = 0;
            end
        end

        function success = trigger(obj)
            obj.socket.send_string(sprintf('optogrid.trigger'));
            try
                reply = char(obj.socket.recv_string());
            catch
                reply = '';
            end
            if contains(reply, 'Opto Triggered')
                success = 1;
            else
                success = 0;
            end
        end

        function success = program(obj)
            obj.socket.send_string(sprintf('optogrid.program'));
            try
                reply = char(obj.socket.recv_string());
            catch
                reply = '';
            end
            obj.socket.send_string(jsonencode(obj.OptoSetting));
            try
                reply2 = char(obj.socket.recv_string());
            catch
                reply2 = '';
            end
            if contains(reply2, 'Opto Programmed')
                success = 1;
            else
                success = 0;
            end
        end

        function success = sync(obj, val)
            if nargin < 2
                val = 1;
            end
            obj.socket.send_string(sprintf('optogrid.sync = %d', val));
            try
                reply = char(obj.socket.recv_string());
            catch
                reply = '';
            end
            if contains(reply, 'Sync Written')
                success = 1;
            else
                success = 0;
            end
        end

        function cleanup(obj)
            if ~isempty(obj.socket)
                obj.socket.close();
            end
            if ~isempty(obj.context)
                obj.context.term();
            end
        end
    end
end