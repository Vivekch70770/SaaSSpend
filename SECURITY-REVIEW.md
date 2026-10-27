# SaaSSpend Stage 2.1 Security Review

Review date: 2026-10-27

This was a read-only source review. No application was started, no tests or
migrations were run, and no database or local environment-file contents were
read. Findings distinguish source-level verification from deployment or
database assumptions that could not be established.

## Review results

| # | Check | Result | Evidence and limitations |
|---|---|---|---|
| 1 | Business endpoints enforce membership using the authenticated identity | PASS | `backend/main.py`: router-level `require_authenticated_user` protects API routes; `require_tenant` checks membership for tenant routes using the authenticated user's ID and the requested organization ID. |
| 2 | Viewer/editor/admin/owner permissions on writes; existing JWT and allowlist unchanged | NEEDS REVIEW | `backend/main.py`: `require_role` guards writes; application/business writes require editor or higher, and access-user deactivation requires admin. `backend/auth.py` derives identity from verified `sub`, validates JWT claims/algorithm, and applies the allowlist. However, `backend/auth.py` is untracked/new relative to `HEAD`, so an unchanged comparison to a prior tracked implementation cannot be established. |
| 3 | No missing/invalid organization, name lookup, Assistant, or fixture bypass | PASS | `backend/main.py`: `require_tenant` rejects missing/invalid organization context and checks membership. `backend/data.py`: application lookups and mutations include organization scope and normalized names. `backend/assistant.py` receives organization context; `backend/data.py` restricts sample fixtures to the legacy organization. |
| 4 | Frontend cannot grant membership or elevate role via the organization header | PASS | `frontend/src/main.tsx` populates the selector from the caller's memberships. `frontend/src/lib/api.ts` sends the selected organization ID, but server-side membership and roles are authoritative. Conditional transport risk is listed below. |
| 5 | Migration is explicit, transactional, backup-first, and handles duplicate names, missing owner configuration, and partial failure | NEEDS REVIEW | `backend/tenant_migration.py`: requires explicit database path and configured owner UUID, validates normalized-name uniqueness, creates/verifies backup before migration, and performs migration transactionally. Pre-commit exceptions roll back. Post-commit recovery depends on reopening the migrated database before restoration (`migrate_database` recovery path); if reopen fails, restoration is not reached. Target database, backup destination, and owner configuration were not inspected. |
| 6 | Import/startup cannot silently initialize or seed the old global schema | PASS | `backend/main.py`: provider construction is lazy. `backend/data.py`: SQLite opens in read/write-existing mode rather than silently creating a missing database. No startup migration or seed path was found in the reviewed code. |
| 7 | Authentication, JWT validation, and allowlist were not weakened | NEEDS REVIEW | The reviewed `backend/auth.py` validates issuer, audience, expiry/required claims, pins accepted algorithm, derives identity from verified token `sub`, and enforces the allowlist. Its untracked/new status means the claim that these checks were not weakened relative to an earlier version cannot be diff-verified. |
| 8 | Secrets, local environment files, and SQLite databases are not accidentally staged/tracked | PASS, with limits | Repository status showed no staged changes and no tracked paths matching environment/database/secret-file patterns. `.gitignore` excludes local `.env` files (except examples) and `backend/saasspend.db`. Untracked `.env.example` files were not opened; ignored local files were not enumerated or inspected. |

## Finding

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟡 MEDIUM | `frontend/src/lib/api.ts` | 5, 40, 47 | If `VITE_API_URL` is unset, `API_BASE` falls back to HTTP loopback while `requestApi` attaches the Supabase bearer token. A local service receiving that request could capture and replay the token. Whether a deployed build omits the variable was not verified. | 8/10 |

## Blockers before an approved migration

- Verify the approved owner UUID is configured locally and confirm it is the intended verified Supabase user. Do not infer it from the allowlist.
- Confirm the exact target database and backup destination; ensure writers are stopped and create/verify the backup before any cutover.
- Address or document the post-commit recovery gap in `backend/tenant_migration.py`: restoration currently requires successfully reopening the migrated database.
- Verify production frontend configuration supplies the intended API endpoint and HTTPS transport; the source contains an HTTP loopback fallback.
- Confirm the reviewed `backend/auth.py` is the intended auth implementation and compare it against the previously approved baseline, since it is untracked relative to `HEAD`.

No finding was fixed as part of this review.
