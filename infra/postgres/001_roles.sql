-- Executed once by the PostgreSQL operator role when initializing a fresh volume.
-- Password values are quoted by psql, not interpolated into SQL by a shell.
\getenv app_password APP_DB_PASSWORD
\getenv migration_password MIGRATION_DB_PASSWORD
\getenv queue_password QUEUE_DB_PASSWORD

CREATE ROLE atlas_migrator LOGIN PASSWORD :'migration_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE atlas_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
CREATE ROLE atlas_queue LOGIN PASSWORD :'queue_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO atlas_migrator, atlas_app, atlas_queue', current_database()) \gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO atlas_migrator;
GRANT USAGE ON SCHEMA public TO atlas_app, atlas_queue;
CREATE EXTENSION IF NOT EXISTS vector;
