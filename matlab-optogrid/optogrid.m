% filepath: /Users/danielmac/repos/OptoGrid/Python Client/matlab-optogrid/OptoGrid.m
classdef OptoGrid < handle
    properties
        DeviceName = 'OptoGrid 1'
        OptoSetting = struct(...
            'sequence_length', 1, ...
            'led_selection', uint64(34359738368), ...
            'duration', 550, ...
            'period', 25, ...
            'pulse_width', 10, ...
            'amplitude', 100, ...
            'pwm_frequency', 50000, ...
            'ramp_up', 0, ...
            'ramp_down', 200)
        BatteryReading = []
        ZMQSocket = 'tcp://localhost:5555'
        context
        socket
        trigger_success_flag = 0 % Defaults to 0, when trigger success, set 1
    end

    methods
        function start(obj)
            py.importlib.import_module('zmq');
            obj.context = py.zmq.Context();
            obj.socket = obj.context.socket(py.zmq.REQ);
            obj.socket.connect(char(obj.ZMQSocket));
            obj.socket.setsockopt(py.zmq.RCVTIMEO, int32(20000)); % 20s timeout in ms
        end

        function success = connect(obj)
            success = 0;
            for attempt = 1:10
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
        
        function success = toggleStatusLED(obj, state)
            % Toggle the status LED on the device (state = 1 for ON, 0 for OFF)
            if nargin < 2
                error('You must specify state (1=on, 0=off)');
            end
            obj.socket.send_string(sprintf('optogrid.toggleStatusLED = %d', state));
            try
                reply = char(obj.socket.recv_string());
            catch
                reply = '';
            end
            if contains(reply, 'Status LED turned on') && state == 1
                success = 1;
            elseif contains(reply, 'Status LED turned off') && state == 0
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

    function [success, DeviceName, battery_voltage_mV] = readbattery(obj)
        obj.socket.send_string(sprintf('optogrid.readbattery'));
        try
            reply = char(obj.socket.recv_string());
        catch
            reply = '';
        end
        
        % Default values
        success = 0;
        DeviceName = obj.DeviceName; % Use the DeviceName property
        battery_voltage_mV = 0;

        if contains(reply, 'Battery Voltage')
            success = 1;
            % Extract device name and voltage using regular expressions
            device_pattern = '^(.*?) Battery Voltage';
            voltage_pattern = 'Battery Voltage = (\d+) mV';
            
            device_tokens = regexp(reply, device_pattern, 'tokens');
            voltage_tokens = regexp(reply, voltage_pattern, 'tokens');
            
            if ~isempty(device_tokens)
                DeviceName = device_tokens{1}{1};
            end
            
            if ~isempty(voltage_tokens)
                battery_voltage_mV = str2double(voltage_tokens{1}{1});
            end
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