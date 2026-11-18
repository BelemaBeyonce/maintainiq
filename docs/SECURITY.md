# M1 security baseline and remaining work

Implemented: Argon2 password hashing, Django sessions/CSRF, one-hour established Django reset tokens, single-use hashed invitations, explicit role/site memberships, server-side tenant scoping, composite relationship constraints, safe errors, explicit CORS origins, private storage configuration, transactional audit append, request-size bounds, shared Redis authentication throttling and non-root container users. No public role selection, tenant-admin bootstrap endpoint, public upload, or privileged cross-tenant administrator API exists.

Local Compose binds only frontend and Mailpit to loopback. PostgreSQL, Redis, worker and backend remain on the internal network. Random local secrets are generated into .env; generated synthetic credentials stay in a private volume file. Never publish that file, environment, reset/invitation links or real account test traces. The synthetic flag cannot be cleared through ordinary mutation APIs.

Production is not claimed. Use HTTPS, secure cookies, explicit trusted origins/hosts, a secret manager, independent gateway rate/body/time limits, operational monitoring and reviewed SMTP before deployment. The proxy makes many clients appear as one backend peer; current auth throttles are shared through Redis but a trusted gateway per-client limiter is still required. Never trust caller-supplied forwarded-IP headers without a reviewed proxy chain.

The S3/local attachment layer is configuration/key architecture only. Future upload APIs must add authenticated tenant/site authorization, MIME/content checks, quarantined storage, malware scanning, quotas, download authorization and retention. There are no media-serving URLs or upload buttons pretending to implement that later workflow.

Remaining pilot hardening includes MFA/email verification, durable invitation-email outbox, tenant lifecycle/retention, backup/restore exercises, load/accessibility audits and independent security testing. No safety-critical operation, prediction, AI output or failure-cause assertion is generated. Work orders and AI are outside M1.
