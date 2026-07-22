# Phase 4B Acceptance

Date: 2026-07-22

## Scope

Implemented DrawingCropPackage-based structured drawing fact extraction.

This phase includes:

- Vision-only extraction client using `AsyncOpenAI`
- Vision health check
- Four staged VLM subtasks: product information, parameter table, symbol definitions, target row verification
- Strict Pydantic schemas for staged results, drawing facts, and final extraction result
- JSON parsing, Markdown-wrapped JSON recovery, schema validation, retry handling, and response_format fallback
- Crop-local bbox to original-image bbox mapping
- PostgreSQL persistence for `cad_drawing_facts`
- Extraction task status/progress APIs
- Idempotent replacement of current facts on re-extraction

Not implemented in this phase:

- STEP measurement mapping
- Flange profile mapping
- YAML generation
- PASS/FAIL compliance judgment
- LLM text completion
- ComponentSpec finalize

## Files

New files:

- `backend/app/drawing/extraction_client.py`
- `backend/app/drawing/extraction_repository.py`
- `backend/app/drawing/extraction_schemas.py`
- `backend/app/drawing/extraction_service.py`
- `backend/app/drawing/extraction_utils.py`
- `backend/tests/test_drawing_extraction_phase4b.py`
- `docs/acceptance/phase-4B-xms06-result.json`
- `docs/acceptance/phase-4B-xms06-evidence.png`

Modified files:

- `backend/app/core/config.py`
- `backend/app/db/models.py`
- `backend/app/drawing/router.py`
- `backend/app/drawing/service.py`

## Vision Configuration

The real acceptance run used the configured Vision endpoint:

- `VISION_BINDING=openai`
- `VISION_MODEL=/mnt/model/Qwen`
- `VISION_BINDING_HOST=http://192.168.0.91:8080/v1`
- `VISION_ENABLE_THINKING=false`
- `VISION_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}`
- `AI_REQUEST_TIMEOUT=600`
- `AI_MAX_RETRIES=2`

The extraction path uses the Vision configuration only. It does not call `LLM_BINDING_HOST` or `LLM_MODEL`.

API key values and image Base64 payloads are not written to logs.

## API

Added:

- `POST /api/cad/spec/tasks/{task_id}/extract`
- `GET /api/cad/spec/tasks/{task_id}/extraction/status`
- `GET /api/cad/spec/tasks/{task_id}/extraction`
- `GET /api/cad/spec/tasks/{task_id}/facts`
- `POST /api/cad/spec/tasks/{task_id}/extract/retry`

GET requests do not trigger model calls.

## Real XMS06 Run

Input:

- STEP revision: `7332d95f-eb0f-4be3-9454-5afde66dc9b0`
- Drawing task: `263cc93f-83a9-4152-88ed-361e220e4373`
- `target_code=XMS06`
- `target_dn=80`

Artifacts:

- Result JSON: `docs/acceptance/phase-4B-xms06-result.json`
- Evidence image: `docs/acceptance/phase-4B-xms06-evidence.png`

Extraction result:

- `matched_code`: `XMS06`
- `matched_dn`: `80`
- `selection_confidence`: `0.95`
- `needs_review`: `true`

Known review warning:

- The model reported that the table visually groups `XMS05` and `XMS06` together. The selected target row is `DN80`, and the persisted target facts are taken from that DN80 row only.

## Extracted Product Facts

```text
product.component_code      raw=XMS06                normalized=XMS06
product.component_type_raw  raw=带颈对焊             normalized=带颈对焊
product.facing_type         raw=RF                   normalized=RF
product.material            raw=SUS316               normalized=SUS316
product.pressure_class      raw=PN16                 normalized=PN16
product.standard_number     raw=HG/T 20592-2009      normalized=HG/T 20592-2009
product.series              raw=B                    normalized=B
```

`PN16` remains categorical text. It is not converted to MPa.

## Extracted Target Row Facts

```text
dimension.A1        raw=89       normalized=89.0     operator=eq
dimension.D         raw=200      normalized=200.0    operator=eq
dimension.K         raw=160      normalized=160.0    operator=eq
dimension.L         raw=18       normalized=18.0     operator=eq
dimension.n         raw=8        normalized=8.0      operator=eq
dimension.适用螺栓  raw=M16      normalized=M16      operator=categorical
dimension.C         raw=20       normalized=20.0     operator=eq
dimension.N         raw=105      normalized=105.0    operator=eq
dimension.S         raw=≥3.2     normalized=3.2      operator=gte
dimension.H1        raw=≈10      normalized=10.0     operator=approx
dimension.R         raw=6        normalized=6.0      operator=eq
dimension.H         raw=50       normalized=50.0     operator=eq
dimension.d         raw=138      normalized=138.0    operator=eq
dimension.f1        raw=2        normalized=2.0      operator=eq
```

Each target dimension fact has:

- `source_region_id`
- `raw_value`
- `normalized_value`
- `confidence`
- `source_bbox_original`
- `source_bbox_precision=row`

No target dimension fact is marked as `cell` precision when only row-level evidence is available.

## Evidence Image

`docs/acceptance/phase-4B-xms06-evidence.png` includes boxes for:

- `product_information` region
- `parameter_table` region
- `XMS06-DN80` target row
- `D=200`
- `K=160`
- `L=18`
- `n=8`

## Forbidden Output Check

Command:

```powershell
conda run -n 3dcad python -c "import json; from pathlib import Path; p=Path('docs/acceptance/phase-4B-xms06-result.json'); data=json.loads(p.read_text(encoding='utf-8')); text=p.read_text(encoding='utf-8'); forbidden=['flange_outer_diameter','bolt_circle_diameter','candidate_yaml','validation_status','STEP measured_value','16 MPa']; print('forbidden_present', [x for x in forbidden if x in text]); tr=data['target_row']; print('target', tr['matched_code'], tr['matched_dn'], tr['needs_review'], tr['selection_confidence']); print('fact_count', len(data['facts']))"
```

Actual output:

```text
forbidden_present []
target XMS06 80 True 0.95
fact_count 21
```

The complete parameter table result retains surrounding table context, including adjacent DN rows. The target row result and persisted facts select `DN80` only.

## Tests

Command:

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
75 passed, 1 warning in 41.13s
```

## Known Limits

- The real model returned row-level evidence for the target dimensions, not precise cell boxes, so target dimension facts are correctly marked as `source_bbox_precision=row`.
- Product information facts use region-level evidence and are marked `needs_review=true`.
- The table image groups `XMS05` and `XMS06`; the extraction records this as a warning while selecting the requested `XMS06/DN80` target row.
