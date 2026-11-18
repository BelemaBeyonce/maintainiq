# MaintainIQ — Milestone 1: Foundation

MaintainIQ is a maintenance-management foundation for teams responsible for centrifugal pumps and compressors. **Milestone 1 only** provides organization/site boundaries, equipment registration, controlled onboarding and a traceable asset history. The frontend reads and writes a real Django/PostgreSQL API; dashboard counts and registry records are persisted, not static mock data.

No work orders, preventive scheduling, maintenance-memory extraction, repeat-failure investigation, AI, prediction, offline sync or operational safety approval are implemented in this milestone.

## Run locally — Windows, macOS or Linux

Install **Docker Desktop with Compose**, **Git**, and **Python 3.12+**. Start Docker Desktop, then:

```powershell
git clone https://github.com/BelemaBeyonce/maintainiq.git
cd maintainiq
py infra/dev.py up
```

On macOS/Linux use `python3 infra/dev.py up`. This single startup command generates a private `.env` with random local secrets if absent, builds the applications, starts PostgreSQL/Redis/Celery/local mail, applies migrations, seeds synthetic demo records and waits for health checks. It never overwrites an existing environment. Do not first copy the placeholder `.env.example`; the launcher does the secure replacement automatically. You can also configure your own `.env` and run `docker compose up --build -d --wait` directly.

Open:

- **Application:** http://localhost:3000
- **Interactive API:** http://localhost:3000/api/docs/
- **OpenAPI schema:** http://localhost:3000/api/schema/
- **Local email inbox:** http://localhost:8025 (development only)

To display your generated local-only demo passwords:

```powershell
py infra/dev.py credentials
```

Sign in as `manager.a@synthetic.maintainiq.test` using its generated password. Organization B uses `manager.b@synthetic.maintainiq.test`. Admin, engineer, technician, requester and auditor accounts follow the same email pattern. **No passwords are hardcoded.** Credentials are generated once into an operator-only file in the private data volume and are not returned by any web endpoint. Keep the output private; do not reuse these accounts/passwords outside the synthetic demo. Password-reset emails appear in the local inbox. The credential file retains initial passwords, so it becomes stale if an account resets its password.

Stop without deleting data:

```powershell
py infra/dev.py down
```

Named volumes preserve the database, private storage and initial credentials. `docker compose down -v` is destructive and is intended only for disposable test environments. If a port is occupied, adjust the loopback-only bindings and matching origin settings before startup. Changing a stored PostgreSQL password requires a reviewed database credential change; replacing `.env` alone does not change an existing database user.

## What is implemented

- Django/DRF backend, PostgreSQL, Next.js/TypeScript frontend, Celery and Redis.
- Secure session login/logout with HttpOnly cookies and CSRF enforcement, password reset through Django's established token implementation, operator onboarding and single-use invitations.
- Six roles: admin, manager, engineer, technician, requester and auditor. No public self-service privileged role selection.
- Organization/site switchers, organization profile and membership management for admins, site/category/location creation and editing, and scoped invitations.
- Asset create/read/update/archive, category and location hierarchy, parent-asset cycle protection, search/filter/pagination, scoped CSV registry export and basic dashboard counts.
- Append-only application audit evidence for asset and access changes; archive retains equipment and its registry history.
- Two isolated synthetic organizations; an oil-and-gas demonstration site with pumps and compressors; synthetic labels throughout demo views.
- Private local/S3 storage abstraction/configuration. Upload/download endpoints are deliberately not exposed in M1.
- Reproducible migrations, generated OpenAPI contract, frontend/backend tests, real-browser acceptance tests and GitHub Actions.

## Architecture

```mermaid
flowchart LR
    Browser[Next.js UI] --> Proxy[Same-origin /api proxy]
    Proxy --> Auth[Django sessions + CSRF]
    Auth --> Scope[Tenant membership + permitted sites]
    Scope --> Services[Domain services + transactions]
    Services --> DB[(PostgreSQL)]
    Services --> Audit[Append-only audit events]
    Audit --> DB
    Auth --> Redis[(Redis: shared throttles / broker)]
    Redis --> Worker[Celery: password-reset email]
    Worker --> Mail[SMTP / local Mailpit]
    Storage[Private local / S3 storage configuration]
```

See [architecture](docs/ARCHITECTURE.md), [API and role contracts](docs/API.md), [database integrity](docs/DATABASE.md), [security boundaries](docs/SECURITY.md), and [actual verification](docs/VERIFICATION.md).

## Permissions in M1

Admins configure their own organization, memberships, sites, locations and categories. Admins and managers may create/update/archive assets. Managers can invite lower-privilege roles only to their permitted sites. Engineers, technicians and auditors can read permitted asset history; requesters can view permitted assets but not audit history or bulk export. Engineers/auditors are read-only in this milestone. Tenant admins have no access to another organization unless independently invited there. Global Django superuser flags do not bypass API membership checks.

Every data request selects an organization with `X-Tenant-ID`; this is only a selection hint, not authorization. The server verifies the user's active membership and authorized sites. Lists, counts, object retrieval, relationship mutations, audit history and registry exports use that scope. Composite PostgreSQL foreign keys reject cross-tenant/site relationships even if application validation is bypassed.

## Run checks without containers

Requires Python 3.12+, Node 24 and a disposable PostgreSQL database. The Django test configuration uses private generated test-only settings and an in-memory throttle/email backend; production uses Redis/SMTP.

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
$env:DATABASE_URL = "postgresql://USER:PASSWORD@localhost:5432/maintainiq_test"
.\.venv\Scripts\python.exe -m pytest --cov=core --cov-report=term-missing --cov-fail-under=90
.\.venv\Scripts\python.exe -m ruff check . ..\infra
.\.venv\Scripts\python.exe -m ruff format --check . ..\infra
cd ..\frontend
npm ci
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
```

The PostgreSQL test user must have permission to create the Django test database. Never point test tooling at a production account/database. CI uses a disposable passwordless PostgreSQL service only on its isolated runner. Test credentials, deployment credentials and synthetic demo credentials are separate.

For source development, run the Django server on port 8000 with environment values appropriate for your local database/Redis, and `npm run dev` in `frontend/`. The Next.js proxy defaults to `http://127.0.0.1:8000`; container builds explicitly target `http://backend:8000`. API trailing slashes are preserved. A production frontend build can be started with `npm start` after the supplied standalone preparation step.

## Milestone 1 acceptance workflow

1. Sign in as Organization A manager, open the asset registry, and register a synthetic pump.
2. Edit the serial number and inspect the recorded create/update evidence on the detail page.
3. Archive the pump. It disappears from active lists; include archived records to open the retained record and history.
4. Sign in as Organization B manager. A's record, history and export contents remain unavailable, even if A's UUID is supplied directly.
5. Sign in as an A technician. Read permitted equipment; attempts to create sites, invite admins or mutate assets are rejected server-side.
6. Sign in as an A admin to create a site/category/location and invite a technician to only that site. Open the private invitation, accept it and verify the resulting scope.

To rerun the browser suite against a disposable local Compose instance, capture `python infra/dev.py credentials` into an ignored `demo-credentials.json` at the repository root, run `npx playwright install chromium` from `frontend/`, then `npm run test:e2e`. You can instead set `DEMO_CREDENTIALS_FILE` to the absolute path of a private credential file. Do not run the mutating suite against valuable or production data.

The automated browser test exercises these real screens and API boundaries. It also checks an explicitly invited multi-organization account and mobile navigation. Screenshots, when generated, contain synthetic data only. See [acceptance and verification](docs/VERIFICATION.md).

## Non-demo onboarding

After migrations, use the protected operator shell:

```bash
docker compose exec backend python manage.py onboard_tenant --name "Your organization" --slug your-organization --email your-admin@example.com
```

The command prompts for a password and creates the first tenant admin. Existing accounts join through an authenticated invitation and must verify their current password. Subsequent user roles/site grants are assigned only by authorized organization admins/managers.

## Limits and next review gate

This is an M1 prototype foundation, not a claim of commercial or production readiness. No MFA, email-address verification, malware-scanning upload flow, passwordless identity provider, operational performance benchmark, backup/restore drill or public deployment is claimed. Invitations currently send synchronously and need an outbox for robust delivery guarantees. Archive is intentionally one-way in M1; cross-site asset transfer requires a future reviewed workflow. Audit evidence is append-only through the application, not tamper-proof against a database administrator.

Milestone 2 requires separate approval. The next scope would cover fault requests, work-order transitions, preventive plans and cost capture—not AI or automatic root-cause claims.
