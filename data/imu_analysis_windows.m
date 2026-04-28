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

PRT = dbc.query(['SELECT a.* FROM prt.aleaepi4ab_fm_view a ' ...
                'left join beh.sessview b on (a.sessid=b.sessid) ' ...
                'WHERE a.firstChoice IS NOT NULL ' ...
                'AND a.subjid NOT LIKE "%%-T-%%" ' ...
                'AND a.sessid = 102316 ' ...
                'AND a.trialtime >= "2026-01-28" ' ...
                'AND a.isopto = 1 ']);

subjid = SD.subjid;

%% Extract key data from SD

data = struct2table(SD.data);
peh = struct2table(SD.peh);

df = [ ...
    data(:, {'n_done_trials', 'choice','hit','viol'}), ...
    peh(:, {'StartTime','States'}) ...
];

% % Remove force trial
% df = df(~cellfun('isempty', df.hit), :);
df = df(~cellfun('isempty', df.choice), :);



%% Extract the key epoch of a trial
df.settleIn   = zeros(height(df), 1);
df.cue_time   = zeros(height(df), 1);
df.choiceMade = zeros(height(df), 1);
df.ITI_begin = zeros(height(df), 1);
for i = 1:height(df)
    States = df.States{i,1};
    df.settleIn(i) = States.settleIn(1); % settleIn time

    df.cue_time(i) = States.settleIn_Sound_opto(1); % cue time = opto sync time

    try
        A = States.choiceMade_1(1);
    catch 
        A = NaN;
    end
    try
        B = States.choiceMade_2(1);
    catch 
        B = NaN;
    end

    df.choiceMade(i) = min([A,B]); % choiceMade time, which ever choice comes first, inclusive nan

    df.ITI_begin(i) = States.ITI(1); % Take the time of entry to ITI state
end
% df.States = [];

% Temp remove settleIn-df.cue_time ~= 0.25s trials, these trial broke
% fixation?
% df = df((df.settleIn-df.cue_time)==-0.25,:);

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



%% Plot PSTH, when average across choice
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
fs = 100; %Hz
dt = 1 / fs;

average_imu_choice_1 = [];
average_imu_choice_2 = [];
count_choice_1 = 0;
count_choice_2 = 0;
relative_choice_sample_all = [];
relative_ITI_sample_all = [];
trial_id_chart = [];
imu_data_chart = [];
choice_bool_chart = [];

for n = 1:height(df)% loop through all included trials
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
    
    before_time = 0.25;
    after_time = 3;
    sync_sample = IMU_smooth.sample(find(IMU_smooth.sync == 2^16));
    sync_sample = sync_sample(1);
    poke_sample = sync_sample + round(fs*(df.choiceMade(n) - df.cue_time(n)));
    relative_choice_sample = round(fs*(df.choiceMade(n) - df.settleIn(n)));
    relative_choice_sample_all = [relative_choice_sample_all;relative_choice_sample];
    relative_ITI_sample = round(fs*(df.ITI_begin(n) - df.settleIn(n)));
    relative_ITI_sample_all = [relative_ITI_sample_all;relative_ITI_sample];

    start_sample = (sync_sample - before_time*fs); % Starts on a bit before start poke
    end_sample =  sync_sample + after_time*fs;
    % end_sample =  sync_sample - round(fs*(df.cue_time(n) - df.choiceMade(n)))+after_time*fs; % Ends a bit after choice
    a = find(IMU_smooth.sample == start_sample);
    b = find(IMU_smooth.sample == end_sample);
    
    
    IMU_smooth_tosave = IMU_smooth(a:b,:);
    unwrapped_yaw = unwrap(deg2rad(IMU_smooth_tosave.yaw)); %Unwrap yaw data in radian
    unwrapped_yaw = rad2deg(unwrapped_yaw);

    IMU_smooth_tosave.yaw =  unwrapped_yaw - unwrapped_yaw(1); %Align yaw to a fix starting point of 0

    unique_choices = unique(df.choice);

    if data.choice(trial) == string(unique_choices{1})
        try
            average_imu_choice_1 = [average_imu_choice_1;IMU_smooth_tosave];
        catch
            average_imu_choice_1 =IMU_smooth_tosave;      
        end
        count_choice_1 = count_choice_1 + 1;
        choice_bool_chart = [choice_bool_chart;0];
        
    elseif data.choice(trial) == string(unique_choices{2})
        try
            average_imu_choice_2 = [average_imu_choice_2;IMU_smooth_tosave];
        catch
            average_imu_choice_2 = IMU_smooth_tosave;
        end
        count_choice_2 = count_choice_2 + 1;
        choice_bool_chart = [choice_bool_chart;1];
    else
        
    end

    % Save it to a master matrix anyway
    trial_id_chart = [trial_id_chart;trial];
    try
        imu_data_chart = [imu_data_chart;IMU_smooth_tosave];
    catch
        imu_data_chart = IMU_smooth_tosave;
    end

end

for g = 1:2
    t = linspace(-before_time,after_time,height(average_imu_choice_1)/count_choice_1);
    for col = 1:4          % 4 sensor groups
        for row = 1:3      % X Y Z (or Roll Pitch Yaw)
            subplot(3, 4, (row-1)*4 + col)


            if g==1 
                this_IMU_smooth = average_imu_choice_1{:, groupCols{col}(row)};
                this_IMU_smooth = reshape(this_IMU_smooth,[height(average_imu_choice_1)/count_choice_1,count_choice_1]);
            
                c = 'r';
            elseif g==2
                this_IMU_smooth = average_imu_choice_2{:, groupCols{col}(row)};
                this_IMU_smooth = reshape(this_IMU_smooth,[height(average_imu_choice_2)/count_choice_2,count_choice_2]);
                c = 'g';
            end
            this_IMU_smooth = double(this_IMU_smooth);
            if col==5 % dummy 5, as it does not exit, let all plot line plot 
                N = height(this_IMU_smooth);
                % Convert yaw to radians
                theta = deg2rad(this_IMU_smooth);
                % Radius corresponds to time
                r = linspace(0, 1, N);         % normalised time (0 → 1)
                polarscatter(theta, r, 10,r,'filled')
                colormap(turbo)
                cb = colorbar;
                cb.Label.String = 'Normalized time';

            else
                hold on
                mu = mean(this_IMU_smooth, 2, 'omitnan');        % mean across trials
                sigma = std(this_IMU_smooth, 0, 2, 'omitnan');   % std across trials

                upper = mu + sigma;
                lower = mu - sigma;
                
                % shaded region
                fill([t'; flipud(t')], [upper; flipud(lower)], c, ...
                     'FaceAlpha', 0.2, 'EdgeColor', 'none'); 
                plot(t',mu,'Color',c,'LineWidth',2)
                xline(0,'LineWidth',1) % Mark poke time

                % mu = mean(relative_choice_sample_all/fs, 'omitnan');
                % sigma = std(relative_choice_sample_all/fs, 'omitnan');
                % xline(mu, 'k', 'LineWidth', 1);
                % yl = ylim;
                % fill([mu-sigma mu-sigma mu+sigma mu+sigma], [yl(1) yl(2) yl(2) yl(1)], ...
                %  [0.7 0.7 0.7], 'FaceAlpha', 0.3, 'EdgeColor', 'none');

                % xline(0.25,'LineWidth',0.1) % Mark cue time
                % xline(mean(relative_choice_sample_all)/fs,'LineWidth',0.1) % Mark choice at t relative to t=0
                % xline(mean(relative_ITI_sample_all)/fs,'LineWidth',0.1) % Mark entry of ITI
            end
            
            if col == 1 && row == 3 %acc
                ylabel('m/s^2')
                xlabel('Time (s)')
            elseif col == 2 && row == 3
                ylabel('Degree/s')
            elseif col == 4 && row == 3
                ylabel('Degree')
                xlabel('Time (s)')
                legend("",string(unique_choices{1}),"","","","",string(unique_choices{2}))
            end
            title(Names((col-1)*3 + row))
            

        end
    end
end

sgtitle(sprintf("Choice trajectory (n %s=%d vs. n %s=%d), %s, %d",string(unique_choices{1}),count_choice_1,string(unique_choices{2}),count_choice_2,subjid,sessid))


subplot(3,4,9);   % bottom-left subplot (row 3, col 1)

% Mark event line 1
xLine = 0;      % x-position of vertical line
yl = ylim;
text(xLine, yl(2) + 0.05*range(yl), 'Cue', ...
    'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'bottom');

% Mark event line 2
xLine = mean(relative_choice_sample_all);      % x-position of vertical line
yl = ylim;
text(xLine, yl(2) + 0.05*range(yl), 'Choice', ...
    'HorizontalAlignment', 'right', ...
    'VerticalAlignment', 'bottom');

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
fs = 100; %Hz
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
    
    before_time = 0.5;
    after_time = 1;
    sync_sample = IMU_smooth.sample(find(IMU_smooth.sync == 2^16));
    sync_sample = sync_sample(1);
    poke_sample = sync_sample - round(fs*(df.cue_time(n) - df.cue_time(n)));
    start_sample = (poke_sample - before_time*fs); % Starts on a bit before start poke
    end_sample =  poke_sample + after_time*fs;
    % end_sample =  sync_sample - round(fs*(df.cue_time(n) - df.choiceMade(n)))+after_time*fs; % Ends a bit after choice
    a = find(IMU_smooth.sample == start_sample);
    b = find(IMU_smooth.sample == end_sample);

    t = linspace(-before_time,after_time,fs*(before_time+after_time)+1);
    for col = 1:2          % 4 sensor groups
        for row = 1:3      % X Y Z (or Roll Pitch Yaw)
            subplot(3, 4, (row-1)*4 + col)

            if data.choice(trial) == "BotL"
                c = 'g';
            elseif data.choice(trial) == "TopL"
                c = 'r';
            else
                c = 'b';
            end
            
            % Parse by opto trial types
            % opto = unique(PRT.led_selection);
            % nO   = numel(opto);
            % cmap = ["k","b","r","m","g","c"];   % or parula, turbo, hsv, etc.
            % idxx = find(string(opto) == string(PRT.led_selection(PRT.trialnum==trial)));
            % c   = cmap(idxx); 

            Ports_char = data.choice{trial};

            this_IMU_smooth = IMU_smooth{:, groupCols{col}(row)};
            if col==4 
                N = height(this_IMU_smooth);
                % Convert yaw to radians
                theta = deg2rad(this_IMU_smooth);
                % Radius corresponds to time
                r = linspace(0, 1, N);         % normalised time (0 → 1)
                polarscatter(theta, r, 10,r,'filled')
                colormap(turbo)
                cb = colorbar;
                cb.Label.String = 'Normalized time';

            else
                plot(t',this_IMU_smooth(a:b),'Color',c)
                xline(0,'LineWidth',2)
            end
            hold on
            if col == 1 && row == 3 %acc
                ylabel('m/s^2')
                xlabel('Time (s)')
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

%% Sensor fusion clustering
Unlabeled_trajectory = imu_data_chart{:, groupCols{1}(3)}; % Extract pitch
Unlabeled_trajectory = double(reshape(Unlabeled_trajectory,[height(imu_data_chart)/height(trial_id_chart),height(trial_id_chart)]));
Unlabeled_trajectory = Unlabeled_trajectory(1:500,:);


% % 1. Compute pairwise distances between trials (using correlation distance)
D = pdist(Unlabeled_trajectory', 'correlation'); % transpose: each trial is a row

% 2. Perform hierarchical clustering
Z = linkage(D, 'average'); % 'average' or 'ward' linkage

% 3. Assign trials to 2 clusters
groups = cluster(Z, 'maxclust', 2); % groups: [50 x 1], values 1 or 2

% 2. Cluster using k-means (k=2), stochastic
% X = Unlabeled_trajectory;
% groups = kmeans(X', 2, 'Distance', 'correlation', 'Replicates', 10); % transpose: trials as rows

mean(groups==choice_bool_chart+1)

%% Cluster trajectory to see what aspect of trial separates the trajectory the best
optimal_groups_all = [];

for i = 1:4
    for j = 1:3
    Unlabeled_trajectory = imu_data_chart{:, groupCols{i}(j)}; % Extract pitch
    Unlabeled_trajectory = double(reshape(Unlabeled_trajectory,[height(imu_data_chart)/height(trial_id_chart),height(trial_id_chart)]));
    Unlabeled_trajectory = Unlabeled_trajectory(1:200,:);
    
    % % 1. Compute pairwise distances between trials (using correlation distance)
    D = pdist(Unlabeled_trajectory', 'correlation'); % transpose: each trial is a row
    
    % 2. Perform hierarchical clustering
    Z = linkage(D, 'average'); % 'average' or 'ward' linkage
    
    % 3. Assign trials to 2 clusters
    groups = cluster(Z, 'maxclust', 2); % groups: [50 x 1], values 1 or 2
    
    % 2. Cluster using k-means (k=2), stochastic
    % X = Unlabeled_trajectory;
    % groups = kmeans(X', 2, 'Distance', 'correlation', 'Replicates', 10); % transpose: trials as rows
    
    optimal_groups_all = [optimal_groups_all,groups];
    end
end

optimal_groups_all = [optimal_groups_all,choice_bool_chart+1];

% Plot cross sensor comparison of grouping
% optimal_groups_all: [nTrial x nSensor], each col = sensor, values 1 or 2

nSensor = size(optimal_groups_all, 2);
agreement_matrix = zeros(nSensor);

for i = 1:nSensor
    for j = 1:nSensor
        % Compute fraction of trials where group assignments agree
        agreement_matrix(i,j) = mean(optimal_groups_all(:,i) == optimal_groups_all(:,j));
    end
end

% Display as heatmap
sensor_labels = {'ACC_X','ACC_Y','ACC_Z', ...
                 'GYRO_X','GYRO_Y','GYRO_Z', ...
                 'MAG_X','MAG_Y','MAG_Z', ...
                 'Roll','Pitch','Yaw','Choice'};

figure;
imagesc(agreement_matrix);
colormap(cmap); % Use your custom diverging colormap
colorbar;
xlabel('Sensor'); ylabel('Sensor');
title('Sensor Group Agreement (0.5 = neutral)');
caxis([0 1]);

set(gca, 'XTick', 1:nSensor, 'XTickLabel', sensor_labels, ...
         'YTick', 1:nSensor, 'YTickLabel', sensor_labels, ...
         'TickLabelInterpreter', 'none', 'XTickLabelRotation', 45);

% Optionally, adjust font size for readability
set(gca, 'FontSize', 12);


%% 4. Plot mean ± std for each group
t = (1:size(Unlabeled_trajectory,1))'; % time vector

figure;
for k = 1:length(groups)
    if k == 1
        c = 'r';
    elseif k == 2 
        c = 'b';
    end
    idx = (groups == k);
    mu = mean(Unlabeled_trajectory(:,idx), 2, 'omitnan');
    sigma = std(Unlabeled_trajectory(:,idx), 0, 2, 'omitnan');
    fill([t; flipud(t)], [mu+sigma; flipud(mu-sigma)], c, 'EdgeColor','none','FaceAlpha',0.3);
    hold on;
    plot(t, mu, c, 'LineWidth', 2);
    xlabel('Sample'); ylabel('Pitch');
    grid on;
end
sgtitle('Pitch Clusters (Mean ± Std)');

% Join it to session data table
trial_cluster_table = [trial_id_chart,groups];
trial_cluster_table = array2table(trial_cluster_table, ...
    'VariableNames', {'n_done_trials', 'group'});

clustered_data = join(trial_cluster_table, data, 'Keys', 'n_done_trials');
CC = sortrows(clustered_data,'group');

% Compute chi-square for 'choice' column only
catvals = categorical(CC.choice);
[~, chi2stat] = crosstab(catvals, CC.group);

disp(['Chi-square for ''choice'': ', num2str(chi2stat)]);

%% Stats analysis on whether choice can separate trajectory
% Unlabeled_trajectory: nSamples x nTrials
% choice_bool_chart: nTrials x 1

tStat_separation = [];
for i = 1:4
    for j = 1:3
        Unlabeled_trajectory = imu_data_chart{:, groupCols{i}(j)}; % Extract pitch
        Unlabeled_trajectory = double(reshape(Unlabeled_trajectory,[height(imu_data_chart)/height(trial_id_chart),height(trial_id_chart)]));
        Unlabeled_trajectory = Unlabeled_trajectory(1:200,:);
        
        Label = choice_bool_chart;
        U_Label = unique(Label);
        
        group0 = Unlabeled_trajectory(:, Label == U_Label(1));
        group1 = Unlabeled_trajectory(:, Label == U_Label(2));
        
        
        mean0 = mean(group0, 2, 'omitnan');
        mean1 = mean(group1, 2, 'omitnan');
        
        t = (1:size(Unlabeled_trajectory,1))';
        % close all
        % figure;
        % hold on
        % fill([t; flipud(t)], [mean0+std(group0,0,2); flipud(mean0-std(group0,0,2))], 'r', 'FaceAlpha',0.2, 'EdgeColor','none'); 
        % plot(t, mean0, 'r', 'LineWidth', 2);
        % 
        % fill([t; flipud(t)], [mean1+std(group1,0,2); flipud(mean1-std(group1,0,2))], 'b', 'FaceAlpha',0.2, 'EdgeColor','none');
        % plot(t, mean1, 'b', 'LineWidth', 2);
        % 
        % legend('0: std','0: mean','1: std','1: mean');
        % xlabel('Sample'); ylabel('Trajectory');
        % title('Mean ± Std Trajectory by Choice');
        % grid on;
        
        avg_traj = mean(Unlabeled_trajectory, 1, 'omitnan'); % 1 x nTrials
        g0 = avg_traj(Label == U_Label(1));
        g1 = avg_traj(Label == U_Label(2));
        
        [~, p] = ttest2(g0, g1);
        tStat_separation = [tStat_separation;p];
    end
end
disp(['p-value for difference in mean trajectory: ', num2str(p)]);