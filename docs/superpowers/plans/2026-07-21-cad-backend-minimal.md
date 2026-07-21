# STEP/CAD Backend Minimal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable FastAPI backend skeleton that can persist CAD model metadata, run a FreeCAD STEP parser, and verify parsing with `D:\3D解析\XMS06-DN80.stp`.

**Architecture:** FastAPI owns upload, job state, database access, and result persistence. FreeCAD runs only as a subprocess script that reads `job.json` and writes `result.json`; it never connects to PostgreSQL.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x async, asyncpg, Pydantic v2, pydantic-settings, pytest, pytest-asyncio.

## Global Constraints

- This is an independent project under `D:\3D解析`; do not search, modify, depend on, or copy from `raganything_reconstructure_v2`.
- Backend code lives in `backend/`, never inside `frontend/`.
- Parser verification uses `D:\3D解析\XMS06-DN80.stp`; do not generate or depend on any alternate test STEP file.
- Do not hardcode PostgreSQL passwords in source code.
- Use `SQLAlchemy URL.create` when constructing database URLs from discrete PostgreSQL settings.
- Do not use `shell=True` for FreeCAD subprocess calls.
- `.env` must be ignored by git when a git repository exists.
- First phase does not implement V2 business integration; `/exports/v2` returns 501.

---

### Task 1: Backend Configuration And Models

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/session.py`
- Create: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.database_url: str`
- Produces: `get_settings() -> Settings`
- Produces: SQLAlchemy ORM classes `CadModel`, `CadModelRevision`, `CadEntity`, `CadRelation`, `CadMesh`

- [ ] Write tests that prove database URL construction uses `URL.create` behavior and percent-encodes special characters.
- [ ] Verify the tests fail before creating production code.
- [ ] Implement settings and ORM tables.
- [ ] Run `pytest backend/tests/test_config.py -v`.

### Task 2: Parser Result Validation

**Files:**
- Create: `backend/app/cad/result_validator.py`
- Create: `backend/tests/test_result_validator.py`

**Interfaces:**
- Produces: `validate_parser_result(data: dict) -> ParserResult`
- Produces: Pydantic models for entities, relations, meshes, and summary.

- [ ] Write tests for missing required keys and a minimal valid parser result.
- [ ] Verify the tests fail.
- [ ] Implement Pydantic validation.
- [ ] Run `pytest backend/tests/test_result_validator.py -v`.

### Task 3: FreeCAD Parser Runner

**Files:**
- Create: `backend/app/cad/parser_runner.py`
- Create: `backend/tests/test_parser_runner.py`

**Interfaces:**
- Produces: `run_freecad_parser(source_file: Path, revision_id: UUID, work_dir: Path, settings: Settings) -> dict`

- [ ] Write tests that reject missing parser scripts and call subprocess without `shell=True`.
- [ ] Verify the tests fail.
- [ ] Implement job file creation, subprocess invocation, timeout handling, and result loading.
- [ ] Run `pytest backend/tests/test_parser_runner.py -v`.

### Task 4: FreeCAD Script And Real Parser Smoke Entry

**Files:**
- Create: `backend/freecad_scripts/parse_step.py`
- Create: `backend/scripts/test_real_freecad.py`

**Interfaces:**
- Produces: CLI `python backend/scripts/test_real_freecad.py D:\3D解析\XMS06-DN80.stp`

- [ ] Write tests for the smoke script command argument validation where possible without FreeCAD.
- [ ] Verify the tests fail.
- [ ] Implement a FreeCAD script that imports one STEP file and emits root/imported_object/solid/face/edge/vertex style JSON.
- [ ] Implement the smoke script with default documented sample path `D:\3D解析\XMS06-DN80.stp`.

### Task 5: FastAPI Minimal API

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/health/router.py`
- Create: `backend/app/cad/router.py`
- Create: `backend/app/cad/service.py`
- Create: `backend/app/cad/repository.py`
- Create: `backend/tests/test_cad_api.py`

**Interfaces:**
- Produces: `GET /api/health`
- Produces: `GET /api/health/database`
- Produces: `POST /api/cad/models`
- Produces: `GET /api/cad/revisions/{revision_id}/status`
- Produces: `POST /api/cad/revisions/{revision_id}/exports/v2`

- [ ] Write API tests for extension rejection, empty file rejection, accepted STP upload, status response, and V2 501 response.
- [ ] Verify the tests fail.
- [ ] Implement endpoints and in-process background task scheduling.
- [ ] Run `pytest backend/tests -v`.

### Task 6: Project Docs

**Files:**
- Create: `backend/README.md`
- Create: `backend/requirements.txt`
- Create: `backend/env.example`
- Create or modify: `.gitignore`

**Interfaces:**
- Produces documented commands for install, database initialization, backend startup, FreeCAD script install, and real parser test.

- [ ] Document the real parser command using `D:\3D解析\XMS06-DN80.stp`.
- [ ] Ensure no example STEP command appears in new backend docs.
- [ ] Run a final text scan for accidental alternate test STEP references.
