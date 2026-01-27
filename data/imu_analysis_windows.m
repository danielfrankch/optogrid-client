% Prompt user to select a Parquet file
[fileName, filePath] = uigetfile('*.parquet', 'Select a Parquet file');

% Check if user canceled
if isequal(fileName, 0)
    error('File selection canceled by user.');
end

% Full file path
fullFileName = fullfile(filePath, fileName);

% Read Parquet file into a table
T = parquetread(fullFileName);
T = sortrows(T,"sample");

%% Extract sessid from filename and query peh and prt
[~, baseFileName, ~] = fileparts(fileName);
filenameParts = split(baseFileName, '_');
if length(filenameParts) >= 2
    sessid = str2double(filenameParts{2});
else
    error('Cannot extract sessid from filename. Expected format: subjid_sessid_deviceid_...');
end
fprintf('Extracted sessid: %d\n', sessid);

dbc = db.labdb.getConnection('client');

% Stage = 'blocklr'; % or randomlr
SD = db.getSessData(sessid);

%% Extract key data from SD

data = struct2table(SD.data);
peh = struct2table(SD.peh);

df = [ ...
    data(:, {'n_done_trials', 'choice','hit','viol'}), ...
    peh(:, {'StartTime','States'}) ...
];

df = df(~cellfun('isempty', df.hit), :);


%% Extract the key epoch of a trial
df.settleIn   = zeros(height(df), 1);
df.cue_time   = zeros(height(df), 1);
df.choiceMade = zeros(height(df), 1);
for i = 1:height(df)
    States = df.States{i,1};
    df.settleIn(i) = States.settleIn(1); % settleIn time

    df.cue_time(i) = States.settleIn_Sound_opto(1); % cue time

    A = States.choiceMade_1(1);
    B = States.choiceMade_2(1);
    df.choiceMade(i) = min(A,B); % choiceMade time, which ever choice comes first, inclusive nan
end
% df.States = [];

%% QC of sync
close all
df.IMU_TTL_timestamp = zeros(height(df),1);
for n = 1:height(df)

    trial = df.n_done_trials(n);
    idx = find(T.sync==trial); % Locate the trial
    IMU = T(idx(1):idx(2),:);

    IMU_TTL_timestamp = IMU.sample(IMU.sync==2^16);
    df.IMU_TTL_timestamp(n) = double(IMU_TTL_timestamp(1))/100*(328/327.68);

end
df.Beh_TTL_timestamp = df.cue_time + df.StartTime - df.StartTime(1);
df.TTL_diff = df.IMU_TTL_timestamp - df.Beh_TTL_timestamp;
df.TTL_diff = df.TTL_diff - mean(df.TTL_diff);

hh = draw.jaxes;
hh.Position = [0.1, 0.2, 0.3, 0.4];
histogram(df.TTL_diff, 10)
xlabel('IMU sync timestamp - Beh sync timestamp (s)')
ylabel('Count')
title(sprintf('Session: %d',sessid))
xlim([-0.03,0.03])


ll = draw.jaxes;
ll.Position = [0.6, 0.2, 0.3, 0.4];
plot(df.n_done_trials,df.TTL_diff);
ylabel('IMU sync timestamp - Beh sync timestamp (s)')
xlabel('Trial number')
title('Delta Timeline')

%% Plot PSTH
close all
ax = draw.jaxes;
fig = ancestor(ax, 'figure');   % get parent figure
fig.Position = [100 100 700 500];  % [left bottom width height] in pixels
hold on

% Column indices in df
accCols  = 2:4;    % ACC X Y Z
gyroCols = 5:7;    % Gyro X Y Z
magCols  = 8:10;   % Mag X Y Z
rpyCols  = 12:14;  % Roll Pitch Yaw
dt = 1 / fs;

for n = 1:20% loop through all included trials
    trial = df.n_done_trials(n);
    idx = find(T.sync==trial); % Locate the trial
    IMU = T(idx(1):idx(2),:);

    % Unit conversion
    for j = accCols
        colName = IMU.Properties.VariableNames{j};
        IMU.(colName) = double(IMU{:,j});
        IMU{:,j} = double(IMU{:,j}).*(9.8*32/65536);
    end
    for j = gyroCols
        colName = IMU.Properties.VariableNames{j};
        IMU.(colName) = double(IMU{:,j});
        IMU{:,j} = double(IMU{:,j}).*(4000/65536);
    end
    
    groupCols = {accCols, gyroCols, magCols, rpyCols};
    Names = IMU.Properties.VariableNames([accCols gyroCols magCols rpyCols]);
    
    windowSize = 5;          % number of samples
    IMU_smooth = IMU;
    for j = [accCols,gyroCols]
        IMU_smooth(:,j) = table(movmean(table2array(IMU(:,j)), windowSize));
    end
    
    before_time = 1;
    after_time = 1;
    sync_sample = IMU_smooth.sample(find(IMU_smooth.sync == 2^16));
    sync_sample = sync_sample(1);
    poke_sample = sync_sample - round(fs*(df.cue_time(n) - df.choiceMade(n)));
    start_sample = (poke_sample - before_time*fs); % Starts on a bit before start poke
    end_sample =  poke_sample + after_time*fs;
    % end_sample =  sync_sample - round(fs*(df.cue_time(n) - df.choiceMade(n)))+after_time*fs; % Ends a bit after choice
    a = find(IMU_smooth.sample == start_sample);
    b = find(IMU_smooth.sample == end_sample);

    for col = 1:4          % 4 sensor groups
        for row = 1:3      % X Y Z (or Roll Pitch Yaw)
            subplot(3, 4, (row-1)*4 + col)

            if data.choice(trial) == "BotR"
                c = 'g';
            elseif data.choice(trial) == "TopR"
                c = 'r';
            else
                c = 'w';
            end
            
            Ports_char = data.choice{trial};

            this_IMU_smooth = IMU_smooth{:, groupCols{col}(row)};
            if col==4 
                N = height(this_IMU_smooth);
                % Convert yaw to radians
                theta = deg2rad(this_IMU_smooth);
                % Radius corresponds to time
                r = linspace(0, 1, N);         % normalised time (0 → 1)
                polarscatter(theta([1,end-10:end]), r([1,end-10:end]), 10,r([1,end-10:end]),'filled')
                % colormap(turbo)
                % cb = colorbar;
                % cb.Label.String = 'Normalized time';

            else
                plot(this_IMU_smooth(a:b),'Color',c)
                xline(fs*before_time,'LineWidth',2)
                xline((b-a)-fs*after_time,'LineWidth',2)
            end
            hold on
            if col == 1 && row == 3 %acc
                ylabel('m/s^2')
                xlabel('IMU Samples (100Hz fs)')
            elseif col == 2 && row == 3
                ylabel('Degree/s')
            elseif col == 4 && row == 3
                % ylabel('Degree')
            end
            title(Names((col-1)*3 + row))
            

        end
    end
end

sgtitle(sprintf('Trial: %d, DrawnPorts: %s',trial,Ports_char))


subplot(3,4,9);   % bottom-left subplot (row 3, col 1)

xLine = 100;      % x-position of vertical line
yl = ylim;

text(xLine, yl(2) + 0.05*range(yl), 'Choice', ...
    'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'bottom');

%%
% Plot line plot
close all
ax = draw.jaxes;
fig = ancestor(ax, 'figure');   % get parent figure
fig.Position = [100 100 700 500];  % [left bottom width height] in pixels


fs = 100;                         % sampling frequency (Hz)
N  = fs*10;                       % 10 seconds of sample
t  = (0:N-1) / fs;                % time vector (seconds)

% Column indices in df
accCols  = 2:4;    % ACC X Y Z
gyroCols = 5:7;    % Gyro X Y Z
magCols  = 8:10;   % Mag X Y Z
rpyCols  = 12:14;  % Roll Pitch Yaw


for i = 2:10
    IMU.Properties.VariableTypes(i) = "double";
end

% Unit conversion
for j = accCols
    IMU(:,j) = table(table2array(IMU(:,j).*(9.8*32/65536)));
end
for j = gyroCols
    IMU(:,j) = table(table2array(IMU(:,j).*(4000/65536)));
end

groupCols = {accCols, gyroCols, magCols, rpyCols};
Names = IMU.Properties.VariableNames([accCols gyroCols magCols rpyCols]);

windowSize = 10;          % number of samples
IMU_smooth = IMU;
for j = [accCols,gyroCols]
    IMU_smooth(:,j) = table(movmean(table2array(IMU(:,j)), windowSize));
end

for col = 1:4          % 4 sensor groups
    for row = 1:3      % X Y Z (or Roll Pitch Yaw)
        subplot(3, 4, (row-1)*4 + col)
        plot(t, IMU_smooth{:, groupCols{col}(row)})
        if col == 1 && row == 3 %acc
            ylabel('m/s^2')
            xlabel('Time (s)')
        elseif col == 2 && row == 3
            ylabel('Degree/s')
        elseif col == 4 && row == 3
            ylabel('Degree')
        end
        title(Names((col-1)*3 + row))
        xline(df.settleIn(n),'LineWidth',2)
        xline(df.cue_time(n),'LineWidth',2)
        xline(df.choiceMade(n),'LineWidth',2)
        xlim([0,df.choiceMade(n) + 1]) % 0- 2s after choiceMade
    end
end
Ports = data.drawnPorts(trial);
Ports_char = cell2mat(Ports{1});

sgtitle(sprintf('Trial: %d, Hit: %d, DrawnPorts: %s',trial,cell2mat(df.hit(n)),Ports_char))

IMU_trigger_time = find(IMU.sync==65536)*10-10;
peh_trigger_time = df.cue_time(n)*1000;
Timeline_difference = IMU_trigger_time - peh_trigger_time

%%

%% Plot 3D trajectory (from ACC)

fs = 100;                 % Hz
dt = 1/fs;
g = 9.81;
D = IMU_smooth(1:end,:);
N = height(D);

acc = [D.acc_x, ...
       D.acc_y, ...
       D.acc_z];

roll  = deg2rad(D.roll);
pitch = deg2rad(D.pitch);
yaw   = deg2rad(D.yaw);

pos = zeros(N,3);   % [x y z]
vel = zeros(N,3);   % [vx vy vz]

for k = 2:N
    % --- Rotation matrix: body → world ---
    cr = cos(roll(k));  sr = sin(roll(k));
    cp = cos(pitch(k)); sp = sin(pitch(k));
    cy = cos(yaw(k));   sy = sin(yaw(k));

    R = [ cy*cp,  cy*sp*sr - sy*cr,  cy*sp*cr + sy*sr;
          sy*cp,  sy*sp*sr + cy*cr,  sy*sp*cr - cy*sr;
          -sp,    cp*sr,             cp*cr           ];

    % --- Acceleration in world frame ---
    acc_world = (R * acc(k,:).').';

    % --- Remove gravity ---
    acc_world(3) = acc_world(3) - g;

    % --- Integrate ---
    vel(k,:) = vel(k-1,:) + acc_world * dt;
    pos(k,:) = pos(k-1,:) + vel(k,:) * dt;
end

t = linspace(0,4,N);

figure; hold on;
scatter3(pos(:,1), pos(:,2), pos(:,3), ...
         15, t, 'filled');
plot3(pos(:,1), pos(:,2), pos(:,3), 'k-', 'LineWidth', 0.5);

axis equal;
grid on;
view(3);

xlabel('X');
ylabel('Y');
zlabel('Z');
title('3D IMU Trajectory (orientation-aware)');

cb = colorbar;
cb.Label.String = 'Time progression';