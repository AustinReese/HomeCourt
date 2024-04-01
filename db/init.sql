DROP TABLE IF EXISTS nfl_selection;
DROP TABLE IF EXISTS clock_selection;
DROP TABLE IF EXISTS test_selection;
DROP TABLE IF EXISTS nba_selection;
DROP TABLE IF EXISTS display_option CASCADE;
DROP TABLE IF EXISTS display CASCADE;
-- DROP TABLE IF EXISTS temperature_report;
DROP TABLE IF EXISTS wiz_bulb;

CREATE TABLE IF NOT EXISTS display (
    displayKey TEXT PRIMARY KEY,
    displayName TEXT
);

INSERT INTO display (displayKey, displayName) VALUES ('off', 'Off');
INSERT INTO display (displayKey, displayName) VALUES ('nfl', 'NFL Scoreboard');
INSERT INTO display (displayKey, displayName) VALUES ('nba', 'NBA Scoreboard');
INSERT INTO display (displayKey, displayName) VALUES ('clock', 'Clock');
INSERT INTO display (displayKey, displayName) VALUES ('mnconn', 'MNConn Scoreboard');
INSERT INTO display (displayKey, displayName) VALUES ('test', 'Test');

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
    bulb_status BOOLEAN,
    ip TEXT,
    r INTEGER,
    g INTEGER,
    b INTEGER,
    brightness INTEGER
);

INSERT INTO wiz_bulb (bulb_name, bulb_status, ip, r, g, b, brightness) 
    VALUES ('Living Room 1', false, '192.168.0.236', 50, 50, 50, 50);

INSERT INTO wiz_bulb (bulb_name, bulb_status, ip, r, g, b, brightness) 
    VALUES ('Living Room 2', false, '192.168.0.51', 50, 50, 50, 50);