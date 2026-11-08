# Milestones

M0 Foundation is complete: Organic shell, FastAPI health API, PostgreSQL/pgvector,
forced row-level security, Alembic, containers, dependency locks, and CI.

M1 Identity and customer core adds operator bootstrap, Argon2id passwords,
opaque server-side sessions, CSRF/Origin protection, workspace memberships and
roles, single-use setup links, portal bindings, teams, customer/contact CRUD,
and a functional Customers workspace. See VERIFICATION.md for executed checks
and any remaining verification limits. No session token is stored in localStorage.

The exact next milestone is **M2: Portal request → agent reply → resolution**,
as specified in PRODUCT_SPEC section 19:

- Seed the default published case configuration and opening workflow.
- Let a bound portal contact create and read only their own cases.
- Provide staff inbox, case detail, and explicit claim behavior.
- Separate public messages from private notes in storage and projections.
- Implement case cycles, allowed transitions, resolution, and concurrency guards.
- Test two-workspace isolation and two contacts sharing one customer through
  real case APIs and the non-owner PostgreSQL role.

The M1 portal screen establishes identity only. It does not claim case access
tests for tables or workflows that do not yet exist.

M3 adds versioned configuration and follow-up. M4 adds events and analytics.
M5 adds knowledge and RAG. M6 adds rules-based health and product finishing.
M7 validates the complete release, including restore, load, security, and
accessibility evidence. These remain planned. No deployment is authorized.
