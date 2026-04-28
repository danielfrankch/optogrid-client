clc; clear; close all;

%% 1. Generate true signal (ground truth)
n = 100;                     % number of time steps
t = 1:n;
x_true = sin(0.1 * t);       % smooth underlying signal

%% 2. Add measurement noise
noise_std = 0.3;
z = x_true + noise_std * randn(1, n);   % noisy observations

%% 3. Kalman Filter initialization

% State model: x_k = x_{k-1} + w_k  (constant model)
A = 1;       % state transition
H = 1;       % observation model

Q = 0.01;    % process noise covariance (model uncertainty)
R = noise_std^2;  % measurement noise covariance

x_est = zeros(1, n);   % estimated state
P = 1;                 % initial estimate covariance

x_est(1) = z(1);       % initialize with first measurement

%% 4. Kalman Filter loop
for k = 2:n
    
    % ---- Prediction ----
    x_pred = A * x_est(k-1);
    P_pred = A * P * A' + Q;
    
    % ---- Kalman Gain ----
    K = P_pred * H' / (H * P_pred * H' + R);
    
    % ---- Update ----
    x_est(k) = x_pred + K * (z(k) - H * x_pred);
    P = (1 - K * H) * P_pred;
end

%% 5. Plot results
figure;
plot(t, x_true, 'g-', 'LineWidth', 2); hold on;
plot(t, z, 'r.', 'MarkerSize', 10);
plot(t, x_est, 'b-', 'LineWidth', 2);

legend('True Signal', 'Noisy Measurement', 'Kalman Estimate');
xlabel('Time');
ylabel('Signal');
title('Kalman Filter Noise Reduction');
grid on;

%% 6. Optional: error comparison
figure;
plot(t, abs(z - x_true), 'r'); hold on;
plot(t, abs(x_est - x_true), 'b');
legend('Measurement Error', 'Kalman Error');
title('Error Reduction');
xlabel('Time');
ylabel('Absolute Error');
grid on;