# Phase 1 Acceptance

Date: 2026-07-22

## Scope

Implemented only Phase 1 CAD parser and background-task reliability work:

- Background parser jobs create and close their own `AsyncSession`.
- FreeCAD subprocess concurrency is guarded by `CAD_MAX_CONCURRENCY`.
- Startup recovery marks stale `queued` / `processing` revisions as `failed` with `interrupted_by_service_restart`.
- Parser persistence writes entities, relations, meshes, and completed revision status in one transaction.
- Persistence failure rolls back parser data and then marks the revision failed in a separate transaction.
- FreeCAD parser emits `cad_parse_v2` with solid-level unique edges and vertices.
- Parser result keeps FreeCAD as the source of geometric facts.
- `backend/tests/fixtures/xms06-topology-v2-golden.json` was generated from the first real V2 parse of `XMS06-DN80.stp`; it records 80 unique edges and 46 unique vertices, not the old duplicated 126 / 160 values.

Not implemented in this phase:

- `cad_features`
- `cad_measurements`
- VLM / LLM
- `ComponentSpec`
- YAML generation
- New specification page
- MCP, Neo4j, Milvus, workflow, or V2 business integration

## Commands And Actual Output

### Install Dependencies In 3dcad

Command:

```powershell
conda run -n 3dcad python -m pip install -r backend\requirements.txt
```

Output summary:

```text
Requirement already satisfied: fastapi ...
Requirement already satisfied: uvicorn ...
Requirement already satisfied: sqlalchemy ...
Requirement already satisfied: asyncpg ...
Requirement already satisfied: pydantic ...
Requirement already satisfied: pydantic-settings ...
Requirement already satisfied: python-multipart ...
Requirement already satisfied: aiofiles ...
Requirement already satisfied: pytest ...
Requirement already satisfied: pytest-asyncio ...
Requirement already satisfied: httpx ...
```

### Focused Phase 1 Tests

Command:

```powershell
conda run -n 3dcad pytest backend/tests/test_cad_phase1_service.py backend/tests/test_cad_phase1_repository.py backend/tests/test_parse_step_v2.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 1.28s
```

### Parser Runner And V2 Parser Tests

Command:

```powershell
conda run -n 3dcad pytest backend/tests/test_parser_runner.py backend/tests/test_parse_step_v2.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 1.30s
```

### XMS06 Phase 1 Acceptance Tests

Command:

```powershell
conda run -n 3dcad pytest backend/tests/test_xms06_phase1_acceptance.py -q
```

Output:

```text
....                                                                     [100%]
4 passed in 6.97s
```

This verifies:

- `revision.face_count == face entity count == face mesh count == 38`.
- `revision.edge_count == unique edge entity count`.
- `revision.vertex_count == unique vertex entity count`.
- Every face references at least one edge.
- Every edge references at least one face and at least one vertex.
- Relations do not reference missing entities.
- Solid-local edge and vertex `source_ref` values are unique.
- Same STEP plus same revision keeps face, edge, and vertex UUIDs stable across reruns.

### Full Backend Test Suite

Command:

```powershell
cd backend
conda run -n 3dcad pytest -q
```

Output:

```text
....................................                                     [100%]
============================== warnings summary ===============================
..\..\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1
  D:\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
36 passed, 1 warning in 6.35s
```

### Real FreeCAD Integration Test With XMS06-DN80.stp

The local `.env` points `CAD_SCRIPT_DIR` at `D:\cad-service\scripts`, which contains an older parser. For this repository acceptance run, `CAD_SCRIPT_DIR` was temporarily overridden to the checked-out parser script.

Command:

```powershell
$env:CAD_SCRIPT_DIR='backend/freecad_scripts'; conda run -n 3dcad python backend\scripts\test_real_freecad.py XMS06-DN80.stp
```

Output:

```json
{
  "parser_name": "FreeCAD",
  "parser_version": "1.0.0",
  "schema_version": "cad_parse_v2",
  "summary": {
    "object_count": 1,
    "solid_count": 1,
    "face_count": 38,
    "edge_count": 80,
    "vertex_count": 46
  },
  "entity_count": 167,
  "relation_count": 372,
  "mesh_count": 38
}
```

## Initial Failed Runs

These failures were observed before implementation or environment correction:

- Running tests outside `3dcad` used the base environment and failed due to missing or mismatched dependencies. Subsequent commands used `conda run -n 3dcad`.
- The first real FreeCAD run used the older external `D:\cad-service\scripts` parser from `.env` and returned `schema_version: "1"`. Re-running with `CAD_SCRIPT_DIR=backend/freecad_scripts` verified this repository's V2 parser.

## Known Limitations

- The full backend tests emit one upstream deprecation warning from Starlette/FastAPI TestClient.
- Acceptance of this repository's parser currently depends on `CAD_SCRIPT_DIR` resolving to `backend/freecad_scripts`; local `.env` may override it.
- FreeCAD reports version `1.0.0` in this environment, so `parser_version` correctly reflects the installed FreeCAD runtime rather than the requested example version.
