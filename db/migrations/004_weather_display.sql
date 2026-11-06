-- Adds the Weather display and its options.
--
-- init.sql only runs when a database is created from scratch, and the Pi's
-- postgres is long-lived, so changes have to be applied here too. Idempotent:
-- safe to re-run.
--
--   psql -U postgres -d postgres -f db/migrations/004_weather_display.sql

BEGIN;

INSERT INTO display (displayKey, displayName, sortOrder) VALUES
    ('weather', 'Weather', 25)
ON CONFLICT (displayKey) DO UPDATE
    SET displayName = EXCLUDED.displayName,
        sortOrder   = EXCLUDED.sortOrder;

INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType, sortOrder) VALUES
    ('weather_units',   'weather', 'Units',   'dropdown', 10),
    ('weather_outlook', 'weather', 'Outlook', 'dropdown', 20)
ON CONFLICT (displayOptionKey) DO UPDATE
    SET displayKey        = EXCLUDED.displayKey,
        displayOptionName = EXCLUDED.displayOptionName,
        formType          = EXCLUDED.formType,
        sortOrder         = EXCLUDED.sortOrder;

CREATE TABLE IF NOT EXISTS weather_selection (
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

-- Rewritten wholesale so re-running cannot duplicate rows. The first row of
-- each option is what the UI selects by default.
DELETE FROM weather_selection;
INSERT INTO weather_selection (displayOptionKey, selectionKey, selectionText) VALUES
    ('weather_units',   'fahrenheit', 'Fahrenheit'),
    ('weather_units',   'celsius',    'Celsius'),
    ('weather_outlook', 'days',       '5 Days'),
    ('weather_outlook', 'hourly',     'Hourly');

COMMIT;
