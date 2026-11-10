# Milestones

M0 Foundation is complete: Organic shell, FastAPI health API, PostgreSQL/pgvector,
forced row-level security, Alembic, containers, dependency locks, and CI.

M1 Identity and customer core is implemented: operator bootstrap, Argon2id
passwords, opaque server-side sessions, CSRF/Origin protection, workspace
memberships and roles, single-use setup links, portal bindings, teams,
customer/contact CRUD, and the Customers workspace. Session tokens stay out of
browser storage.

M2 Case vertical slice is complete. It includes the default published
configuration, portal requests scoped to each contact, a staff inbox and case
list, assignment and explicit claim, public replies and private notes, read
markers, fixed transitions, resolution cycles, response and resolution clocks,
optimistic concurrency, and idempotent retries.
The Organic support and portal interfaces adapt at 1440, 1024, 700, and 390px.
See [verification evidence](VERIFICATION.md) for executed checks and limits.

M3 Configuration and follow-up adds five starter presets, immutable published
versions, typed case fields, task ownership and completion history, and ratings
for the latest resolved cycle. A qualifying rating creates one follow-up.
Customer CSVs have a staged preview, row-level errors, and an atomic commit.
See the [M3 verification record](VERIFICATION.md#m3-configuration-and-follow-up).

M4 Activity and analytics adds configurable event definitions, revocable
ingestion credentials, atomic event batches, and the Customer 360 timeline.
Analytics shows recorded activity by customer and operational service measures,
with drilldowns and audited exports for administrators and managers.
See the [M4 verification record](VERIFICATION.md#m4-activity-and-analytics).

M5 Knowledge and RAG implements document drafts, published revisions, durable
indexing, authorized lexical and vector retrieval, and the support copilot.
Generation availability depends on the pinned local model's evaluation gates.
See the [synthetic evaluation record](RAG_EVALUATION.md).

**M5.1 generation quality is in progress and paused at an incomplete checkpoint.**
The first development candidate fell back on every attempted generation.
Generation stays disabled. Follow [M5.1 resume instructions](M5_1_RESUME.md)
before further experiments. The original evaluation corpus and gates remain unchanged.

**M6 Health and product finish** remains deferred until the M5.1 handoff.
It adds versioned health profiles, daily snapshots, and explanations for
coverage, missing inputs, and stale scores.
M7 validates the complete release, including restore, load, security, and
accessibility evidence. No merge to main or deployment is authorized.
