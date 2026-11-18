# Milestone 1 verification

Executed on 18 November 2026. Existing source was inspected and continued; no Milestone 2 workflows or AI features were implemented. Previous results were rechecked rather than assumed.

| Check | Actual local result |
|---|---|
| Backend Pytest suite | **61 passed** against PostgreSQL 16 |
| Backend coverage | **95.07%** of `core` application statements (973 statements, 48 missed); includes migrations and management commands |
| Backend Ruff lint / format | Passed |
| PostgreSQL migrations | Fresh test database creation and both migrations passed; deployed local schema current; no model drift |
| Composite constraints | Direct cross-tenant/site ORM writes rejected; rollback and tenant-scoped mutations tested |
| OpenAPI | Generated and validated with fail-on-warn; no warnings/errors in final check |
| Demo seed | Two tenants, 12 generated accounts, four synthetic seed assets; repeated seed preserves credentials/data/audit counts |
| Frontend ESLint | Passed, zero warnings permitted |
| Frontend TypeScript | Passed |
| Frontend unit/API-client tests | **10 passed**, no unhandled test errors |
| Frontend optimized production build | Passed; standalone server started successfully |
| Live Playwright acceptance | **6 passed** against production Next.js + Django + PostgreSQL + Redis |
| Mobile viewport | 390 px viewport and page width both 390 px; table scroll remains inside its container |
| Compose configuration | Validated; full image/startup verification is covered by the hosted compose-acceptance CI job |
| GitHub CI | Inspect the exact pushed commit's run; a workflow file alone is not a passing hosted run |
| External S3 / public deployment | Not exercised; M1 provides the private-storage architecture/configuration only |

## Commands executed

From `backend/` with the project's development virtual environment:

```bash
pytest --cov=core --cov-report=term-missing --cov-report=xml --cov-fail-under=90
ruff check . ../infra
ruff format --check . ../infra
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py spectacular --file ../docs/openapi.yaml --validate --fail-on-warn
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py migrate --check
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py makemigrations --check --dry-run
```

The local backend additionally ran `migrate --noinput`, `check`, `seed_demo --credentials-file <private-workspace-path>` and `runserver 127.0.0.1:8000 --noreload` using private environment configuration. PostgreSQL and Redis were real disposable containers, not mocked persistence.

From `frontend/`:

```bash
npm run lint
npm run format:check
npm run typecheck
npm test
NEXT_TELEMETRY_DISABLED=1 npm run build
npm start
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e
```

The browser tests use generated synthetic credentials supplied through a private file. CI supplies its own path through DEMO_CREDENTIALS_FILE and installs Chromium through Playwright. Do not point these mutating acceptance tests at real production data. The tests intentionally create additional synthetic records; use a disposable environment for a clean demonstration.

## Acceptance scenarios actually exercised

1. A manager creates a pump, edits its serial number, archives it, and retrieves retained create/update/archive history.
2. B manager cannot read/mutate A's UUID, retrieve A history, or include A data in lists/exports.
3. Technician sees only permitted read views and receives server-side denials for site/admin invitations and registry mutations.
4. Admin creates sites, categories and functional locations, issues a site-limited invitation, and the recipient accepts/logs in with exactly that site grant.
5. A fresh existing account proves its current password when joining a second organization, then switches between manager and engineer scopes without mixed records or write controls.
6. Auditor navigates the asset list on a mobile viewport without global horizontal overflow.

## Problems found and resolved

- Initial test-client default credentials overrode intentionally hostile tenant headers. Changed the fixture so negative tests really send each requested header, then verified denial.
- Locked TypeScript to the supported 6.x line after the installed ESLint tooling rejected TypeScript 7.
- Fixed Next.js/Django trailing-slash redirect looping at the same-origin API proxy.
- Split membership list/detail method contracts and added schema-safe querysets/header documentation; final OpenAPI validation is clean.
- Fixed an incomplete async sign-out mock and tightened browser locators so hidden select options are not mistaken for visible records. No failing test run is counted as passed.
- Fixed mobile overflow from an absolutely positioned assistive label escaping the table container, while retaining internal table scrolling.
- Archived records reject subsequent mutations with 404 even when include_archived=true; history remains readable.

## Scope and limits

M1 is a foundation prototype, not a field-validated CMMS or production-readiness certification. No work orders, preventive schedules, memory extraction, repeat-failure inference, AI, prediction, offline sync, malware-scanning upload pipeline or cloud deployment was performed. MFA, durable invitation delivery, backup/restore drills, load testing and independent security review remain later gates. Audit is append-only at application level, not tamper-proof against privileged database access.

Screenshots in `docs/screenshots/` contain only synthetic records and are evidence of the local browser run. Test traces may contain synthetic session information and should not be shared when running against real data.
