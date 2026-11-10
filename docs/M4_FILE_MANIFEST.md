# M4 changed files

- `backend/alembic/versions/0006_activity_analytics.py` adds activity tables,
  forced policies, tenant foreign keys, and report indexes.
- `backend/app/modules/activities/` contains event contracts, configuration,
  ingestion, Customer 360 projections, and scoped retention.
- `backend/app/modules/analytics/` contains report contracts, cohort queries,
  snapshot orchestration, record drilldowns, and CSV exports.
- `backend/app/modules/workspace/credential_models.py`,
  `backend/app/platform/rate_limits.py`, and `backend/app/platform/models.py`
  register credential and rate-limit persistence. The application entry point,
  identity and customer projections, settings, and Compose wire in the module.
- `frontend/src/features/activity/` contains the Organic tracking settings,
  timeline, event inspection, and analytics views. Staff navigation, Settings,
  Customer 360, and the frontend stylesheet entry point connect them.
- `backend/tests/test_m4_activity.py` and `backend/tests/test_m4_integration.py`
  exercise canonical validation, tenant isolation, and independently checked
  metric cohorts. Shared PostgreSQL fixture cleanup handles the new tables.
- `backend/scripts/verify_m3_upgrade.py`, `frontend/e2e/m4-responsive.spec.ts`,
  `frontend/e2e/m4-full-stack.spec.ts`, and the GitHub Actions workflow
  verify upgrades, responsive behavior, and the real stack.
- `scripts/send_synthetic_events.py` submits two labelled sample events and
  demonstrates late arrival and replay with a local credential.
- The OpenAPI contract and generated TypeScript types describe the new routes.
  The README, roadmap, verification notes, and architecture decision document
  the implemented scope.
