# SaaSSpend
FastAPI backend + React/TypeScript/Tailwind/Recharts frontend, running on NovaLabs mock data.

## Run on Windows
```powershell
# PowerShell terminal 1, from the project folder
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
# API docs: http://localhost:8000/docs

# PowerShell terminal 2, from the project folder
cd frontend
npm.cmd install
npm.cmd run dev
# Vite: http://localhost:5173
```

In development, the frontend API client defaults to the approved loopback endpoint `http://127.0.0.1:8000`; HTTP endpoints must be explicit loopback URLs. Production builds require `VITE_API_URL` to be set to an HTTPS endpoint. The API client validates this value before attaching an access token, and the production build fails for missing, malformed, or insecure endpoint configuration. FastAPI CORS defaults to Vite loopback origins on ports 5173-5175; set `SAASSPEND_CORS_ORIGINS` to explicit comma-separated origins for other environments.

## Authentication and organizations

The frontend signs users in through Supabase Auth and sends the current access token as a bearer token. Configure `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` for the frontend, and configure `SUPABASE_URL` and `SAASSPEND_ALLOWED_USER_IDS` for the backend. The backend verifies the JWT against Supabase's JWKS, issuer, audience, expiry, and required claims, then checks the verified token subject against the allowlist. The allowlist only permits API authentication; it does not automatically grant organization membership.

After authentication, users can select only organizations returned by the backend for their verified identity. Business-data routes require an organization selector and a matching server-side membership; writes also require the role appropriate to the operation. Creating an organization makes the authenticated caller its owner. Changing a client-side organization ID or role does not grant access.

## Stage 2.1 tenant migration

The backend no longer creates or seeds the SQLite database during import or startup. Tenant API routes require a verified Supabase session, membership in the selected organization, and the role required by the operation. Set `SAASSPEND_DATABASE_PATH` only when intentionally targeting a migrated database.

Candidate preparation requires an explicitly approved Supabase user UUID in `SAASSPEND_LEGACY_OWNER_USER_ID`; it never derives the owner from `SAASSPEND_ALLOWED_USER_IDS`. It requires an explicit source database path, retains a verified pre-migration backup, and builds the tenant schema in a separate candidate database:

```powershell
cd backend
$env:SAASSPEND_LEGACY_OWNER_USER_ID = "APPROVED_SUPABASE_USER_UUID"
.\.venv\Scripts\python.exe tenant_migration.py --database "C:\path\to\disposable-copy.sqlite"
```

This command prepares but does not install a candidate database. It creates a validated `<database>.stage2.1.candidate` file (or the explicitly selected `--candidate`) from the verified backup; candidate construction or validation failures leave the source untouched. Candidate validation checks SQLite integrity, foreign keys, schema, organization and owner membership, normalized-name uniqueness, and every application field including `renewal_reviewed`. The source `applications` table must match the explicitly supported legacy column set exactly; unexpected or missing columns abort preparation before a backup or candidate is published. Preparation expects exactly eight legacy application records and assigns them to one `Legacy organization`; new organizations do not inherit those records.

Production cutover and rollback are not implemented. Do not point the running application at the candidate as a substitute for an approved cutover procedure. Any future cutover requires separate approval, a verified backup and rollback plan, stopped writers and closed connections, and explicit handling and verification of SQLite WAL/SHM sidecars.

## Prototype pages

Licenses, Renewals, Shadow IT, Access, and Security use the FastAPI endpoints backed by `MockProvider`. Shadow IT discoveries, access assignments, and security findings remain temporary in-memory sample data restricted to the legacy organization; their updates last only for the lifetime of the backend process. This prototype does not connect to vendor accounts, monitor networks or devices, synchronize an identity provider, or perform security scanning.

## Verify

```powershell
# Frontend type-check and production build
cd frontend
$env:VITE_API_URL = "https://api.example.test"
npm.cmd run build

# Backend tests use temporary databases
cd ..\backend
.\.venv\Scripts\python.exe -m unittest
```

## Swap in real integrations
`backend/data.py` defines a `Provider` protocol. `MockProvider` implements it; write `SlackProvider`, `GitHubProvider`, etc. with the same methods and change one line in `main.py`. All savings maths lives in `services.py`.
