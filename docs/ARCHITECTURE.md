# Milestone 1 architecture

The monorepo separates `backend/` (Django domain), `frontend/` (Next.js UI), `infra/` (local runtime), and `docs/` (contracts and evidence). Existing foundation work was continued rather than rebuilt. No Milestone 2 workflows or AI services are included.

| Component | Responsibility |
|---|---|
| `core/models.py` | Tenant, global User/Role, Membership, Site, FunctionalLocation, AssetCategory, Asset, invitations/site grants and AuditEvent |
| `core/scope.py` | Active membership resolution and permitted-site querysets |
| `core/services.py` | Atomic asset writes/archive, hierarchy checks, invitations, account verification and access updates |
| `core/serializers.py` | Explicit validated inputs; unknown and read-only mutation fields rejected |
| `core/views.py` | REST contracts, scoped pagination/filters/counts/export and authentication endpoints |
| `core/tasks.py` | Bounded-retry password reset mail delivery via Celery |
| `core/storage.py` | Private tenant/site namespaced storage-key foundation; no upload endpoint |
| `frontend/lib/api.ts` | Same-origin session/CSRF requests, tenant selection, sanitized errors |
| `frontend/components/workspace.tsx` | Membership-backed organization/site selection; IDs are hints, not permissions |
| `infra/dev.py` | Preserve/generate private local configuration; start/stop Compose |

## Identity and authorization

Django hashes passwords with Argon2 and stores sessions in PostgreSQL. Cookies are HttpOnly/SameSite=Lax; CSRF tokens protect mutations including anonymous login/invitation acceptance/password reset. Login does not accept roles. Invitations store only SHA-256 digests of high-entropy bearer tokens, expire after 24 hours, and are consumed atomically. A changed/deactivated inviter loses the ability to authorize acceptance. Existing accounts must prove their current password before joining another organization. Password-reset tokens use Django's established generator, expire in one hour, and become invalid after password change; row locking prevents concurrent reuse.

Scope checks are enforced on every business API path. Site grants restrict managers, engineers, technicians, requesters and auditors; organization admins remain tenant-scoped. Foreign relationship inputs are looked up inside the selected tenant/site before mutation. Hierarchy changes serialize through a tenant row lock to prevent racing cycle creation. Asset site transfers are not supported in M1.

## Persistence and audit

Domain mutations run inside database transactions with their audit record. Archiving keeps the asset, before/after snapshots and actor/time evidence. The audit model, instance operations and queryset updates/deletes reject mutation at application level; protected database access remains an operational responsibility. Cross-scope composite foreign keys add defense in depth beyond API filtering.

## Queue and attachments

Redis provides shared authentication throttles and the Celery broker. The M1 worker sends password-reset emails; no work-order scheduler is presented as implemented. Mailpit is a private local development inbox. SMTP credentials belong in deployment environment variables.

Private filesystem storage and S3-compatible storage can be configured. Object keys use tenant/site UUID namespaces plus random IDs. No files are served publicly and no attachment endpoint exists in M1. Future attachment workflows require MIME/content validation, quarantine, malware scanning, size quotas, scoped signed download authorization and retention policy before release.
