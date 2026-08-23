-- Least-privilege database roles (control C-18, threats T-02 / T-21 / T-24).
--
-- Roles are cluster-level objects, so they are provisioned by an administrator rather
-- than by an application migration. Run this once per cluster, before the first
-- `alembic upgrade`.
--
-- Three roles with genuinely different jobs:
--
--   adai_migrator  owns the schema and is the ONLY role with DDL. Used by alembic.
--   adai_app       the API. DML only, no DDL, and SUBJECT to row level security.
--   adai_worker    background pipeline. DML plus BYPASSRLS, because it legitimately
--                  processes documents belonging to every user and has no user-facing
--                  input path for an IDOR to arrive through. RLS exists to contain
--                  mistakes in request handling; the worker has no request handling.
--   adai_auth      pre-authentication credential lookup ONLY. Login must find a user by
--                  email before any identity exists, so it cannot satisfy an RLS
--                  predicate. This role has SELECT on `users` and nothing else -- no
--                  other table, no INSERT, no UPDATE, no DELETE.
--
-- No role is a superuser. No role may create databases or roles.

\set ON_ERROR_STOP on

-- Replace these before running. Never commit real passwords.
\set migrator_password 'CHANGE_ME_MIGRATOR'
\set app_password      'CHANGE_ME_APP'
\set worker_password   'CHANGE_ME_WORKER'
\set auth_password     'CHANGE_ME_AUTH'

CREATE ROLE adai_migrator LOGIN PASSWORD :'migrator_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

CREATE ROLE adai_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- BYPASSRLS is deliberate and is the one privilege that distinguishes this role.
CREATE ROLE adai_worker LOGIN PASSWORD :'worker_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS;

CREATE ROLE adai_auth LOGIN PASSWORD :'auth_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS;

CREATE DATABASE adai OWNER adai_migrator;

\connect adai

-- Only the migrator may create objects.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO adai_app, adai_worker, adai_auth;
GRANT CREATE ON SCHEMA public TO adai_migrator;

-- DML only for the runtime roles, on tables the migrator creates now and later.
ALTER DEFAULT PRIVILEGES FOR ROLE adai_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO adai_app, adai_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE adai_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO adai_app, adai_worker;

-- The API may never read the audit log; it may only append to it.
-- (RLS also enforces this, via an INSERT-only policy. Both, deliberately.)
ALTER DEFAULT PRIVILEGES FOR ROLE adai_migrator IN SCHEMA public
  REVOKE SELECT, UPDATE, DELETE ON TABLES FROM adai_app;

-- adai_auth is deliberately not covered by the default-privileges grants above. It gets
-- exactly one privilege, on exactly one table, and must be re-granted if users is
-- recreated.
ALTER DEFAULT PRIVILEGES FOR ROLE adai_migrator IN SCHEMA public
  REVOKE ALL ON TABLES FROM adai_auth;
-- Run after the first migration:
--   GRANT SELECT ON users TO adai_auth;
