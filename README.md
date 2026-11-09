# Atlas CX

Customer Operations & Service Intelligence Platform. The repository contains the
M0 foundation, M1 identity and customer core, M2 support workflow, M3
configuration and follow-up, and M4 customer activity and service analytics.
Atlas CX is standalone.

Staff can sign in, manage customers and contacts, search and filter records,
archive records, and administer workspace membership and teams according to
their role. Administrators issue single-use staff and portal setup links.
Bound portal contacts can submit requests and follow their own public
conversations. Staff can claim and assign cases, reply publicly, write private
notes, request information, resolve, reopen, and close work according to their
role. Cases retain resolution cycles and response/resolution target snapshots.
Administrators publish versioned case configuration from five starter presets.
Staff manage follow-up tasks, and portal contacts can rate their latest resolved
cycle. A low rating creates a single staff follow-up. Administrators and managers
can validate and commit customer CSVs, inspect report records, and export service
data. Administrators define accepted events and issue workspace ingestion keys.
Staff inspect recorded events and operational reports. Health and knowledge
retrieval remain planned.

Read the unchanged [product specification](docs/PRODUCT_SPEC.md),
[design system](docs/DESIGN_SYSTEM.md), [wireframes](docs/Atlas_CX_Wireframe_Atlas.pdf),
[AGENTS.md](AGENTS.md), and [roadmap](docs/ROADMAP.md) before coding.
[Source provenance](docs/SOURCES.md) records original names and hashes.

## Local containers

Requirements: Docker Engine/Desktop with Compose v2 supporting `up --wait`.

```sh
cp .env.example .env
docker compose config --quiet
docker compose up --build -d --wait
python scripts/smoke.py
```

PowerShell: use `Copy-Item .env.example .env` for the first command.
Open [Atlas CX](http://localhost:8080) and [API docs](http://localhost:8000/api/docs).
The proxy serves frontend and API from one origin; ports bind only to loopback.
PostgreSQL 17 includes pgvector 0.8.2. A separate migration job runs before API
startup. The API receives only the non-owner `atlas_app` database credential.

Initialize a workspace through the operator CLI. It prompts for the password;
do not put passwords in command arguments or shell history.

```sh
docker compose run --rm -it migrate .venv/bin/python -m app.modules.identity.operator bootstrap --workspace example --name "Example workspace" --email admin@example.com --display-name "Workspace administrator"
```

Use your own email and workspace name. There is no default administrator or
public registration. Repeating bootstrap with the same account verifies its
password and does not reset it. Once an administrator exists, add staff through
Settings. Copy each setup link through a trusted channel; Atlas CX does not
send email. Links expire after 24 hours and can be consumed once. People with an
existing Atlas CX account must enter their current password.

Operator recovery, after verifying the person's identity outside Atlas CX:

```sh
docker compose run --rm -it migrate .venv/bin/python -m app.modules.identity.operator recover --email admin@example.com
```

Recovery prints a sensitive single-use link to the operator terminal. Do not
paste it into logs or issues. Workspace administrators cannot reset another
person's global password.

`docker compose down` retains local data. Adding `--volumes` erases it.
Role initialization runs only for a fresh volume; changing example values does
not rotate existing database passwords. Example credentials and signing keys are
public local-development values. Production configuration rejects those signing
keys and requires an HTTPS public origin. The local stack has no public TLS or
backup automation.

## Host development

Use Node 24.17.0, npm 11, Python 3.12.13, and uv 0.11.2. Exact dependencies are
locked in package-lock.json and backend/uv.lock.

```sh
npm ci
docker compose up -d --wait db
docker compose run --rm migrate
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Run `npm run dev` from another terminal at the repository root. For Vite
development, set `PUBLIC_ORIGIN=http://localhost:5173` in the host API environment
before starting it. Vite proxies `/api` to port 8000. The origin must match exactly
for browser mutations; there is no wildcard CORS. Cookies remain Secure,
HttpOnly, and SameSite=Lax, including on the local loopback development origin.

Host processes use the localhost database URLs in .env.example. Alembic and the
operator CLI require an explicit `MIGRATION_DATABASE_URL` environment variable;
they never fall back to the API credential. Never give that variable to the API.
Liveness works without PostgreSQL; readiness and authenticated work require it.

## Checks

```sh
npm run check
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Default pytest selects unit/HTTP tests. Integration tests require an expendable,
migrated PostgreSQL database: set `TEST_DATABASE_URL` to its `atlas_app` URL and
`MIGRATION_DATABASE_URL` to its `atlas_migrator` URL, then run
`uv run pytest -m integration`. Tests exercise the actual non-owner role,
forced RLS, authentication, CSRF, CRUD, constraints, setup links, and revocation.
They also exercise contact-scoped case access, private-message isolation,
concurrent claims, state transitions, clocks, retries, and assignment transfers.
SQLite cannot verify these controls. Fixture cleanup uses the migration role.

From the root:

```sh
npx playwright install chromium
npm run test:e2e
python scripts/verify_sources.py
```

Browser tests exercise customer, support, and portal interactions at 1440, 1024,
700, and 390 pixels, plus the foundation's 320-pixel shell checks. Test-only API
fixtures provide deterministic UI states. The separate M1–M4 real-stack tests
skip unless `E2E_BASE_URL` is set. CI runs them against Compose with synthetic
identities and a random password prepared by `backend/scripts/seed_m1_browser.py`
and `seed_m2_browser.py`. These scripts write private, ignored temporary
credentials files and are only for an expendable test database. They never run
at application startup. Do not run them against real customer data.

## Demonstrating the support workflow

1. Sign in as an administrator. Create a customer and two contacts under Customers.
   Issue each contact a portal setup link and accept it in a separate browser
   context. Setup links are sensitive and single use.
2. Sign in as the first contact through `/portal/sign-in`. Choose New request,
   enter a category, subject, and description, then submit. Reload to confirm it
   persisted. The second contact cannot see or open that request.
3. In the staff Support inbox, find the request and choose Claim case. Details
   provides assignment and priority editing. A competing stale claim must be
   reviewed before retrying.
4. Add an Internal note, then a Public reply. Only the public reply appears in
   the portal. Choose Ask customer to post a question and pause resolution;
   the contact's reply resumes it. First response never pauses.
5. Resolve with a public summary and resolution code. The portal can explicitly
   reopen with a message. History retains the prior resolution and a new cycle.
   Resolve again, then close as a manager or administrator. Closed requests
   offer creation of a related request.

The default published configuration supplies three categories and four priority
targets. Each case pins its configuration and original targets; editing priority
does not reset its clocks. Public and internal drafts remain separate in memory.
Failed writes retain drafts, and conflicts require review and a new explicit save.

## Configuration, follow-ups, and imports

Open **Settings → Case configuration → Start a draft**. Copy a preset, choose
workspace routing teams, and edit categories, priority targets, state labels,
or fields. Save the draft, review its portal form, and publish it for new cases.
To demonstrate a second industry, publish the Service business preset in a
separate workspace, route Appointment to an active team, and submit a portal
request with an appointment date. Earlier cases still use their original version.

Submit a rating of 1 or 2 after a portal request is resolved. The resulting task
appears under **Follow-ups → Feedback**. Open it, enter what was done, and
complete it. Historical ratings remain visible to their requester.

Choose **Customers → Import CSV** to validate a UTF-8 file, inspect each row, and
confirm the import. The required columns are `external_id`, `name`, and `kind`.
The optional columns are `lifecycle`, `owner_email`, `tags` (semicolon-separated),
and `activity_expected` (true or false). The limit is 1 MiB and 1,000 data rows.
Previews expire after 24 hours. From the backend checkout, an operator can clear
expired staging with `uv run python -m scripts.purge_customer_imports WORKSPACE_SLUG`
using the migration database credential.

## Demonstrating recorded activity

1. In **Customers**, create an active synthetic customer with an external ID
   such as `synthetic-training-01`.
2. In **Settings → Event tracking**, create the enabled key `feature_used`.
   Set the display label to **Synthetic feature used**, enable **Counts as
   meaningful activity**, and add a string property `feature` with a maximum
   length of 120.
3. Create an ingestion credential and copy it. Run the following local command
   with a recent offset timestamp in place of the placeholder. Paste the key
   when the terminal prompts for it.

   ```sh
   python scripts/send_synthetic_events.py --customer-external-id synthetic-training-01 --namespace first-run --occurred-at "<recent ISO timestamp with offset>"
   ```

4. Open the customer’s **Timeline** or **Activity** tab. Two synthetic records
   appear in occurrence order, including the late event. The terminal reports
   the replay as a duplicate. Reusing the namespace and timestamp safely
   replays the same records.
5. In **Analytics → Activity**, select the same customer and filter by
   `feature_used`. **Analytics → Service** reports recorded cases, feedback,
   and follow-ups. Administrators and managers can inspect records and export
   a bounded CSV. Revoke the synthetic key in **Event tracking** when finished.

The bearer API is `POST /api/v1/events/batch`. The workspace rate is configurable
per key through `EVENT_BATCHES_PER_MINUTE`. Operators can purge raw events older
than 180 days with the migration database credential. Run from `backend`.

```sh
uv run python -m app.modules.activities.maintenance --workspace WORKSPACE_UUID
```

Regenerate contracts after API schema changes.

```sh
cd backend
uv run python -m scripts.export_openapi
cd ..
npm run api:generate
```

CI checks quality, contracts, dependencies, source hashes, PostgreSQL isolation,
M0 through M3 data preservation during upgrade, rollback and repeat upgrades,
container builds, health smoke checks, and real browser workflows.
It does not deploy. See [verification evidence](docs/VERIFICATION.md),
[M3 changed files](docs/M3_FILE_MANIFEST.md),
[identity/customer architecture](docs/architecture/0002-identity-customer-core.md),
[case workflow decisions](docs/architecture/0003-case-workflow.md), and
[M3 architecture decisions](docs/architecture/0004-configuration-followups-imports.md).
See also the [M4 changed files](docs/M4_FILE_MANIFEST.md) and
[M4 architecture decisions](docs/architecture/0005-activity-analytics.md).
The next milestone is **M5 Knowledge and RAG**.
