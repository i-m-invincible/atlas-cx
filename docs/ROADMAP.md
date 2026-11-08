# Milestones

M0 Foundation is complete: Organic shell, FastAPI health API, PostgreSQL/pgvector,
forced row-level security, Alembic, containers, dependency locks, and CI.

M1 Identity and customer core is implemented: operator bootstrap, Argon2id
passwords, opaque server-side sessions, CSRF/Origin protection, workspace
memberships and roles, single-use setup links, portal bindings, teams,
customer/contact CRUD, and the Customers workspace. Session tokens stay out of
browser storage.

M2 Case vertical slice is implemented: default published configuration, portal requests scoped to each contact,
staff inbox and case list, assignment and explicit claim,
public replies and private notes, read markers, fixed transitions, resolution
cycles, response/resolution clocks, optimistic concurrency, and idempotent retries.
The Organic support and portal interfaces adapt at 1440, 1024, 700, and 390px.
See [verification evidence](VERIFICATION.md) for executed checks and limits.

Work is paused at the user's request after the verified M2 code checkpoint.
Before starting another milestone, follow [RESUME.md](RESUME.md) to check the
saved documentation commit and finish the M2 handoff.

The next implementation milestone is **M3: Configuration and follow-up**, from product
specification section 19:

- Publish immutable configuration versions and demonstrate a second preset.
- Provide all five prescribed presets and bounded custom fields.
- Implement follow-up tasks with scoped ownership and audit history.
- Add ratings and create exactly one task for qualifying low feedback.
- Add the specified CSV import flows and validation.

M4 adds activity ingestion and independently checked analytics. M5 adds knowledge
and RAG. M6 adds rules-based health and product finishing. M7 validates the complete
release, including restore, load, security, and accessibility evidence. These
remain planned. No merge to main or deployment is authorized.
