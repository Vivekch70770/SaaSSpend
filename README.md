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

The frontend API client uses `http://127.0.0.1:8000` by default. Set `VITE_API_URL` in a frontend `.env` file to use another API base URL. FastAPI CORS permits the Vite development origins `http://localhost:5173` and `http://127.0.0.1:5173`.

## Prototype pages

Licenses, Renewals, Shadow IT, Access, and Security use the FastAPI endpoints backed by `MockProvider`. Page actions update the provider's in-memory mock state for the lifetime of the backend process. Shadow IT discoveries, access assignments, renewal costs, and security findings are illustrative sample data: this prototype does not connect to vendor accounts, monitor networks or devices, synchronize an identity provider, or perform security scanning.

## Verify

```powershell
# Frontend type-check and production build
cd frontend
npm.cmd run build

# Backend import and API smoke tests
cd ..\backend
.\.venv\Scripts\python.exe -m unittest
```

## Swap in real integrations
`backend/data.py` defines a `Provider` protocol. `MockProvider` implements it; write `SlackProvider`, `GitHubProvider`, etc. with the same methods and change one line in `main.py`. All savings maths lives in `services.py`.
