# Atlas CX engineering rules

Read `docs/PRODUCT_SPEC.md` and `docs/DESIGN_SYSTEM.md` before every coding task.
Inspect `docs/Atlas_CX_Wireframe_Atlas.pdf` for work affecting layout or interaction.
If a required source is missing, stop and report it. Do not invent requirements.
The product specification governs behavior; the design specification, including
its unchanged Organic appendix, governs appearance. Preserve source documents
byte for byte unless the user explicitly requests a specification change.

- Work one milestone at a time. This is standalone Atlas CX. Do not integrate
  Churn Atlas, churn prediction, or unsupported external channels.
- Use the Minimalist Organic system: exact nine colors, Source Serif 4 bound to
  Organic Source Serif, Instrument Sans bound to Organic Instrument Sans,
  restrained paper work surfaces, ruled rows, and specified control radii.
- Keep controls labelled and keyboard accessible, focus visible, reading order
  logical, and loading/error states understandable. Respect reduced motion and
  forced colors. Verify responsive behavior and actual actions, not just images.
- Keep a modular monolith. Routers validate transport, services own rules, and
  scoped repositories own persistence. Use synchronous SQLAlchemy transactions.
- The organization boundary is the workspace. Customers are never tenants.
  Tenant tables require workspace scope, composite tenant foreign keys, forced
  PostgreSQL RLS with read/write policies, and a non-owner application role.
  The workspace root uses its own ID as the boundary. Test with the actual role.
- Derive tenant and audience from verified sessions, never request headers or
  unverified IDs. Deny access until authentication is implemented. Portal
  projections must exclude internal content and other contacts' requests.
- Keep secrets out of Git, browser storage, responses, logs, and screenshots.
  Separate migration credentials from API credentials. Add authorization, CSRF,
  validation, and transaction tests alongside future authenticated mutations.
- Write real tests of observable behavior, failures, and isolation. Database
  tests must use PostgreSQL/pgvector; SQLite cannot verify RLS. Do not silently
  replace integrations with mocks in production or count skipped tests as passes.
- Lock dependencies, maintain Alembic migrations, regenerate API types, and run
  relevant checks. Explain non-obvious choices in short architecture decisions.
- Document only implemented behavior. Label planned work, synthetic fixtures,
  limitations, and unverified checks. No fabricated metrics, features, customer
  evidence, integrations, performance claims, or accessibility certifications.
- Use clear, professional, natural English. Do not add generic marketing copy.
- Never merge to main, deploy, or create paid resources without authorization.

Checks: `npm run check`; from backend, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy app`, and `uv run pytest`.
Run `uv run pytest -m integration` against a migrated local test database, then
`npm run test:e2e` when a browser runtime is available. Record actual results.
