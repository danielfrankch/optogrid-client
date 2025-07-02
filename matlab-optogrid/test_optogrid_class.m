% filepath: /Users/danielmac/repos/OptoGrid/Python Client/matlab-optogrid/test_optogrid_class.m
% Test script for optogrid class
clear;clc;
%% Test 0: Create and start OptoGrid object
og = optogrid();
og.start();

%% Test 1: Connect to OptoGrid
result = og.connect();
if result
    disp('Connect: Success');
else
    disp('Connect: Failed');
end

%% Test 2: Enable IMU
result = og.enableIMU();
if result
    disp('Enable IMU: Success');
else
    disp('Enable IMU: Failed');
end

%% Test 3: Sync
result = og.sync(3);
if result
    disp('Sync: Success');
else
    disp('Sync: Failed');
end

%% Test 4: Program OptoGrid
result = og.program();
if result
    disp('Program: Success');
else
    disp('Program: Failed');
end

%% Test 5: Trigger OptoGrid
result = og.trigger();
if result
    disp('Trigger: Success');
else
    disp('Trigger: Failed');
end

%% Test 6: Disable IMU
result = og.disableIMU();
if result
    disp('Disable IMU: Success');
else
    disp('Disable IMU: Failed');
end

%% Cleanup
og.cleanup();
disp('Test complete!');