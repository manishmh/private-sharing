-- One-time privileged setup for the LOCAL PostgreSQL database used by Vault.
-- Run as the postgres superuser, e.g.:
--     sudo -u postgres psql -f backend/setup_db.sql
--
-- Creates a dedicated 'vault' login role and a 'vault' database it owns.
-- Idempotent: safe to re-run.

DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vault') THEN
      CREATE ROLE vault WITH LOGIN PASSWORD 'vault';
   END IF;
END
$$;

SELECT 'CREATE DATABASE vault OWNER vault'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'vault')
\gexec

GRANT ALL PRIVILEGES ON DATABASE vault TO vault;
