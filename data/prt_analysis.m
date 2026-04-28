%% Query data
clear; clc;
dbc = db.labdb.getConnection();

% Opto experiments starts on 2025-07-16
df = dbc.query(['SELECT a.* FROM prt.aleaepi4ab_fm_view a ' ...
                'left join beh.sessview b on (a.sessid=b.sessid) ' ...
                'WHERE a.firstChoice IS NOT NULL ' ...
                'AND a.subjid NOT LIKE "%%-T-%%" ' ...
                'AND a.trialtime >= "2026-02-19" ' ...
                'AND a.isopto = 1 ']);

% Take valid trials only
df = df(~isnan(df.hit),:);
%%
subjids = unique(df.subjid);
close all
figure
colors = lines(height(subjids));   % 6 distinct colours

% Plot continuity of stimulation
subplot(2,2,1)
for i = 1:height(subjids)
    dff = df(string(df.subjid)==subjids(i),:);
    
    dff = sortrows(dff,'trialnum');
    
    plot(dff.trialnum,str2double(dff.last_stim_time_ms)/1000,'LineWidth',2,'Color',colors(i,:));
    hold on
end
title('Optogrid Stimulation Time')
xlabel('Trial Count')
ylabel('Last Stim Time (s)')

% Plot time accuracy
subplot(2,2,2)
for i = 1:height(subjids)
    dff = df(string(df.subjid)==subjids(i),:);
    
    dff = sortrows(dff,'trialnum');
    sessid = dff.sessid(1);
    peh_dff = get_session_state_timestamps(sessid,'settleIn_Sound_opto');
    
    scale_factor = (32/32.768); %Rounding of RTC counter
    optogrid_stim_time = (scale_factor)*str2double(dff.last_stim_time_ms); %ms
    
    peh_stim_time = 1000*peh_dff{:,2}; %ms

    Delta_time = optogrid_stim_time - peh_stim_time;
    plot(dff.trialnum,Delta_time-Delta_time(1),'LineWidth',2,'Color',colors(i,:));
    hold on
end
title('Optogrid Time Accuracy')
xlabel('Trial Count')
ylabel('Delta Time (ms)')

%% Plot battery 
subplot(2,2,3)
for i = 1:height(subjids)
    dff = df(string(df.subjid)==subjids(i),:);
    
    dff = sortrows(dff,'trialnum');
    
    plot(dff.trialnum,str2double(dff.battery_mv)/1000,'LineWidth',1.5,'Color',colors(i,:));
    hold on
end
title('Optogrid Battery')
xlabel('Trial Count')
ylabel('Battery Voltage (V)')
ylim([3.5,4.2])

%% Plot uLED_check
subplot(2,2,4)

checks = df.uLED_check;
subjids = df.subjid;  % table column of subject IDs

% Get unique uLED_check values and their counts
[uChecks, ~, idx] = unique(checks);
counts = accumarray(idx, 1);

% Sort by count (largest → smallest)
[countsSorted, sortIdx] = sort(counts, 'descend');
uChecksSorted = uChecks(sortIdx);

% Convert all strings to Python integers (BigInt equivalent)
pyInts = cellfun(@(s) py.int(s), uChecksSorted, 'UniformOutput', false);

% Count number of 1 bits for each
nLEDsWorking = cellfun(@(x) double(int32(py.bin(x).count('1'))), pyInts);

% Plot bar chart
bar(countsSorted)
xlabel('Number of working uLEDs')
ylabel('Number of cases')
title('uLED check distributions')

% Custom x-ticks: number of working LEDs
xticks(1:numel(nLEDsWorking))
xticklabels(string(nLEDsWorking))
xtickangle(45)

% --- Add text annotation for each bar ---
hold on

for i = 1:numel(uChecksSorted)
    % Find indices in df that match this uLED_check value
    mask = strcmp(checks, uChecksSorted(i));
    
    % Get the corresponding subject IDs
    subj_list = subjids(mask);
    
    % Get unique
    unique_subj_list = unique(subj_list);

    % Convert to comma-separated string (truncate if too long)
    txt = strjoin(string(unique_subj_list), '\n ');
    % if strlength(txt) > 50
    %     txt = extractBefore(txt, 50) + "...";  % truncate for readability
    % end
    
    % Place text above the bar
    text(i, countsSorted(i)-60, txt, 'HorizontalAlignment', 'center', ...
        'VerticalAlignment', 'middle', 'FontSize', 12)
end

hold off

%% Analysis on one animal
dff = df(string(df.subjid)=="COS-M-0164", :);
% dff = dff( ...
%     datetime(dff.trialtime,'InputFormat','yyyy-MM-dd HH:mm:ss.SSSS') ...
%     < datetime(2026,3,27), :);
%
values = dff.led_selection;
hitVals = dff.hit;

[uniqueVals, ~, idx] = unique(values);

% Count occurrences
counts = accumarray(idx, 1);

% Mean of hit per group
meanHit = accumarray(idx, hitVals, [], @mean);

% Combine into table
result = table(uniqueVals, counts, meanHit)

% Psychometric plot

% Compute difference variable
dff.dEV = dff.Aev - dff.Cev;

% Logical for TopL choice
dff.choose_lottery = string(dff.firstChoice) == "BotL";

% Plot Psycho curve
c = ["k","b","r","m","b","r"];

XPos = [0.1,0.1,0.4,0.6,0.7];
YPos = [0.1,0.6,0.1,0.6,0.1];
Opto = ["Sham","V1","RSC","M2","S1","mPFC"];
for i = 2:6
    ax = draw.jaxes;
    ax.Position = [XPos(i-1) YPos(i-1) 0.2 0.25];
    hold on
    inc = string(dff.led_selection) == uniqueVals{1};
    % [bx,by,be] = stats.binned(round(dff.dEV(inc)), dff.choose_lottery(inc),'n_bins',4);
    [bx,by,be] = stats.binned(round(dff.dEV(inc)), dff.choose_lottery(inc),'bin_e',[unique(round(dff.dEV(inc)))-0.5;max(unique(round(dff.dEV(inc))))+0.5]);
    bx = unique(round(dff.dEV(inc)));
    draw.errorplot(ax,bx,by,be,'Color',c(1));
    inc = string(dff.led_selection) == uniqueVals{i};
    % [bx,by,be] = stats.binned(round(dff.dEV(inc)), dff.choose_lottery(inc),'n_bins',4);
    [bx,by,be] = stats.binned(round(dff.dEV(inc)), dff.choose_lottery(inc),'bin_e',[unique(round(dff.dEV(inc)))-0.5;max(unique(round(dff.dEV(inc))))+0.5]);
    bx = unique(round(dff.dEV(inc)));
    draw.errorplot(ax,bx,by,be,'Color',c(i));
    yline(0.5,'--')
    % ax.YLim= [-0.2,1.2];
    % ax.XLim = [-1,4];
    ax.XTick = unique(round(dff.dEV(inc)));
    xlabel('delta EV');
    ylabel('P(Lottery)');
    title(uniqueVals{i})
    lgd = legend("","Sham","",Opto(i));
    lgd.Position(2) = lgd.Position(2) + 0.15;  % move upward

end
sgtitle('COS-M-0164, Optogrid Results')
grid on;
hold off;