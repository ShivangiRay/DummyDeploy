# API Playground with Live Mock Server

MockForge is a full-stack developer tool for defining, publishing, testing, and sharing API mocks. Write a small JSON schema, deploy it, and immediately call the generated endpoints or inspect them in Swagger UI.

## What it includes

- Monaco-powered JSON schema editor with client-side validation
- Endpoint sidebar generated from the schema
- HTTP playground with methods, headers, request body, response metadata, and request history
- SQLite-backed FastAPI mock server
- Public runtime routes for `GET`, `POST`, `PUT`, and `DELETE`
- Generated OpenAPI JSON and project-specific Swagger UI
- Deploy, clone, and clipboard sharing controls
- Owner-token protection for mock-data updates and cloning; public mock routes stay callable by anyone
- Responsive Tailwind interface and a dashboard of created projects

## Project layout

```text
frontend/  Next.js 14 + TypeScript + Tailwind + Monaco
backend/   FastAPI + SQLite dynamic mock service
```

## Run locally

Prerequisites: Node.js 18+ and Python 3.11+ (Python 3.14 is supported with the current dependency ranges).

```bash
# Terminal 1 — API server
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 — web app
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Set `NEXT_PUBLIC_API_URL` if the FastAPI service is hosted somewhere other than `http://localhost:8000`.

## Example schema

```json
{
  "name": "User Service",
  "basePath": "/api",
  "endpoints": [
    { "method": "GET", "path": "/users", "response": { "data": [] }, "status": 200 },
    { "method": "POST", "path": "/users", "response": { "id": 1, "name": "John" }, "status": 201 }
  ]
}
```

After deployment, a project with ID `{projectId}` exposes:

- `GET /projects/{projectId}/api/users` — public mock route
- `GET /projects/{projectId}/openapi.json` — generated OpenAPI document
- `GET /projects/{projectId}/docs` — Swagger UI
- `PUT /projects/{projectId}/mocks` — update a mock response, authenticated with `X-Owner-Token`

The `POST /projects` response includes the `ownerToken`. Keep it private: it authorizes mutable operations for that project.
