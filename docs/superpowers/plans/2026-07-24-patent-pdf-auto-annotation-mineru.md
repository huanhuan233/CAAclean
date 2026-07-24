# MinerU PDF Patent Auto-Annotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real current-page PDF auto-annotation workflow that parses a patent specification through MinerU with pypdf fallback, localizes visible parts through the existing vision client, and creates reviewable editable leaders in the existing patent annotation editor.

**Architecture:** Extract the existing MinerU transport and vision-client factory into shared core modules, then keep patent text parsing, image preparation, localization, and HTTP contracts inside a focused `app.patent_annotation` package. Upgrade the frontend draft schema compatibly to 0.2, expose the rendered PDF canvas, and orchestrate parsing/localization through a small composable and compact UI panel while continuing to use the existing store, inspector, and SVG overlay.

**Tech Stack:** Python 3.11 in conda environment `3dcad`, FastAPI, Pydantic v2, pypdf 5.x, Pillow, pytest/pytest-asyncio, Vue 3, TypeScript, Element Plus, vue-pdf-embed, Node.js 20, Node test runner.

## Global Constraints

- Work directly on `main`; do not reset, overwrite, or recreate the existing STEP/PDF manual annotation editor.
- Frontend commands must use Node.js 20.
- Backend and backend tests must run after `conda activate 3dcad`.
- Reuse `VisionJsonClient.complete_json(...)`; do not add another OpenAI-compatible HTTP client.
- Reuse `MINERU_LAYOUT_MODE`, `MINERU_LAYOUT_URL`, `MINERU_LAYOUT_COMMAND`, and `MINERU_LAYOUT_TIMEOUT`; do not create duplicate MinerU settings.
- Add only `pypdf>=5,<6`; do not add PyTorch, Grounding DINO, SAM, GPU services, a database table, or a task queue.
- Accept patent specification PDF only; do not implement DOC/DOCX or OCR in this phase.
- Parse-document uploads are limited to 30 MB; localization images are limited to 20 MB and PNG/JPG/WEBP.
- Server-side uploads live only inside request-scoped temporary directories and are always cleaned.
- Do not hard-code sample patent filenames, expected ref-number sets, or coordinates in product code.
- Re-running current-page auto annotation may replace only old automatic annotations; it must never remove manual annotations.
- Continue importing schema 0.1 drafts and migrate them to schema 0.2.
- Do not run repository-wide `lint --fix`.

---

## File Structure

### Backend

- Create `backend/app/core/mineru.py`: generic configured MinerU payload client.
- Create `backend/app/core/vision.py`: shared `build_vision_client(settings)` factory.
- Modify `backend/app/drawing/providers.py`: delegate MinerU transport to the shared client without changing provider behavior.
- Modify `backend/app/drawing/router.py`: import the shared vision factory.
- Create `backend/app/patent_annotation/__init__.py`: package marker.
- Create `backend/app/patent_annotation/errors.py`: stable patent error code/message exception.
- Create `backend/app/patent_annotation/schemas.py`: document, model-localization, and normalized API models.
- Create `backend/app/patent_annotation/document_parser.py`: MinerU/pypdf normalization and deterministic patent structure extraction.
- Create `backend/app/patent_annotation/image_utils.py`: clean and coordinate-grid image generation.
- Create `backend/app/patent_annotation/localization.py`: prompt, batching, vision calls, normalization, and merge rules.
- Create `backend/app/patent_annotation/router.py`: multipart endpoints and dependency factories.
- Modify `backend/app/main.py`: include the patent annotation router.
- Modify `backend/requirements.txt`: add bounded pypdf dependency.
- Create `backend/tests/test_patent_document_parser.py`.
- Create `backend/tests/test_patent_localization.py`.
- Create `backend/tests/test_patent_annotation_router.py`.
- Modify `backend/tests/test_drawing_phase4a.py`: shared MinerU regression coverage.

### Frontend

- Create `frontend/src/typings/api/patent-annotation.d.ts`: API namespace.
- Create `frontend/src/service/api/patent-annotation.ts`: multipart request functions.
- Modify `frontend/src/service/api/index.ts`: export the API.
- Modify `frontend/src/views/patent-annotation/types.ts`: schema 0.2 automation fields.
- Modify `frontend/src/views/patent-annotation/geometry.ts`: normalize 0.1/0.2 and automation fields.
- Modify `frontend/src/views/patent-annotation/composables/usePatentAnnotations.ts`: migration, mapping, automatic replacement, and acceptance semantics.
- Create `frontend/src/views/patent-annotation/auto-annotation.ts`: ink snapping, label layout, and default mapping pure functions.
- Create `frontend/src/views/patent-annotation/composables/usePatentAutoAnnotation.ts`: workflow orchestration.
- Create `frontend/src/views/patent-annotation/modules/AutoAnnotationPanel.vue`: compact parsing/mapping/candidate UI.
- Modify `frontend/src/views/patent-annotation/modules/PdfAnnotationWorkspace.vue`: expose current-page PNG/ImageData.
- Modify `frontend/src/views/patent-annotation/modules/AnnotationInspector.vue`: origin/confidence/review UI.
- Modify `frontend/src/views/patent-annotation/modules/LeaderOverlay.vue`: left/right SVG text anchoring and reviewed drag behavior.
- Modify `frontend/src/views/patent-annotation/index.vue`: integrate the panel and workflow in PDF mode.
- Modify `frontend/src/views/patent-annotation/__tests__/annotations.test.ts`.
- Modify `frontend/src/views/patent-annotation/__tests__/geometry.test.ts`.
- Create `frontend/src/views/patent-annotation/__tests__/auto-annotation.test.ts`.
- Modify `frontend/package.json`: include the new test file in `test:patent-annotation`.

---

### Task 1: Share MinerU and vision infrastructure

**Files:**
- Create: `backend/app/core/mineru.py`
- Create: `backend/app/core/vision.py`
- Modify: `backend/app/drawing/providers.py`
- Modify: `backend/app/drawing/router.py`
- Modify: `backend/tests/test_drawing_phase4a.py`

**Interfaces:**
- Produces: `MineruClient(mode, url, command, timeout, transport=None).fetch_payload(path: Path) -> dict`
- Produces: `build_vision_client(settings: Settings) -> VisionJsonClient`
- Preserves: `MineruLayoutProvider(...).detect(path) -> LayoutDetectionResult`

- [ ] **Step 1: Add failing shared-client regression tests**

Add tests proving that the layout provider delegates one path to a transport, timeout becomes `mineru_timeout`, and `build_vision_client` preserves model/extra-body configuration:

```python
@pytest.mark.asyncio
async def test_mineru_layout_uses_shared_payload_client(tmp_path):
    seen = []

    async def transport(path):
        seen.append(path)
        return {"regions": [{"type": "table", "bbox": [1, 2, 30, 40]}]}

    image = make_image(tmp_path / "drawing.png")
    result = await MineruLayoutProvider(mode="http", transport=transport).detect(image)
    assert seen == [image]
    assert result.provider == "mineru"
```

- [ ] **Step 2: Run the focused Drawing tests and verify the new import fails**

Run:

```powershell
. D:\anaconda\shell\condabin\conda-hook.ps1
conda activate 3dcad
python -m pytest backend/tests/test_drawing_phase4a.py -q --basetemp D:\3D解析\.pytest_tmp\drawing-shared
```

Expected: FAIL because `app.core.mineru` and `app.core.vision` do not exist.

- [ ] **Step 3: Implement `MineruClient`**

Implement these exact behaviors:

```python
class MineruClient:
    def __init__(self, *, mode="disabled", url=None, command=None, timeout=180, transport=None): ...

    async def fetch_payload(self, input_path: Path) -> dict:
        if self.mode == "disabled":
            raise MineruError("mineru_not_configured", "MinerU provider is disabled")
        # transport -> HTTP raw bytes -> command path, all under timeout
        # JSON object required; timeout/connection/invalid result receive stable codes
```

Use `asyncio.to_thread` for urllib and `asyncio.create_subprocess_exec` for command mode. Do not use `shell=True`.

- [ ] **Step 4: Delegate `MineruLayoutProvider` to the shared client**

Keep the existing constructor compatible, construct `MineruClient`, call `fetch_payload`, translate `MineruError` to `DrawingError`, then pass the payload to `_parse_provider_payload`.

- [ ] **Step 5: Move the vision factory**

Move the exact JSON parsing and `enable_thinking=False` merge from `drawing/router.py` into:

```python
def build_vision_client(settings: Settings) -> VisionJsonClient:
    ...
```

Import it back into Drawing router so existing endpoints do not change.

- [ ] **Step 6: Run Drawing regression tests**

Run the focused command from Step 2. Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/core/mineru.py backend/app/core/vision.py backend/app/drawing/providers.py backend/app/drawing/router.py backend/tests/test_drawing_phase4a.py
git commit --no-verify -m "refactor: share MinerU and vision clients"
```

### Task 2: Define patent schemas and deterministic structure extraction

**Files:**
- Create: `backend/app/patent_annotation/__init__.py`
- Create: `backend/app/patent_annotation/errors.py`
- Create: `backend/app/patent_annotation/schemas.py`
- Create: `backend/app/patent_annotation/document_parser.py`
- Create: `backend/tests/test_patent_document_parser.py`

**Interfaces:**
- Produces: `PatentAnnotationError(code: str, message: str)`
- Produces: `parse_patent_structure(content: PatentDocumentContent, file_name: str) -> PatentDocumentParseResult`
- Produces schemas named in the approved design, including `parser: Literal["mineru", "pypdf"]`

- [ ] **Step 1: Write failing parser tests**

Use the approved Chinese fixture and assert:

```python
result = parse_patent_structure(
    PatentDocumentContent(
        pages=[PatentDocumentPage(page_no=1, text=PATENT_TEXT, parser="pypdf")],
        full_text=PATENT_TEXT,
        parser="pypdf",
    ),
    file_name="sample.pdf",
)
assert [item.ref_no for item in result.components] == ["1", "2", "61", "68"]
assert [item.figure_no for item in result.figures] == ["1", "2", "4"]
assert result.figures[-1].explicit_ref_nos == ["68"]
assert result.figures[-1].detail_markers[0].marker == "A"
assert result.figures[-1].detail_markers[0].parent_figure_no == "3"
```

Add separate tests for `名称（编号）`, cross-page “附图说明”/“图中：”, stable candidate order, and exclusion of claim sequence numbers.

- [ ] **Step 2: Run the parser test and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_patent_document_parser.py -q --basetemp D:\3D解析\.pytest_tmp\patent-parser
```

Expected: import failure for the missing package.

- [ ] **Step 3: Implement Pydantic models and error type**

Use `Field(default_factory=list)` for every list. Define:

```python
class PatentDocumentPage(BaseModel):
    page_no: int = Field(ge=1)
    text: str
    markdown: str | None = None
    image_refs: list[str] = Field(default_factory=list)
    parser: Literal["mineru", "pypdf"]

class PatentDocumentContent(BaseModel):
    pages: list[PatentDocumentPage]
    full_text: str
    parser: Literal["mineru", "pypdf"]
    warnings: list[str] = Field(default_factory=list)
```

Define component, detail marker, figure, parse result, raw model point/box/item/output, normalized point/box/item/result, and localization candidate schemas.

- [ ] **Step 4: Implement text normalization and component extraction**

Implement pure helpers:

```python
def normalize_match_text(text: str) -> str: ...
def extract_components(text: str) -> list[PatentComponent]: ...
def extract_figures(text: str, components: list[PatentComponent]) -> list[PatentFigure]: ...
```

The legend regex accepts `； ; 。`, identifiers `A`, `1`, `61`, `1a`, and separators `、 , ， . ．`. Stop at “具体实施方式” or another known section heading. Parenthetical fallback fills only missing ref numbers.

- [ ] **Step 5: Implement context and detail-marker extraction**

Collect paragraphs that mention each `图N`, cap joined context at 4000 characters, find explicit refs only when paired with known names/numbers, and build candidate refs as explicit first followed by known component order.

Recognize both `图4为...图3中A处放大...` and whitespace variants. Attach the marker to the detail figure and do not add `A` to components.

- [ ] **Step 6: Run parser tests**

Run the command from Step 2. Expected: all structure tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/patent_annotation backend/tests/test_patent_document_parser.py
git commit --no-verify -m "feat: extract patent figures and components"
```

### Task 3: Implement MinerU-first PDF parsing with pypdf fallback

**Files:**
- Modify: `backend/app/patent_annotation/document_parser.py`
- Modify: `backend/tests/test_patent_document_parser.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces: `PatentDocumentParser(mineru_client=None).parse(pdf_path: Path, *, file_name: str, fast: bool = False) -> PatentDocumentParseResult`
- Consumes: `MineruClient.fetch_payload(path) -> dict`

- [ ] **Step 1: Add failing double-parser tests**

Cover:

```python
@pytest.mark.asyncio
async def test_mineru_success_reports_parser(tmp_path):
    parser = PatentDocumentParser(mineru_client=FakeMineru({"pages": [{"page_no": 1, "text": PATENT_TEXT}]}))
    result = await parser.parse(make_text_pdf(tmp_path), file_name="sample.pdf")
    assert result.parser == "mineru"

@pytest.mark.asyncio
async def test_mineru_timeout_falls_back_to_pypdf(tmp_path):
    parser = PatentDocumentParser(mineru_client=FailingMineru("mineru_timeout"))
    result = await parser.parse(make_text_pdf(tmp_path), file_name="sample.pdf")
    assert result.parser == "pypdf"
    assert "mineru_timeout" in result.warnings
```

Also test fast mode skips MinerU, flexible nested MinerU payload normalization, empty MinerU plus text PDF fallback, and both parsers empty raising `patent_document_no_text`.

- [ ] **Step 2: Run and verify RED**

Run the Task 2 parser command. Expected: missing `PatentDocumentParser` behavior.

- [ ] **Step 3: Add `pypdf>=5,<6`**

Append exactly one bounded dependency line to `backend/requirements.txt`.

- [ ] **Step 4: Implement MinerU payload normalization**

Implement:

```python
def mineru_payload_to_content(payload: dict) -> PatentDocumentContent:
    # unwrap data/result
    # support pages, content_list, markdown, text, full_text
    # preserve page order and image references
    # require at least one non-whitespace text fragment
```

Do not leak raw payload into the public response.

- [ ] **Step 5: Implement pypdf extraction**

Use `PdfReader`, one `PatentDocumentPage` per PDF page, and warnings such as `pypdf_page_3_no_text`. Convert malformed/encrypted/unreadable PDFs to `patent_document_parse_failed`.

- [ ] **Step 6: Implement orchestration**

Attempt MinerU unless `fast=True`. On MinerU unavailable/timeout/connection/invalid/no-text, append its code and try pypdf. If pypdf has no text, raise `PatentAnnotationError("patent_document_no_text", "当前版本仅支持带文字层或 MinerU 可识别的 PDF")`.

- [ ] **Step 7: Run parser tests**

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/patent_annotation/document_parser.py backend/tests/test_patent_document_parser.py backend/requirements.txt
git commit --no-verify -m "feat: parse patent PDF with MinerU fallback"
```

### Task 4: Prepare images and localize visible patent parts

**Files:**
- Create: `backend/app/patent_annotation/image_utils.py`
- Create: `backend/app/patent_annotation/localization.py`
- Create: `backend/tests/test_patent_localization.py`

**Interfaces:**
- Produces: `prepare_patent_images(source: Path, output_dir: Path, *, max_image_mb=20, max_side=2048) -> PatentImageAssets`
- Produces: `PatentLocalizationService(vision_client, model_name).localize(...) -> LocalizationResult`

- [ ] **Step 1: Write failing image and localization tests**

Cover EXIF rotation, RGBA white background, longest-side resize, grid dimensions, and:

```python
result = await service.localize(
    image_path,
    figure_no="4",
    figure_description="局部图",
    figure_context="弹簧 68",
    candidates=[LocalizationCandidate(ref_no="68", name="弹簧")],
    work_dir=tmp_path,
)
assert result.items[0].anchor.x == 0.25
assert result.items[0].anchor.y == 0.75
assert result.items[0].review_state == "accepted"
```

Add fake outputs for unknown refs, duplicate refs with different confidence, visible without anchor, reversed bbox, anchor outside bbox, rejected confidence, 17 candidates causing two calls, and `VisionModelError`.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_patent_localization.py -q --basetemp D:\3D解析\.pytest_tmp\patent-localization
```

- [ ] **Step 3: Implement image preparation**

Decode with Pillow, EXIF transpose, composite alpha over white, convert RGB, resize down to 2048, apply `ImageOps.autocontrast(cutoff=1)`, save `clean.png`, copy it, and draw pale grid lines plus 0–1000 edge labels into `coordinate-grid.png`.

- [ ] **Step 4: Implement the constrained prompt**

Define one backend constant/function containing all nine approved visibility/anchor/bbox/candidate/coordinate/JSON rules. Append figure number, description, capped context, and JSON candidate list. Do not include sample patent values.

- [ ] **Step 5: Implement batching and model calls**

Slice candidates in stable groups of 16 and call:

```python
await vision_client.complete_json(
    task_name="patent_page_localization",
    schema=ModelLocalizationOutput,
    messages=[{"type": "text", "text": prompt}],
    image_paths=[assets.clean_path, assets.grid_path],
)
```

- [ ] **Step 6: Implement merge and normalization**

Filter unknown refs, keep highest-confidence duplicate, normalize 1000 coordinates, sort bbox endpoints, clamp values, cap reason to 120 characters, and assign review state. Visible without anchor becomes invisible/rejected with warning. Anchor outside bbox remains unchanged but becomes review with warning.

- [ ] **Step 7: Run localization tests**

Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/patent_annotation/image_utils.py backend/app/patent_annotation/localization.py backend/tests/test_patent_localization.py
git commit --no-verify -m "feat: localize patent parts with vision"
```

### Task 5: Expose patent annotation APIs

**Files:**
- Create: `backend/app/patent_annotation/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_patent_annotation_router.py`

**Interfaces:**
- Produces: `POST /api/patent-annotations/parse-document`
- Produces: `POST /api/patent-annotations/localize-page`
- Produces dependency functions: `get_document_parser(settings)` and `get_localization_service(settings)`

- [ ] **Step 1: Write failing router tests**

Use `TestClient(app)` and dependency overrides. Cover non-PDF, empty/oversized PDF, fake valid parser response, missing/invalid components JSON, non-image, missing vision configuration, and fake localization response.

Example:

```python
response = client.post(
    "/api/patent-annotations/localize-page",
    files={"image_file": ("page.png", PNG_BYTES, "image/png")},
    data={"figure_no": "1", "components_json": "[]"},
)
assert response.status_code == 422
assert response.json()["detail"]["code"] == "patent_components_invalid"
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_patent_annotation_router.py -q --basetemp D:\3D解析\.pytest_tmp\patent-router
```

- [ ] **Step 3: Implement parse-document**

Read at most `30 * 1024 * 1024 + 1` bytes, validate `.pdf`, write to `TemporaryDirectory`, call the parser, and return `PatentDocumentParseResult`. Accept `fast: bool = Form(False)`.

- [ ] **Step 4: Implement localize-page**

Validate suffix/content type and 20 MB size, parse `components_json` with `TypeAdapter(list[LocalizationCandidate])`, reject an empty list, build the service only after configuration validation, and call it inside a request temporary directory.

- [ ] **Step 5: Implement HTTP error mapping**

Map invalid uploads/components to 422, no text to 422, vision not configured to 503, and localization/provider failures to 502. Every detail is:

```json
{"code": "patent_localization_failed", "message": "readable message"}
```

- [ ] **Step 6: Include the router in `app.main`**

Import and call `app.include_router(patent_annotation_router)` without changing other router prefixes.

- [ ] **Step 7: Run all new backend tests and Drawing regression**

Run:

```powershell
python -m pytest backend/tests/test_patent_document_parser.py backend/tests/test_patent_localization.py backend/tests/test_patent_annotation_router.py backend/tests/test_drawing_phase4a.py backend/tests/test_drawing_extraction_phase4b.py -q --basetemp D:\3D解析\.pytest_tmp\patent-backend
```

- [ ] **Step 8: Commit**

```powershell
git add backend/app/patent_annotation/router.py backend/app/main.py backend/tests/test_patent_annotation_router.py
git commit --no-verify -m "feat: expose patent auto annotation APIs"
```

### Task 6: Upgrade the frontend draft schema and replacement semantics

**Files:**
- Modify: `frontend/src/views/patent-annotation/types.ts`
- Modify: `frontend/src/views/patent-annotation/geometry.ts`
- Modify: `frontend/src/views/patent-annotation/composables/usePatentAnnotations.ts`
- Modify: `frontend/src/views/patent-annotation/__tests__/annotations.test.ts`
- Modify: `frontend/src/views/patent-annotation/__tests__/geometry.test.ts`

**Interfaces:**
- Preserves: schema 0.1 import
- Produces: schema 0.2 export
- Produces: `applySuggestedAnnotations(items, options?) -> { added: number; skippedManualRefs: string[] }`
- Produces: `acceptPageAutoAnnotations(sourceId, page) -> number`

- [ ] **Step 1: Add failing 0.1 migration tests**

Assert a 0.1 document imports, exports as 0.2, and old annotations receive `origin="manual"`. Assert 0.2 automation metadata is retained and invalid confidence/bbox values are normalized.

- [ ] **Step 2: Add failing replacement tests**

Create manual ref `1`, old auto refs `1` and `2`, then apply new auto refs `1`, `2`, `3` for one page. Assert manual `1` survives, old auto annotations are removed, new auto `1` is skipped, and new `2/3` are present. Assert annotations on another source/page remain untouched.

- [ ] **Step 3: Run frontend tests and verify RED**

Run with Node 20:

```powershell
pnpm test:patent-annotation
```

- [ ] **Step 4: Extend types**

Add `NormalizedBox`, `AnnotationOrigin`, `ReviewState`, optional automation fields, and `PatentSource.figureNo?`. Define `PatentAnnotationDocument.schemaVersion` as `'0.2'` in the normalized runtime type while the normalizer accepts input 0.1 or 0.2.

- [ ] **Step 5: Implement migration normalization**

In `normalizePatentAnnotationDocument`, accept both versions, default old annotations to manual, normalize optional confidence to 0～1, bbox endpoints to 0～1 sorted coordinates, and preserve model reason/name.

- [ ] **Step 6: Implement store semantics**

Keep the existing storage key. Extend `updateSource` for `figureNo`. Manual `createAnnotation` sets manual origin. Editing an automatic annotation sets `reviewed=true` and accepted state.

Enhance `applySuggestedAnnotations(items, options?)`: with no options retain append behavior; with `{sourceId, page, replaceAuto:true}`, perform the approved replacement/skip rules and normalize the combined document.

- [ ] **Step 7: Implement page acceptance**

`acceptPageAutoAnnotations` updates only review-state automatic annotations on the requested page and returns the changed count.

- [ ] **Step 8: Run patent tests**

Expected: all pass.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/views/patent-annotation/types.ts frontend/src/views/patent-annotation/geometry.ts frontend/src/views/patent-annotation/composables/usePatentAnnotations.ts frontend/src/views/patent-annotation/__tests__/annotations.test.ts frontend/src/views/patent-annotation/__tests__/geometry.test.ts
git commit --no-verify -m "feat: track automatic patent annotations"
```

### Task 7: Add ink snapping, label layout, mapping, and PDF capture

**Files:**
- Create: `frontend/src/views/patent-annotation/auto-annotation.ts`
- Create: `frontend/src/views/patent-annotation/__tests__/auto-annotation.test.ts`
- Modify: `frontend/src/views/patent-annotation/modules/PdfAnnotationWorkspace.vue`
- Modify: `frontend/package.json`

**Interfaces:**
- Produces: `snapPointToInk(point, imageData, options?) -> Point2D`
- Produces: `autoLayoutAnnotations(anchors, options?) -> AutoLayoutItem[]`
- Produces: `inferFigureNo(fileName, figures, sourceIndex) -> string`
- Exposes: `getCurrentPageImageBlob({scale?}?) -> Promise<Blob>`
- Exposes: `getCurrentPageImageData() -> ImageData | null`

- [ ] **Step 1: Add failing pure-function tests**

Create synthetic ImageData with a dark pixel and assert nearest-point snapping, radius cutoff, transparent-pixel ignore, and boundary clamp. Add 6 anchors on one side and assert labels remain within 0.06～0.94 with at least 0.055 spacing.

Test filename mapping for `图4.pdf`, `figure2.pdf`, and source-index fallback.

- [ ] **Step 2: Add the new test file to `test:patent-annotation` and run RED**

Expected: missing module/functions.

- [ ] **Step 3: Implement `snapPointToInk`**

Search integer pixels within a radius, accept `alpha > 0` and `(r+g+b)/3 < threshold`, track minimum squared Euclidean distance, and return normalized coordinates using image width/height.

- [ ] **Step 4: Implement deterministic layout**

Stable-sort left/right groups by y then refNo. Assign x `0.06/0.94`; distribute y forward and backward to maintain minimum separation within bounds. Assign elbow x using `min(anchor.x-0.04, 0.18)` for left labels and `max(anchor.x+0.04, 0.82)` for right labels.

- [ ] **Step 5: Implement figure inference**

Match `/图\s*(\d+)/i` then `/figure\s*(\d+)/i`; otherwise select `figures[sourceIndex]?.figure_no`, falling back to the first figure.

- [ ] **Step 6: Expose the PDF canvas**

In `PdfAnnotationWorkspace.vue`, implement an internal `captureCanvas()` that reads only `stageRef.querySelector("canvas")`, paints white into an offscreen canvas, scales the longest side into 1600～2048, and exposes:

```ts
defineExpose({
  getCurrentPageImageBlob,
  getCurrentPageImageData
});
```

Reject with `当前 PDF 页尚未渲染` if no canvas/context/blob is available.

- [ ] **Step 7: Run frontend tests and typecheck**

Run:

```powershell
pnpm test:patent-annotation
pnpm typecheck
```

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/views/patent-annotation/auto-annotation.ts frontend/src/views/patent-annotation/__tests__/auto-annotation.test.ts frontend/src/views/patent-annotation/modules/PdfAnnotationWorkspace.vue frontend/package.json
git commit --no-verify -m "feat: prepare PDF pages for auto annotation"
```

### Task 8: Add frontend API and auto-annotation orchestration

**Files:**
- Create: `frontend/src/typings/api/patent-annotation.d.ts`
- Create: `frontend/src/service/api/patent-annotation.ts`
- Modify: `frontend/src/service/api/index.ts`
- Create: `frontend/src/views/patent-annotation/composables/usePatentAutoAnnotation.ts`
- Modify: `frontend/src/views/patent-annotation/__tests__/annotations.test.ts`

**Interfaces:**
- Produces: `parsePatentDocument(file, {fast?})`
- Produces: `localizePatentPage(params)`
- Produces composable state/actions used by the panel and page.

- [ ] **Step 1: Define API types**

Create `Api.PatentAnnotation` interfaces matching snake_case backend JSON exactly: component, detail marker, figure, parse result with parser, candidate, normalized localization item/result.

- [ ] **Step 2: Implement multipart API functions**

`parsePatentDocument` sends `file` and optional `fast`. `localizePatentPage` sends `image_file`, `figure_no`, optional description/context, and `JSON.stringify(components)`.

- [ ] **Step 3: Add failing workflow helper tests**

Test the pure suggestion-building export from the composable module: localization items are snapped, laid out, receive auto metadata, rejected items are excluded, and one item is created per accepted/review result.

- [ ] **Step 4: Run patent tests and verify RED**

Expected: missing composable/helper.

- [ ] **Step 5: Implement composable state**

Track:

```ts
parseResult: Ref<Api.PatentAnnotation.DocumentParseResult | null>
selectedRefs: Ref<Set<string>>
parsing: Ref<boolean>
localizing: Ref<boolean>
progressText: Ref<string>
```

Expose component name edits by replacing the matching component object, not mutating API response aliases.

- [ ] **Step 6: Implement parse and default mappings**

After parse, select all components and assign figure numbers only to PDF sources without `figureNo`, using `inferFigureNo`. Display request detail messages using `error.response?.data?.detail?.message ?? error.message`.

- [ ] **Step 7: Implement current-page localization**

Accept a PDF workspace capture interface, active source/page, and a `confirmReplace` callback. If old auto annotations exist and confirmation is declined, stop before capture/API.

Build candidates from the figure candidate refs intersected with selected refs, plus detail markers. Capture PNG/ImageData, call the API, build suggestions, and call:

```ts
store.applySuggestedAnnotations(suggestions, {
  sourceId,
  page,
  replaceAuto: true
});
```

Return `{added, reviewCount, warnings}` for UI messaging.

- [ ] **Step 8: Run patent tests and typecheck**

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/typings/api/patent-annotation.d.ts frontend/src/service/api/patent-annotation.ts frontend/src/service/api/index.ts frontend/src/views/patent-annotation/composables/usePatentAutoAnnotation.ts frontend/src/views/patent-annotation/__tests__/annotations.test.ts
git commit --no-verify -m "feat: orchestrate PDF patent auto annotation"
```

### Task 9: Integrate automatic annotation UI and review controls

**Files:**
- Create: `frontend/src/views/patent-annotation/modules/AutoAnnotationPanel.vue`
- Modify: `frontend/src/views/patent-annotation/index.vue`
- Modify: `frontend/src/views/patent-annotation/modules/AnnotationInspector.vue`
- Modify: `frontend/src/views/patent-annotation/modules/LeaderOverlay.vue`

**Interfaces:**
- Consumes the Task 8 composable.
- Emits parse, mapping, candidate toggle/edit, localize, and accept-page actions.

- [ ] **Step 1: Implement the compact panel**

Include a hidden PDF input, parse button, parser label (`MinerU` or `pypdf 回退`), title/count summary, warnings alert, collapsible component table with checkbox and editable name, active source filename, figure select/description, progress text, auto-annotate button, and accept-page button.

- [ ] **Step 2: Integrate into the existing page**

Render the panel only when `mode === "pdf"`. Keep a typed `PdfAnnotationWorkspace` ref, pass active source/page to the composable, and retain the current STEP workspace unchanged.

Use `ElMessageBox.confirm("替换当前页旧的自动标注？", ...)` only when old automatic annotations exist.

- [ ] **Step 3: Add inspector status badges**

Rows show:

- manual: `人工`;
- accepted auto: `自动 87%` green;
- review auto: `待审核 58%` orange.

Selected automatic annotation shows confidence, reason, normalized bbox, model name, and an “接受” button.

- [ ] **Step 4: Mark drag edits reviewed**

Existing overlay update events continue through store `updateAnnotation`, which marks auto annotations accepted/reviewed. Set SVG `text-anchor` dynamically:

```vue
:text-anchor="annotation.label.x < annotation.anchor.x ? 'start' : 'end'"
```

- [ ] **Step 5: Run scoped lint, tests, typecheck, and build**

Run with Node 20:

```powershell
pnpm exec eslint src/service/api/index.ts src/service/api/patent-annotation.ts src/views/patent-annotation/types.ts src/views/patent-annotation/geometry.ts src/views/patent-annotation/auto-annotation.ts src/views/patent-annotation/composables/usePatentAnnotations.ts src/views/patent-annotation/composables/usePatentAutoAnnotation.ts src/views/patent-annotation/modules/PdfAnnotationWorkspace.vue src/views/patent-annotation/modules/AutoAnnotationPanel.vue src/views/patent-annotation/modules/AnnotationInspector.vue src/views/patent-annotation/modules/LeaderOverlay.vue src/views/patent-annotation/index.vue src/views/patent-annotation/__tests__/annotations.test.ts src/views/patent-annotation/__tests__/geometry.test.ts src/views/patent-annotation/__tests__/auto-annotation.test.ts
pnpm test:patent-annotation
pnpm typecheck
pnpm build:test
```

Expected: all pass; do not run global lint fix.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/views/patent-annotation/modules/AutoAnnotationPanel.vue frontend/src/views/patent-annotation/index.vue frontend/src/views/patent-annotation/modules/AnnotationInspector.vue frontend/src/views/patent-annotation/modules/LeaderOverlay.vue
git commit --no-verify -m "feat: add patent auto annotation controls"
```

### Task 10: Golden-sample smoke test, review, and final delivery

**Files:**
- No sample files are added.
- Modify only production/tests if the smoke test reveals a reproducible defect.

**Interfaces:**
- Exercises both new APIs and `/patent-annotation`.

- [ ] **Step 1: Verify parser configuration without exposing secrets**

In `3dcad`, print only booleans and non-secret model name:

```powershell
python -c "from app.core.config import get_settings; s=get_settings(); print({'mineru_mode':s.mineru_layout_mode,'vision_model':s.vision_model,'vision_host_configured':bool(s.vision_binding_host),'vision_key_configured':bool(s.vision_binding_api_key)})"
```

- [ ] **Step 2: Parse the golden patent PDF**

Start/reuse the backend and call `parse-document` with the local specification PDF. Verify components `1,2,3,4,5,61...68`, figures `1...4`, detail marker `3 ↔ A ↔ 4`, parser source, and warnings. Record actual results without committing input/output files.

- [ ] **Step 3: Run the browser workflow**

Start frontend on Node 20, upload resources 527–530, map them to figures 1–4, parse the specification, and invoke current-page localization for each page when vision is configured.

Verify multiple editable leaders, status badges, drag/edit acceptance, accept-all, and rerun preserving a manually added annotation.

If vision is not configured, verify document parsing and UI mapping still work and that localization returns/display a readable 503; record localization counts as “not run — vision not configured”, not fabricated values.

- [ ] **Step 4: Run final backend verification**

```powershell
python -m pytest backend/tests/test_patent_document_parser.py backend/tests/test_patent_localization.py backend/tests/test_patent_annotation_router.py backend/tests/test_drawing_phase4a.py backend/tests/test_drawing_extraction_phase4b.py -q --basetemp D:\3D解析\.pytest_tmp\final-patent
```

- [ ] **Step 5: Run final frontend verification**

```powershell
pnpm test:patent-annotation
pnpm typecheck
pnpm build:test
```

- [ ] **Step 6: Run two-axis code review**

Review the implementation diff since the design/plan baseline for documented standards and this plan/spec separately. Fix every high-confidence spec gap and regression, then rerun the affected tests.

- [ ] **Step 7: Commit final fixes**

```powershell
git add backend/app/core/mineru.py backend/app/core/vision.py backend/app/drawing/providers.py backend/app/drawing/router.py backend/app/main.py backend/app/patent_annotation backend/requirements.txt backend/tests/test_patent_document_parser.py backend/tests/test_patent_localization.py backend/tests/test_patent_annotation_router.py backend/tests/test_drawing_phase4a.py frontend/package.json frontend/src/service/api/index.ts frontend/src/service/api/patent-annotation.ts frontend/src/typings/api/patent-annotation.d.ts frontend/src/views/patent-annotation
git commit --no-verify -m "feat: add automatic PDF patent annotation"
```

- [ ] **Step 8: Push main**

```powershell
git push origin main
```

- [ ] **Step 9: Report**

Report the change summary, APIs and schemas, main files, exact backend/frontend test results, actual per-figure localization counts/review counts or the explicit configuration blocker, and the documented first-version limitations.
