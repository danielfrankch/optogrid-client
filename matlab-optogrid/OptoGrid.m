% filepath: /Users/danielmac/repos/optogrid-client/matlab-optogrid/OptoGrid.m

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
        ZMQSocket = 'tcp://localhost:5555'
        socket
        trigger_success_flag = 0
        timeout = 20000 % Timeout in milliseconds (add this property)
    end

    methods
        function start(obj)
            % Initialize ZMQ socket using zmqhelper
            obj.socket = net.zmqhelper('type', 'req', 'url', obj.ZMQSocket);
            % Set receive timeout on the underlying socket
            obj.socket.socket.setReceiveTimeOut(obj.timeout);
        end

        function success = connect(obj)
            success = 0;
            for attempt = 1:10
                obj.socket.sendmsg(sprintf('optogrid.connect = %s', obj.DeviceName));
                try
                    reply = obj.socket.waitformsg();
                    if contains(reply, sprintf('%s Connected', obj.DeviceName))
                        success = 1;
                        return;
                    end
                catch
                    % Timeout or other error occurred
                    continue;
                end
            end
        end

        function success = enableIMU(obj)
            obj.socket.sendmsg('optogrid.enableIMU');
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'IMU enabled, and logging started')
                    success = 1;
                else
                    success = 0;
                end
            catch
                success = 0;
            end
        end

        function success = disableIMU(obj)
            obj.socket.sendmsg('optogrid.disableIMU');
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'IMU disabled, and logging stopped')
                    success = 1;
                else
                    success = 0;
                end
            catch
                success = 0;
            end
        end
        
        function success = toggleStatusLED(obj, state)
            if nargin < 2
                error('You must specify state (1=on, 0=off)');
            end
            obj.socket.sendmsg(sprintf('optogrid.toggleStatusLED = %d', state));
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'Status LED turned on') && state == 1
                    success = 1;
                elseif contains(reply, 'Status LED turned off') && state == 0
                    success = 1;
                else
                    success = 0;
                end
            catch
                success = 0;
            end
        end

        function success = trigger(obj)
            obj.socket.sendmsg('optogrid.trigger');
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'Opto Triggered')
                    success = 1;
                else
                    success = 0;
                end
            catch
                success = 0;
            end
        end

        function [success, DeviceName, battery_voltage_mV] = readbattery(obj)
            obj.socket.sendmsg('optogrid.readbattery');
            
            % Default values
            success = 0;
            DeviceName = obj.DeviceName;
            battery_voltage_mV = 0;
            
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'Battery Voltage')
                    success = 1;
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
            catch
                % Timeout or other error - keep default values
            end
        end

        function [success, DeviceName, uLED_check] = readuLEDCheck(obj)
            obj.socket.sendmsg('optogrid.readuLEDCheck');
            
            % Default values
            success = 0;
            DeviceName = obj.DeviceName;
            uLED_check = '';
            
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'uLED Check')
                    success = 1;
                    % Extract device name and uLED check value
                    device_pattern = '^(.*?) uLED Check';
                    check_pattern = 'uLED Check = (.*)$';
                    
                    device_tokens = regexp(reply, device_pattern, 'tokens');
                    check_tokens = regexp(reply, check_pattern, 'tokens');
                    
                    if ~isempty(device_tokens)
                        DeviceName = device_tokens{1}{1};
                    end
                    
                    if ~isempty(check_tokens)
                        uLED_check = check_tokens{1}{1};
                    end
                end
            catch
                % Timeout or other error - keep default values
            end
        end

        function [success, DeviceName, last_stim_time_ms] = readlastStim(obj)
            obj.socket.sendmsg('optogrid.readlastStim');
            
            % Default values
            success = 0;
            DeviceName = obj.DeviceName;
            last_stim_time_ms = 0;
            
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'Last Stim Time')
                    success = 1;
                    % Extract device name and last stim time
                    device_pattern = '^(.*?) Last Stim Time';
                    time_pattern = 'Last Stim Time = (\d+) ms';
                    
                    device_tokens = regexp(reply, device_pattern, 'tokens');
                    time_tokens = regexp(reply, time_pattern, 'tokens');
                    
                    if ~isempty(device_tokens)
                        DeviceName = device_tokens{1}{1};
                    end
                    
                    if ~isempty(time_tokens)
                        last_stim_time_ms = str2double(time_tokens{1}{1});
                    end
                end
            catch
                % Timeout or other error - keep default values
            end
        end

        function success = program(obj)
            obj.socket.sendmsg('optogrid.program');
            try
                reply = obj.socket.waitformsg();
                obj.socket.sendmsg(jsonencode(obj.OptoSetting));
                reply2 = obj.socket.waitformsg();
                if contains(reply2, 'Opto Programmed')
                    success = 1;
                else
                    success = 0;
                end
            catch
                success = 0;
            end
        end

        function success = sync(obj, val)
            if nargin < 2
                val = 1;
            end
            obj.socket.sendmsg(sprintf('optogrid.sync = %d', val));
            try
                reply = obj.socket.waitformsg();
                if contains(reply, 'Sync Written')
                    success = 1;
                else
                    success = 0;
                end
            catch
                success = 0;
            end
        end

        function cleanup(obj)
            if ~isempty(obj.socket)
                obj.socket.socket.close();
            end
        end
    end
end