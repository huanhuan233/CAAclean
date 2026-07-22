# Phase 5 Acceptance

Date: 2026-07-22

## Scope

Implemented a first-pass Component Spec review UI for Phase 4 Drawing Facts.

This phase includes:

- A new first-level route: `/cad-spec?revision_id=...`
- A new first-level menu item: `组件规范`
- A `生成组件规范` entry from the existing CAD model page
- Uploading a 2D drawing image
- Entering `target_code` and `target_dn`
- Creating a spec task
- Running layout detection and extraction through Phase 4 APIs
- Viewing task status
- Viewing product facts, target row facts, all Drawing Facts, and raw VLM JSON
- Clicking a fact to highlight `source_bbox_original` on the drawing image
- Zoom, pan, and fit-to-window controls
- Re-extracting after changing target code or DN

Not implemented in this phase:

- STEP dimension mapping
- YAML generation
- LLM calls
- Profile or ComponentSpec finalization

## Files

New files:

- `frontend/src/views/cad-spec/index.vue`
- `docs/acceptance/phase-5.md`

Modified files:

- `frontend/src/views/cad-model/index.vue`
- `frontend/src/service/api/cad.ts`
- `frontend/src/typings/api/cad.d.ts`
- `frontend/src/router/routes/index.ts`
- `frontend/src/router/elegant/imports.ts`
- `frontend/src/router/elegant/routes.ts`
- `frontend/src/router/elegant/transform.ts`
- `frontend/src/typings/elegant-router.d.ts`
- `frontend/src/typings/components.d.ts`
- `frontend/src/locales/langs/zh-cn.ts`
- `frontend/src/locales/langs/en-us.ts`

## Behavior Notes

- The existing CAD model page is preserved. The new button only navigates to `/cad-spec` and passes the current `revision_id`.
- The new page does not display server absolute paths. Drawing images are loaded from API URLs such as `/api/cad/spec/tasks/{task_id}/drawing/image`.
- The page does not display image Base64.
- Re-extraction clears the previous selected fact, previous result JSON, and previous facts before calling the extraction API with the new target.
- If Phase 4B provides row-level evidence, the UI highlights the row-level bbox and labels its precision as `row`. It does not mark row-level evidence as `cell`.
- `POST /layout` and `POST /extract` now return `202` after scheduling backend work; the UI polls status instead of waiting on long-running requests, avoiding the frontend 10 second request timeout.
- Vision layout image scanning runs in a worker thread so the background layout job does not block `/layout/status` polling.

## Verification

The local `pnpm` shim on PATH was bound to a Node 16 runtime even though the shell also had Node 20. The scripts were run through the same pnpm/corepack entry with an explicit Node 20 executable:

```powershell
C:\Users\pxy06\AppData\Local\fnm_multishells\2824_1784695643479\node.exe C:\Users\pxy06\AppData\Local\fnm_multishells\23036_1784515735199\node_modules\corepack\dist\pnpm.js typecheck
```

Actual output:

```text
> @sa/elp@1.4.0 typecheck D:\3D解析\frontend
> vue-tsc --noEmit --skipLibCheck

Using Node v20.20.2
```

Command:

```powershell
C:\Users\pxy06\AppData\Local\fnm_multishells\2824_1784695643479\node.exe C:\Users\pxy06\AppData\Local\fnm_multishells\23036_1784515735199\node_modules\corepack\dist\pnpm.js lint
```

Actual output:

```text
> @sa/elp@1.4.0 lint D:\3D解析\frontend
> eslint . --fix

Using Node v20.20.2
```

Command:

```powershell
C:\Users\pxy06\AppData\Local\fnm_multishells\2824_1784695643479\node.exe C:\Users\pxy06\AppData\Local\fnm_multishells\23036_1784515735199\node_modules\corepack\dist\pnpm.js build
```

Actual output:

```text
> @sa/elp@1.4.0 build D:\3D解析\frontend
> vite build --mode prod

> @sa/elp@1.4.0 postbuild D:\3D解析\frontend
> sa print-soybean

Build successful. Please see dist directory
```

Backend regression command:

```powershell
cd backend
conda run -n 3dcad pytest -q
```

Actual output:

```text
........................................................................ [ 96%]
...                                                                      [100%]
============================== warnings summary ===============================
..\..\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1
  D:\anaconda\envs\3dcad\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
78 passed, 1 warning in 12.40s
```

## Known Limits

- The page depends on Phase 4B evidence precision. If the model/result only supplies row-level bbox for `D` or `K`, the UI highlights that row-level bbox. Cell-level highlighting will appear automatically when the fact has a cell-level `source_bbox_original`.
