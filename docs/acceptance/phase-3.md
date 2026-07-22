# Phase 3 Acceptance

Date: 2026-07-22

## Scope

Implemented the Phase 2 measurement result API and evidence display in the existing CAD page.

Implemented API:

- `GET /api/cad/revisions/{revision_id}/measurements`
- `GET /api/cad/revisions/{revision_id}/measurements/{measurement_id}`
- `GET /api/cad/revisions/{revision_id}/features`
- `GET /api/cad/revisions/{revision_id}/features/{feature_id}`
- `POST /api/cad/revisions/{revision_id}/measurements/recompute`

Supported filters:

- `measurement_type`
- `feature_type`
- `scope_entity_id`
- `confidence_min`
- `page`
- `page_size`

Implemented on the existing CAD page:

- Added Dimensions and Features tabs beside Face / Edge / Vertex.
- Added measurement list fields: type, normalized value, unit, confidence, algorithm version.
- Selecting a measurement highlights source Face evidence where source entities resolve to faces.
- Selecting a circular pattern highlights member source faces and displays count, member diameter, PCD, angle spacing, residual, and parameters.
- Viewer accepts optional circular-pattern evidence and draws a PCD helper circle plus main-axis helper line.
- Switching model, tree node, face, edge, vertex, measurement, or feature clears stale selection, highlight, and evidence state.
- Viewer uses `ResizeObserver`, so folding either side panel triggers canvas resize through the existing viewer resize path.
- Fixed recompute persistence after SQLAlchemy read autobegin so `POST /measurements/recompute` does not fail with a nested transaction error.

Not implemented in this phase:

- 2D drawings
- VLM
- LLM
- YAML
- ComponentSpec fields

## Commands And Actual Output

### Backend API And Regression Tests

Command:

```powershell
cd backend
conda run -n 3dcad pytest -q
```

Output:

```text
...............................................                          [100%]
============================== warnings summary ===============================
..\..\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1
  D:\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
47 passed, 1 warning in 7.74s
```

### Frontend Verification

The default shell had a stale `pnpm.cmd` bound to Node v16.20.2. For the required `pnpm ...` commands, I prepended a temporary `pnpm.cmd` wrapper that invokes the same pnpm entrypoint with Node v20.20.2, so the command names below are the commands that were run.

Command:

```powershell
cd frontend
$wrapper = Join-Path $env:TEMP 'codex-node20-pnpm'
$env:PATH = "$wrapper;C:\Users\pxy06\AppData\Local\fnm_multishells\28460_1784684108654;" + $env:PATH
pnpm typecheck
```

Output:

```text
> @sa/elp@1.4.0 typecheck <workspace>\frontend
> vue-tsc --noEmit --skipLibCheck

Using Node v20.20.2
```

Exit code: `0`.

Command:

```powershell
pnpm lint
```

Output:

```text
> @sa/elp@1.4.0 lint <workspace>\frontend
> eslint . --fix

Using Node v20.20.2
```

Exit code: `0`.

Command:

```powershell
pnpm build
```

Output:

```text
> @sa/elp@1.4.0 build <workspace>\frontend
> vite build --mode prod

> @sa/elp@1.4.0 postbuild <workspace>\frontend
> sa print-soybean

Build successful. Please see dist directory
Using Node v20.20.2
```

Exit code: `0`.

## Known Limitations

- The viewer highlights evidence Face meshes. When a measurement source is an Edge, the page resolves related faces through the existing edge topology endpoint.
- PCD helper rendering uses the feature's `center`, `axis`, and `pitch_circle_diameter` parameters.
- The backend suite still emits the existing FastAPI/Starlette TestClient warning.
