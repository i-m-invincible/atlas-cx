# Identity and customer core

Status: implemented for M1. The source specifications remain unchanged.

## Identity and authorization

A global user can belong to several workspaces and have separate staff and
portal access. There is no public user directory. Login and provisioning use
exact normalized-email lookups. Pending staff projections retain the inviting
workspace's supplied name, rather than disclosing a global name before acceptance.
Existing-account setup requires the existing password and never silently resets it.

The operator CLI requires the migration role and prompts for passwords. It
bootstraps the first administrator and issues recovery links only after external
identity verification. Tenant administrators can provision access, not reset
global credentials.

Random 256-bit session and setup tokens are stored as SHA-256 digests.
Passwords use Argon2id (64 MiB, three iterations, parallelism one). Sessions have
a 12-hour idle limit and seven-day absolute limit. Password changes revoke all
sessions. Each request rechecks membership or portal binding; role changes and
deactivation revoke affected sessions. Failed login attempts use hashed account
and IP buckets in PostgreSQL, with five failures per 15-minute window.

Cookies are Secure, HttpOnly, SameSite=Lax, and host-only. The frontend keeps
session state in memory and clears private query data when identity changes.
Unsafe requests require exact Origin and a CSRF header, including login/setup.
Anonymous CSRF values are signed and matched to an HttpOnly cookie. Authenticated
CSRF values are derived from the session using a separate server secret.
Setup tokens travel in URL fragments, which the setup page removes immediately.

## Tenant boundary

Every tenant row has workspace scope and forced PostgreSQL RLS. Composite
foreign keys prevent cross-workspace associations. The API role cannot bypass
RLS, owns no tables, and cannot hard-delete customers, contacts, or audit history.
Tenant settings are transaction-local and derived from verified identity.
A narrowly scoped workspace-slug SELECT policy supports pre-authentication login.

Staff customer visibility is workspace-wide; teams do not create hidden customer
silos. Viewers read; agents create/edit; managers and administrators archive.
Only administrators change workspace settings, memberships, teams, or portal
provisioning. The last active administrator cannot be removed. Required customer
ownership and feedback-manager transfers occur in the access-change transaction.

Portal contact SELECT policies expose only the bound contact and its own binding.
Portal identities cannot call staff CRM endpoints, even for their own customer.
M2 must add contact-scoped case policies and safe public projections before
exposing cases. M1 contains no case table or case visibility implementation.

## Writes, history, and contracts

Customer/contact records use soft archive, versioned detail ETags, and mandatory
If-Match for changes. Missing preconditions return 428; stale versions return 409.
Writes and audit events commit together before HTTP success. Archive disables
portal bindings and invalidates unused portal setup links. Bound contact emails
cannot change. Audit payloads record field names and explicit archive reasons,
not passwords, session values, or entire record bodies.

Lists use signed keyset cursors bound to workspace, resource, and filters.
The API rejects extra input fields and naive datetimes. OpenAPI generates the
frontend DTOs. Unknown health/activity stays null rather than inventing values.

The original M0 migration is preserved. M1 is an additive frozen-SQL migration.
CI exercises an upgrade with an existing M0 workspace and empty-schema rollback/
repeat upgrade. The API continues to use only the application database role.

## Browser architecture and limits

React Query owns customer data; a separate session provider owns identity.
React Hook Form/Zod validate drafts. Temporal converts workspace-local tracking
dates to aware instants and rejects ambiguous or nonexistent local times.
Feature routes load separately to keep the initial bundle bounded.

The compact interface uses existing Organic tokens and self-hosted Source Serif 4
and Instrument Sans. Forms retain drafts on failures, focus error summaries,
and guard unsaved navigation. Conflict review requires an explicit new save.
The portal page states that request handling is not available until M2.

There is no email delivery, public password-reset endpoint, case workflow,
knowledge/RAG, analytics, health computation, or external service integration.
Local public development keys are rejected by production configuration. Public
hosting, restore, load testing, and screen-reader release review remain later work.
