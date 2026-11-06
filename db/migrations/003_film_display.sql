-- Adds the Silent Film display and its options.
--
-- init.sql only runs when a database is created from scratch, and the Pi's
-- postgres is long-lived, so changes have to be applied here too. Idempotent:
-- safe to re-run.
--
--   psql -U postgres -d postgres -f db/migrations/003_film_display.sql

BEGIN;

INSERT INTO display (displayKey, displayName, sortOrder) VALUES
    ('film', 'Silent Film', 35)
ON CONFLICT (displayKey) DO UPDATE
    SET displayName = EXCLUDED.displayName,
        sortOrder   = EXCLUDED.sortOrder;

-- Present already if 002 has run; repeated here so this migration stands alone.
ALTER TABLE display_option ADD COLUMN IF NOT EXISTS sortOrder INT;

INSERT INTO display_option (displayOptionKey, displayKey, displayOptionName, formType, sortOrder) VALUES
    ('film_speed',    'film', 'Projector Speed', 'dropdown', 10),
    ('film_tint',     'film', 'Tint',            'dropdown', 20),
    ('film_restored', 'film', 'Restored Print',  'checkbox', 30)
ON CONFLICT (displayOptionKey) DO UPDATE
    SET displayKey        = EXCLUDED.displayKey,
        displayOptionName = EXCLUDED.displayOptionName,
        formType          = EXCLUDED.formType,
        sortOrder         = EXCLUDED.sortOrder;

CREATE TABLE IF NOT EXISTS film_selection (
    id SERIAL PRIMARY KEY,
    displayOptionKey TEXT,
    selectionKey TEXT,
    selectionText TEXT,
    CONSTRAINT fk_configuration
        FOREIGN KEY(displayOptionKey)
        REFERENCES display_option(displayOptionKey)
);

-- Rewritten wholesale so re-running can't duplicate rows. The first row of
-- each option is what the UI selects by default.
DELETE FROM film_selection;
INSERT INTO film_selection (displayOptionKey, selectionKey, selectionText) VALUES
    ('film_speed', 'silent', 'Silent'),
    ('film_speed', 'crank',  'Hand-Cranked'),
    ('film_speed', 'talkie', 'Modern'),
    ('film_tint',  'sepia',  'Sepia'),
    ('film_tint',  'silver', 'Silver'),
    ('film_tint',  'night',  'Night');

COMMIT;
