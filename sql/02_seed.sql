-- =============================================================================
-- 02_seed.sql — Sample employee data
--
-- Run this after 01_schema.sql to populate the table with test records.
-- Uses INSERT ... ON CONFLICT DO NOTHING so re-running is safe.
-- =============================================================================

INSERT INTO employee (name)
VALUES
    ('John Doe'),
    ('Jane Smith'),
    ('Michael Johnson')
ON CONFLICT DO NOTHING;
