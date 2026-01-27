function Return = get_session_state_timestamps(sessid,theState)

    % Query session data from db
    dbc = db.labdb.getConnection('client');
    SD = db.getSessData(sessid);

    % Extract peh, keep only attempted trials
    data = struct2table(SD.data);
    peh = struct2table(SD.peh);
    df = [ ...
        data(:, {'n_done_trials','hit','viol'}), ...
        peh(:, {'StartTime','States'}) ...
    ];
    df = df(~cellfun('isempty', df.hit), :);

    % Extract theState's trial-wise times
    df.(theState)   = zeros(height(df), 1);
    for i = 1:height(df)
        States = df.States{i,1};
        df.(theState)(i) = States.(theState)(1); % State's trial-wise time
    end
    
    % Zero it to the first StartTime
    df.(theState) = df.(theState) + df.StartTime - df.StartTime(1);

    % Return n_done_trials, and theState's Time
    Return = df(:, ["n_done_trials", theState]);

end