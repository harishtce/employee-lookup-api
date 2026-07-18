-- =============================================================================
-- 03_queries.sql — Reference SQL queries used by the Lambda function
--
-- These are the exact parameterized statements executed at runtime.
-- $1 placeholders shown here are the psql notation; the Python driver uses %s.
-- =============================================================================

-- GET /employees — list all employees (capped to 10 001 rows to detect truncation)
SELECT id, name
FROM   employee
ORDER  BY id
LIMIT  10001;

-- GET /employees/{id} — fetch a single employee by primary key
-- Parameter: $1 = employee id (positive integer)
SELECT id, name
FROM   employee
WHERE  id = $1;
