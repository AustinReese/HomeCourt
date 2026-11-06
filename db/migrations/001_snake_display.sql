-- Adds the Snakes display and the sortOrder column that the UI tiles use.
--
-- init.sql only runs when a database is created from scratch, and the Pi's
-- postgres is long-lived, so changes have to be applied here too. Idempotent:
-- safe to re-run.
--
--   psql -U postgres -d postgres -f db/migrations/001_snake_display.sql

BEGIN;

ALTER TABLE display ADD COLUMN IF NOT EXISTS sortOrder INT;

INSERT INTO display (displayKey, displayName, sortOrder) VALUES
    ('off',    'Off',               0),
    ('nfl',    'NFL Scoreboard',   10),
    ('nba',    'NBA Scoreboard',   20),
    ('snake',  'Snakes',           30),
    ('clock',  'Clock',            40),
    ('mnconn', 'MNConn Scoreboard', 50),
    ('test',   'Test',             60)
ON CONFLICT (displayKey) DO UPDATE
    SET displayName = EXCLUDED.displayName,
        sortOrder   = EXCLUDED.sortOrder;

INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType) VALUES
    ('snake_count',  'snake', 'Snakes',        'dropdown'),
    ('snake_speed',  'snake', 'Speed',         'dropdown'),
    ('snake_trails', 'snake', 'Motion Trails', 'checkbox')
ON CONFLICT (displayOptionKey) DO UPDATE
    SET displayKey        = EXCLUDED.displayKey,
        displayOptionName = EXCLUDED.displayOptionName,
        formType          = EXCLUDED.formType;

CREATE TABLE IF NOT EXISTS snake_selection (
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

-- Rewritten wholesale so re-running can't duplicate rows.
DELETE FROM snake_selection;
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) VALUES
    ('snake_count', 'few',    'Few'),
    ('snake_count', 'some',   'Some'),
    ('snake_count', 'many',   'Many'),
    ('snake_speed', 'slow',   'Slow'),
    ('snake_speed', 'medium', 'Medium'),
    ('snake_speed', 'fast',   'Fast');

COMMIT;
