# SaaSSpend Stage 2.1 Security Review

Review status: updated 2026-10-27

This report distinguishes findings from the initial read-only review that are
resolved in the current source from remaining implementation and deployment
risks. Source review does not certify a deployment or production database.
No live migration or production cutover has been performed.

## Historical findings resolved in current source

| Historical concern | Current status | Current behavior |
|---|---|---|
| Production API requests could fall back to an HTTP loopback endpoint while carrying a bearer token. | Resolved in frontend source | Production configuration requires an explicitly configured HTTPS `VITE_API_URL`; development permits HTTPS or explicit HTTP loopback URLs. The API client validates configuration before session lookup and request dispatch. Deployment must still set the correct trusted endpoint. |
| Candidate migration preparation could discard unrecognized legacy application columns. | Resolved in migration preparation | Preparation compares the complete `applications` column set with the supported legacy schema, including `renewal_reviewed`, and rejects missing or unexpected columns before creating a backup or candidate. |
| Earlier migration recovery relied on reopening a partly migrated target. | Superseded for candidate preparation | Preparation now builds and validates a separate candidate from a verified backup and does not replace the source database. This does not implement production cutover or rollback. |
| The auth implementation had no tracked Git baseline for comparison. | Historical provenance concern | `backend/auth.py` is now part of the tracked implementation. Its current source performs JWT and allowlist validation, but this fact alone does not establish historical equivalence to any prior deployment. |

## Current source review

| Area | Result | Evidence and limits |
|---|---|---|
| JWT authentication and identity | PASS, source-level | `backend/auth.py` obtains a JWKS signing key, restricts accepted algorithms, validates issuer, audience, required claims and expiry, derives identity from verified `sub`, and enforces `SAASSPEND_ALLOWED_USER_IDS`. Runtime identity-provider configuration and deployed keys were not inspected. |
| Organization membership and roles | PASS, source-level | `backend/main.py` applies authentication at the API router, checks membership for tenant routes using the verified user ID and selected organization, and applies editor/admin thresholds to writes. `backend/data.py` scopes business queries by organization. No live authorization configuration was tested in this review. |
| Candidate source preservation | PASS for preparation path | `backend/tenant_migration.py` reads the source in read-only mode, verifies a backup, builds the candidate separately, validates it, and publishes only to the candidate path. Tests cover disposable sources, schema/record corruption, backup failures, WAL state, and publication failures. This does not prove production operational readiness. |
| Frontend endpoint trust | CONDITIONAL RISK | `frontend/src/lib/apiBase.ts` enforces HTTPS in production and rejects malformed configuration, but accepts any syntactically valid HTTPS host. A deployment must control `VITE_API_URL` and ensure it names the intended API endpoint. |
| Fixture and sample-data isolation | LIMITED / PROTOTYPE | `backend/data.py` restricts the current in-memory shadow IT, access, and security fixtures to the legacy organization. These records are illustrative, mutable process-local samples, not organization-specific integrations or durable business records. |

## Remaining risks and limitations

1. **Production cutover and rollback are not implemented.** Candidate preparation is available, but there is no supported command or procedure that installs the candidate as the live database or restores a cutover. Do not treat preparation success as a completed migration.
2. **Endpoint trust remains deployment-dependent.** HTTPS validation prevents HTTP production endpoints, but does not pin the API hostname. Protect production build configuration and deploy only with the approved `VITE_API_URL`.
3. **Operational migration controls remain outstanding.** Before any separately approved production cutover, define and rehearse a backup, writer shutdown, connection closure, WAL/SHM handling, candidate installation, post-install validation, and rollback procedure using disposable copies. The candidate command itself does not perform those actions.
4. **Prototype fixtures are not tenant-owned persisted records.** Legacy-only gating prevents them from being returned to newly created organizations, but they remain sample data held in backend process memory.
5. **Deployment settings were not audited.** This report does not verify environment-variable values, CORS deployment origins, Supabase project configuration, infrastructure, production database state, or actual deployed frontend artifacts.

## Migration gate

Do not perform production cutover based solely on this report or on candidate
preparation. Require explicit owner approval, an approved verified Supabase
user UUID configured locally (not inferred from the allowlist), a verified
backup, a tested operational cutover and rollback procedure, stopped writers,
closed database connections, and explicit WAL/SHM handling. Revalidate the
candidate and source immediately before any separately approved operation.
