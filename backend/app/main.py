from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

DATABASE = Path(os.environ.get("MOCK_API_DATABASE", Path(__file__).parent.parent / "mock_api.db"))
ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE"}


@contextmanager
def db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, base_path TEXT NOT NULL,
          schema_json TEXT NOT NULL, owner_token TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mocks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
          method TEXT NOT NULL, path TEXT NOT NULL, response_json TEXT NOT NULL,
          status INTEGER NOT NULL, headers_json TEXT NOT NULL DEFAULT '{}',
          delay_ms INTEGER NOT NULL DEFAULT 0, UNIQUE(project_id, method, path),
          FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """)
        # Existing local databases are upgraded in place.
        columns = {column["name"] for column in conn.execute("PRAGMA table_info(mocks)")}
        if "headers_json" not in columns:
            conn.execute("ALTER TABLE mocks ADD COLUMN headers_json TEXT NOT NULL DEFAULT '{}'")
        if "delay_ms" not in columns:
            conn.execute("ALTER TABLE mocks ADD COLUMN delay_ms INTEGER NOT NULL DEFAULT 0")


class EndpointSchema(BaseModel):
    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str = Field(min_length=1)
    response: Any = {}
    status: int = Field(default=200, ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict)
    delayMs: int = Field(default=0, ge=0, le=30000)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("Path must begin with '/'")
        return value.rstrip("/") or "/"


class ProjectSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    basePath: str = "/api"
    endpoints: list[EndpointSchema] = Field(min_length=1)

    @field_validator("basePath")
    @classmethod
    def validate_base_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("basePath must begin with '/'")
        return value.rstrip("/") or "/"


class ResponseUpdate(BaseModel):
    path: str
    method: Literal["GET", "POST", "PUT", "DELETE"]
    response: Any
    status: int = Field(ge=100, le=599, default=200)
    headers: dict[str, str] = Field(default_factory=dict)
    delayMs: int = Field(default=0, ge=0, le=30000)


def get_project(project_id: str) -> sqlite3.Row:
    with db() as conn:
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def require_owner(project_id: str, x_owner_token: str | None = Header(default=None)) -> sqlite3.Row:
    project = get_project(project_id)
    if not x_owner_token or not secrets.compare_digest(project["owner_token"], x_owner_token):
        raise HTTPException(401, "A valid X-Owner-Token is required")
    return project


def write_project(schema: ProjectSchema, project_id: str | None = None, token: str | None = None) -> tuple[str, str]:
    project_id = project_id or uuid4().hex[:12]
    token = token or secrets.token_urlsafe(24)
    schema_data = schema.model_dump(mode="json")
    with db() as conn:
        conn.execute(
            "INSERT INTO projects (id,name,base_path,schema_json,owner_token,created_at) VALUES (?,?,?,?,?,?)",
            (project_id, schema.name, schema.basePath, json.dumps(schema_data), token, datetime.now(timezone.utc).isoformat()),
        )
        conn.executemany(
            "INSERT INTO mocks (project_id,method,path,response_json,status,headers_json,delay_ms) VALUES (?,?,?,?,?,?,?)",
            [(project_id, e.method, e.path, json.dumps(e.response), e.status, json.dumps(e.headers), e.delayMs) for e in schema.endpoints],
        )
    return project_id, token


app = FastAPI(title="API Mock Server", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/projects")
def list_projects() -> list[dict[str, str]]:
    with db() as conn:
        rows = conn.execute("SELECT id, name, created_at FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.post("/projects", status_code=201)
def create_project(schema: ProjectSchema, request: Request) -> dict[str, Any]:
    project_id, token = write_project(schema)
    return {"id": project_id, "ownerToken": token, "publicUrl": str(request.base_url).rstrip("/") + f"/projects/{project_id}"}


@app.get("/projects/{project_id}")
def project_detail(project_id: str) -> dict[str, Any]:
    project = get_project(project_id)
    return {"id": project["id"], "name": project["name"], "basePath": project["base_path"], "schema": json.loads(project["schema_json"]), "createdAt": project["created_at"]}


@app.post("/projects/{project_id}/clone", status_code=201)
def clone_project(project_id: str, request: Request, _: sqlite3.Row = Depends(require_owner)) -> dict[str, Any]:
    original = get_project(project_id)
    schema = ProjectSchema.model_validate(json.loads(original["schema_json"]))
    schema.name = f"{schema.name} (copy)"
    new_id, token = write_project(schema)
    return {"id": new_id, "ownerToken": token, "publicUrl": str(request.base_url).rstrip("/") + f"/projects/{new_id}"}


@app.put("/projects/{project_id}/mocks")
def update_mock(project_id: str, update: ResponseUpdate, _: sqlite3.Row = Depends(require_owner)) -> dict[str, str]:
    with db() as conn:
        result = conn.execute(
            "UPDATE mocks SET response_json=?, status=?, headers_json=?, delay_ms=? WHERE project_id=? AND method=? AND path=?",
            (json.dumps(update.response), update.status, json.dumps(update.headers), update.delayMs, project_id, update.method, update.path),
        )
        if result.rowcount:
            project = conn.execute("SELECT schema_json FROM projects WHERE id=?", (project_id,)).fetchone()
            schema = json.loads(project["schema_json"])
            for endpoint in schema["endpoints"]:
                if endpoint["method"] == update.method and endpoint["path"] == update.path:
                    endpoint.update(update.model_dump(mode="json"))
                    break
            conn.execute("UPDATE projects SET schema_json=? WHERE id=?", (json.dumps(schema), project_id))
    if not result.rowcount:
        raise HTTPException(404, "Mock endpoint not found")
    return {"message": "Mock response updated"}


@app.get("/projects/{project_id}/openapi.json")
def project_openapi(project_id: str, request: Request) -> dict[str, Any]:
    project = get_project(project_id)
    schema = json.loads(project["schema_json"])
    paths: dict[str, Any] = {}
    for endpoint in schema["endpoints"]:
        path = schema["basePath"] + endpoint["path"]
        paths.setdefault(path, {})[endpoint["method"].lower()] = {
            "summary": f"Mock {endpoint['method']} {endpoint['path']}",
            "responses": {str(endpoint["status"]): {"description": "Configured mock response", "content": {"application/json": {"example": endpoint["response"]}}}},
        }
    public = str(request.base_url).rstrip("/") + f"/projects/{project_id}"
    return {"openapi": "3.0.3", "info": {"title": project["name"], "version": "1.0.0"}, "servers": [{"url": public}], "paths": paths}


@app.get("/projects/{project_id}/docs", include_in_schema=False)
def project_docs(project_id: str):
    get_project(project_id)
    return get_swagger_ui_html(openapi_url=f"/projects/{project_id}/openapi.json", title="Mock API Docs")


@app.api_route("/projects/{project_id}/{requested_path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def serve_mock(project_id: str, requested_path: str, request: Request) -> JSONResponse:
    project = get_project(project_id)
    full_path = "/" + requested_path
    base_path = project["base_path"]
    if base_path != "/" and full_path.startswith(base_path):
        endpoint_path = full_path[len(base_path):] or "/"
    elif base_path == "/":
        endpoint_path = full_path
    else:
        raise HTTPException(404, "Mock endpoint not found")
    with db() as conn:
        mock = conn.execute("SELECT response_json,status,headers_json,delay_ms FROM mocks WHERE project_id=? AND method=? AND path=?", (project_id, request.method, endpoint_path)).fetchone()
    if not mock:
        raise HTTPException(404, "Mock endpoint not found")
    if mock["delay_ms"]:
        time.sleep(mock["delay_ms"] / 1000)
    return JSONResponse(content=json.loads(mock["response_json"]), status_code=mock["status"], headers=json.loads(mock["headers_json"]))
