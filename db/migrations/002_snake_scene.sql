-- Adds the Snakes "Scene" option (desert / neon) and an explicit order for
-- display options, which until now came out alphabetically by key.
--
-- Idempotent: safe to re-run.
--   psql -U postgres -d postgres -f db/migrations/002_snake_scene.sql

BEGIN;

ALTER TABLE display_option ADD COLUMN IF NOT EXISTS sortOrder INT;

INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType, sortOrder) VALUES
    ('snake_scene',  'snake', 'Scene',  'dropdown', 10),
    ('snake_count',  'snake', 'Snakes', 'dropdown', 20),
    ('snake_speed',  'snake', 'Speed',  'dropdown', 30),
    ('snake_trails', 'snake', 'Trails', 'checkbox', 40)
ON CONFLICT (displayOptionKey) DO UPDATE
    SET displayKey        = EXCLUDED.displayKey,
        displayOptionName = EXCLUDED.displayOptionName,
        formType          = EXCLUDED.formType,
        sortOrder         = EXCLUDED.sortOrder;

UPDATE display_option SET sortOrder = 10
    WHERE sortOrder IS NULL;

-- Rewritten wholesale so re-running can't duplicate rows. Desert is first,
-- which is what the UI preselects.
DELETE FROM snake_selection;
INSERT INTO snake_selection (displayOptionKey, selectionKey, selectionText) VALUES
    ('snake_scene', 'desert', 'Desert'),
    ('snake_scene', 'neon',   'Neon'),
    ('snake_count', 'few',    'Few'),
    ('snake_count', 'some',   'Some'),
    ('snake_count', 'many',   'Many'),
    ('snake_speed', 'slow',   'Slow'),
    ('snake_speed', 'medium', 'Medium'),
    ('snake_speed', 'fast',   'Fast');

COMMIT;
