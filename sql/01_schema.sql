-- =============================================================================
-- 01_schema.sql — Employee table schema
--
-- Run this once against your RDS PostgreSQL instance to create the table.
-- Compatible with PostgreSQL 12+.
-- =============================================================================

CREATE TABLE IF NOT EXISTS employee (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
