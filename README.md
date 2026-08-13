# API Playground with Live Mock Server

MockForge is a full-stack developer tool for defining, publishing, testing, and sharing API mocks. Write a small JSON schema, deploy it, and immediately call the generated endpoints or inspect them in Swagger UI.

## What it includes

- Monaco-powered JSON schema editor with client-side validation
- Endpoint sidebar generated from the schema
- HTTP playground with methods, headers, request body, response metadata, and request history
- SQLite-backed FastAPI mock server
- Public runtime routes for `GET`, `POST`, `PUT`, and `DELETE`
- Generated OpenAPI JSON and project-specific Swagger UI
- Deploy, clone, reload, and clipboard sharing controls
- Owner-token protection for mock-data updates and cloning; public mock routes stay callable by anyone
- Per-endpoint response editor for JSON payloads, status codes, headers, and simulated latency
- Responsive Tailwind interface and a dashboard of created projects

## Project layout

```text
frontend/  Next.js 14 + TypeScript + Tailwind + Monaco
backend/   FastAPI + SQLite dynamic mock service
```

## Run locally

Prerequisites: Node.js 18+ and Python 3.11+ (Python 3.14 is supported with the current dependency ranges).

From the repository root, open **two terminals**. Do not run both servers in the same terminal.

```bash
# Terminal 1 — FastAPI mock server
cd /Users/shivangi/Documents/GitProjects/DummyDeploy/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2 — Next.js web app
cd /Users/shivangi/Documents/GitProjects/DummyDeploy/frontend
npm install
npm run dev
```

When both commands are running, open [http://localhost:3000](http://localhost:3000). The frontend expects the API server at `http://localhost:8000`; set `NEXT_PUBLIC_API_URL` before `npm run dev` only if the API runs elsewhere.

## Quick test

1. Open `http://localhost:3000` and keep the sample schema.
2. Click **Deploy**. The app creates a project and fills the Playground URL.
3. Select **Playground**, choose `GET`, and click **Send**.
4. Confirm the response has status `200` and body:

```json
{"data": []}
```

To test the deployed API outside the browser, copy the project ID from the deploy message and run:

```bash
curl http://localhost:8000/projects/PROJECT_ID/api/users
```

The generated Swagger UI is available at:

```text
http://localhost:8000/projects/PROJECT_ID/docs
```

To test the sample `POST /users` endpoint:

```bash
curl -X POST http://localhost:8000/projects/PROJECT_ID/api/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Ada"}'
```

Mock responses are configured by the schema. Request bodies are accepted but do not change which response the server returns.

## Editing a deployed mock

Choose an endpoint in the sidebar and open **Playground**. Owners can use the **Mock response** panel to update the response JSON, status code, response headers, and an optional delay (up to 30 seconds), then save without redeploying. The updated settings are served immediately and are reflected in the generated OpenAPI document.

Owner tokens are saved only in the browser's local storage. Loading a project created in another browser remains public for testing and documentation, but editing and cloning require its original owner token.

## Example schema

```json
{
  "name": "User Service",
  "basePath": "/api",
  "endpoints": [
    { "method": "GET", "path": "/users", "response": { "data": [] }, "status": 200, "headers": { "X-Mock-Source": "MockForge" }, "delayMs": 0 },
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
