# M1 REST contract

All paths below begin `/api/` and retain their trailing slash. The Next.js same-origin proxy forwards cookies and headers to Django. Obtain CSRF with `GET auth/csrf/`; mutations send `X-CSRFToken` and session cookies. Business requests also send `X-Tenant-ID` with an authorized organization's UUID. Cookies are never stored in JavaScript local storage. Interactive schema: `/api/docs/`.

| Endpoint | Methods | Scope |
|---|---|---|
| `auth/csrf/` | GET | Public CSRF initialization |
| `auth/login/`, `auth/logout/` | POST | Credentials/session; CSRF required |
| `auth/context/` | GET | Current identity and authorized organizations/sites |
| `auth/password-reset/` | POST | Public rate-limited generic reset request |
| `auth/password-reset/confirm/` | POST | Single-use established Django token; password policy |
| `invitations/` | POST | Admin or permitted manager; no self-selected role |
| `auth/invitations/inspect/`, `auth/invitations/accept/` | POST | Private invitation token, expiry and inviter authority checked |
| `organization/` | GET, PATCH | Read own scope; admin-only profile mutation |
| `memberships/` | GET | Admin-only tenant membership list (first 100) |
| `memberships/{id}/` | PATCH | Admin role/site/activation change; no self-demotion |
| `sites/`, `categories/`, `locations/` | GET, POST | Scoped reads; admin creates reference data |
| `sites/{id}/`, `categories/{id}/`, `locations/{id}/` | GET, PUT, PATCH | Scoped read; admin-only code/name and location-parent updates |
| `assets/` | GET, POST | Scoped registry; admin/manager creates |
| `assets/{id}/` | GET, PUT, PATCH, DELETE | Scoped read; admin/manager update/archive |
| `assets/{id}/history/` | GET | Authorized append-only history; requester excluded |
| `assets/export/` | GET | Same filters/scope as list; admin/manager/engineer/auditor only |
| `audit-events/`, `audit-events/{id}/` | GET | Tenant/site-scoped audit; no mutation API |
| `dashboard/` | GET | Scoped persisted registry counts |
| `health/` | GET | Sanitized database connectivity |

Role behavior: admin sees all sites in its own tenant; all other roles need explicit site grants. Only admin/manager can mutate assets. Managers invite engineer/technician/requester/auditor roles only to their own sites; only admins grant admin/manager. Technicians read permitted asset history but cannot administer. Requesters read permitted assets without bulk export or history. Engineers/auditors are read-only in M1. Restricted or foreign objects return 404; unavailable relationship/site inputs return generic validation errors without confirming foreign existence.

Asset creation example (replace all IDs with records in the same authorized scope):

```json
{"site_id":"SITE_UUID","category_id":"CATEGORY_UUID","functional_location_id":null,"parent_id":null,"tag":"P-202","name":"Synthetic injection pump","manufacturer":"Synthetic Example Manufacturer","model":"Example","serial_number":"SYN-202","status":"standby","criticality":"high","description":"Synthetic demonstration record."}
```

Tags normalize to uppercase and are unique per tenant. Status: active, standby, out_of_service. Criticality: low, medium, high, critical. Parent/location must belong to the same site; parent cycles and archived parents are rejected. Site is immutable after asset creation in M1. DELETE archives; active children must first be reparented/archived. `include_archived=true` permits authorized archive retrieval and history; ordinary lists omit archived rows. Synthetic flags, tenant ID, timestamps and archive state are server-owned.

List filters: `site`, `category`, `status`, `criticality`, `search` (<=100 characters), `include_archived` (true/false), `page`. Default pages contain 20 records with stable ordering and `count/next/previous/results`. Counts and export use the same permission filters. CSV values that could be spreadsheet formulas are escaped. Registry export is not a general maintenance-reporting feature.

Validation/permission failures return an `error` envelope with safe details and request ID. Common statuses: 400 invalid fields/relationships, 401 invalid login credentials, 403 missing session/CSRF or insufficient role, 404 hidden/missing resource, 409 uniqueness/archive conflict, 429 throttled login/onboarding. Request limit errors use 413. No raw database or SMTP error is returned. Django session authentication uses 403 for unauthenticated business endpoints. Every application response includes X-Request-ID.
