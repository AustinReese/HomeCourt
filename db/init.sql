DROP TABLE IF EXISTS nfl_selection;
DROP TABLE IF EXISTS snake_selection;
DROP TABLE IF EXISTS clock_selection;
DROP TABLE IF EXISTS test_selection;
DROP TABLE IF EXISTS nba_selection;
DROP TABLE IF EXISTS display_option CASCADE;
DROP TABLE IF EXISTS display CASCADE;
-- DROP TABLE IF EXISTS temperature_report;
DROP TABLE IF EXISTS wiz_bulb;

-- sortOrder drives the order of the tiles in the UI. 'off' is not a tile:
-- the UI has a power switch instead, and still sends display 'off' for it.
CREATE TABLE IF NOT EXISTS display (
    displayKey TEXT PRIMARY KEY,
    displayName TEXT,
    sortOrder INT
);

INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('off', 'Off', 0);
INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('nfl', 'NFL Scoreboard', 10);
INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('nba', 'NBA Scoreboard', 20);
INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('snake', 'Snakes', 30);
INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('clock', 'Clock', 40);
INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('mnconn', 'MNConn Scoreboard', 50);
INSERT INTO display (displayKey, displayName, sortOrder) VALUES ('test', 'Test', 60);

CREATE TABLE IF NOT EXISTS display_option (
    displayOptionKey TEXT PRIMARY KEY,
    displayKey TEXT,
    displayOptionName TEXT,
    formType TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayKey)
        REFERENCES display(displayKey)
);

INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('nfl_live_updates', 'nfl', 'Enable Live Updates', 'checkbox');
INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('nba_live_updates', 'nba', 'Enable Live Updates', 'checkbox');
INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('clock_hour_format', 'clock', 'Hour Format', 'dropdown');
INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('test_script', 'test', 'Script to Test', 'dropdown');
INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('snake_count', 'snake', 'Snakes', 'dropdown');
INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('snake_speed', 'snake', 'Speed', 'dropdown');
INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) 
    VALUES ('snake_trails', 'snake', 'Motion Trails', 'checkbox');

CREATE TABLE IF NOT EXISTS clock_selection (
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

INSERT INTO clock_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('clock_hour_format', '12hr', '12 Hour');
INSERT INTO clock_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('clock_hour_format', '24hr', '24 Hour');

CREATE TABLE IF NOT EXISTS nfl_selection(
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

CREATE TABLE IF NOT EXISTS nba_selection(
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

CREATE TABLE IF NOT EXISTS test_selection (
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

INSERT INTO test_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('test_script', 'rotating_box', 'Rotating Box');
INSERT INTO test_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('test_script', 'pulsing_colors', 'Pulsing Colors');

CREATE TABLE IF NOT EXISTS snake_selection (
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('snake_count', 'few', 'Few');
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('snake_count', 'some', 'Some');
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('snake_count', 'many', 'Many');
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('snake_speed', 'slow', 'Slow');
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('snake_speed', 'medium', 'Medium');
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) 
    VALUES ('snake_speed', 'fast', 'Fast');

CREATE TABLE IF NOT EXISTS temperature_report (
    id SERIAL PRIMARY KEY,
    deviceName TEXT,
    humidity FLOAT,
    dhtTemp FLOAT,
    dsTemp FLOAT,
    vcc FLOAT,
    reportTimestamp timestamp 
);

CREATE TABLE IF NOT EXISTS wiz_bulb (
    id SERIAL PRIMARY KEY,
    bulb_name TEXT,
    ip TEXT,
    is_enabled BOOLEAN
);

INSERT INTO wiz_bulb (bulb_name, ip, is_enabled) 
    VALUES ('Basement', '192.168.0.236', true);

INSERT INTO wiz_bulb (bulb_name, ip, is_enabled) 
    VALUES ('Unused', '192.168.0.51', false);

INSERT INTO wiz_bulb (bulb_name, ip, is_enabled) 
    VALUES ('Living Room Primary', '192.168.0.43', true);

INSERT INTO wiz_bulb (bulb_name, ip, is_enabled) 
    VALUES ('Living Room Secondary', '192.168.0.47', true);
