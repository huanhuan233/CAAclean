# Component Library Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified component-library workbench where one upload creates a linked STEP revision and drawing extraction task, exposes both in a business file tree, and opens the existing specialist viewers with exact identifiers.

**Architecture:** Add a `component_builds` orchestration module that owns the relationship between catalog metadata, `CadModelRevision`, and `CadSpecTask`. Its small HTTP interface creates and projects builds while delegating STEP and drawing parsing to the existing modules. Add a Vue workbench page that consumes this aggregate interface; keep the CAD and drawing pages as specialist viewers and extend only their route selection and return behavior.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, PostgreSQL JSONB/UUID, pytest, Vue 3, TypeScript, Element Plus, Vue Router, Vite.

## Global Constraints

- Preserve all pre-existing dirty worktree changes and do not reformat unrelated files.
- ComponentSpec v1.2 YAML remains the final conceptual output; actual YAML generation is outside this phase.
- One `ComponentBuild` links exactly one active STEP revision and one active drawing task.
- STEP is both source evidence and `artifacts.reference_step`; the drawing is provenance evidence, not a new artifact type.
- Existing direct STEP upload and direct drawing-task workflows must remain usable.
- Display real percentages only when returned by the backend; drawing layout uses stage text until its status response exposes progress.
- Disabled future nodes must say `待生成` or `后续能力` and must never appear completed.

---

### Task 1: ComponentBuild persistence and status projection

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/component_builds/__init__.py`
- Create: `backend/app/component_builds/schemas.py`
- Create: `backend/app/component_builds/repository.py`
- Create: `backend/app/component_builds/service.py`
- Test: `backend/tests/test_component_build_service.py`

**Interfaces:**
- Consumes: `CadModel`, `CadModelRevision`, and `CadSpecTask` SQLAlchemy rows.
- Produces: `ComponentBuildService.get_tree() -> list[dict]`, `ComponentBuildService.get_build(build_id: UUID) -> dict`, and `ComponentBuildService.get_status(build_id: UUID) -> dict`.
- Produces model fields: `id`, component identity fields, `cad_model_id`, `cad_revision_id`, `drawing_task_id`, build status fields, timestamps.

- [ ] **Step 1: Write failing model and projection tests**

```python
def test_component_build_has_source_links():
    columns = ComponentBuild.__table__.columns
    assert columns["cad_revision_id"].nullable is True
    assert columns["drawing_task_id"].nullable is True
    assert columns["component_id"].nullable is False


@pytest.mark.asyncio
async def test_status_projects_linked_source_states():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(component_id="xms06", component_name="XMS06", component_type="flange")
    await repository.attach_step(build.id, model_id=uuid4(), revision_id=uuid4())
    service = ComponentBuildService(repository, source_status_reader=FakeSourceStatusReader())

    status = await service.get_status(build.id)

    assert status["status"] == "parsing_sources"
    assert status["sources"]["reference_step"]["status"] == "processing"
    assert status["sources"]["drawing"]["status"] == "waiting_for_step"
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run: `python -m pytest tests/test_component_build_service.py -v` from `backend`.

Expected: collection fails because `app.component_builds` and `ComponentBuild` do not exist.

- [ ] **Step 3: Add the ORM model and Pydantic contracts**

Add `ComponentBuild` to `backend/app/db/models.py` with nullable UUID foreign keys for `cad_model_id`, `cad_revision_id`, and `drawing_task_id`; strings for identity and status; integers for default DN/PN; and UTC timestamps using the existing `utc_now`.

Define these request/response contracts in `schemas.py`:

```python
class ComponentBuildCreateFields(BaseModel):
    component_id: str = Field(min_length=1, max_length=160)
    component_name: str = Field(min_length=1, max_length=255)
    component_type: str = Field(min_length=1, max_length=80)
    component_subtype: str | None = None
    family: str | None = None
    standard_number: str | None = None
    version: str = "1.0.0"
    default_dn: int | None = None
    default_pn: int | None = None


class ComponentBuildRetryIn(BaseModel):
    role: Literal["reference_step", "drawing"]
```

- [ ] **Step 4: Implement repository adapters and deterministic projection**

Create an in-memory repository for tests and a SQLAlchemy repository for production. Repository methods:

```python
async def create_build(self, **fields) -> ComponentBuild
async def get_build(self, build_id: UUID) -> ComponentBuild | None
async def list_builds(self) -> list[ComponentBuild]
async def attach_step(self, build_id: UUID, *, model_id: UUID, revision_id: UUID) -> ComponentBuild
async def attach_drawing(self, build_id: UUID, *, task_id: UUID) -> ComponentBuild
async def set_status(self, build_id: UUID, *, status: str, message: str | None = None) -> None
```

Project source state with this precedence:

```python
if step_status == "failed" or drawing_status == "failed":
    build_status = "source_failed"
elif drawing_status == "needs_manual_layout":
    build_status = "review_required"
elif step_status == "completed" and drawing_status == "review_ready":
    build_status = "sources_ready"
elif revision_id or drawing_task_id:
    build_status = "parsing_sources"
else:
    build_status = "draft"
```

Tree output must create virtual children for `输入资料`, `数据融合`, `ComponentSpec`, and `发布校验`; future output nodes use `disabled: true` and status `future`.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_component_build_service.py -v` from `backend`.

Expected: all tests pass.

Commit:

```bash
git add backend/app/db/models.py backend/app/component_builds backend/tests/test_component_build_service.py
git commit -m "feat: add component build status model"
```

### Task 2: Aggregate upload and query HTTP interface

**Files:**
- Create: `backend/app/component_builds/router.py`
- Modify: `backend/app/component_builds/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_component_build_api.py`

**Interfaces:**
- Consumes: `CadService.create_model_from_upload(file, name)`, `DrawingLayoutService.create_task(...)`, `create_drawing_service(...)`, and `SessionLocal`.
- Produces:
  - `POST /api/component-builds`
  - `GET /api/component-builds/tree`
  - `GET /api/component-builds/{build_id}`
  - `GET /api/component-builds/{build_id}/status`
  - `POST /api/component-builds/{build_id}/retry`

- [ ] **Step 1: Write failing aggregate API tests**

```python
def test_create_build_links_step_and_drawing():
    response = client.post(
        "/api/component-builds",
        data={
            "component_id": "xms06",
            "component_name": "XMS06",
            "component_type": "flange",
            "version": "1.0.0",
            "default_dn": "80",
            "default_pn": "16",
        },
        files={
            "step_file": ("XMS06-DN80.stp", b"ISO-10303-21;", "application/octet-stream"),
            "drawing_file": ("XMS06.png", PNG_BYTES, "image/png"),
        },
    )

    assert response.status_code == 202
    assert response.json()["cad_revision_id"] == str(fake_service.revision_id)
    assert response.json()["drawing_task_id"] == str(fake_service.task_id)


def test_tree_exposes_specialist_targets():
    payload = client.get("/api/component-builds/tree").json()
    step = find_node(payload, "reference_step")
    drawing = find_node(payload, "drawing")
    assert step["target"]["revision_id"]
    assert drawing["target"]["task_id"]
```

- [ ] **Step 2: Run the API tests and verify 404 failures**

Run: `python -m pytest tests/test_component_build_api.py -v` from `backend`.

Expected: requests fail because the router is not registered.

- [ ] **Step 3: Implement aggregate creation**

`POST /api/component-builds` receives form fields plus required `step_file` and `drawing_file`. The service must:

1. Validate `.step` or `.stp` and `.png`, `.jpg`, `.jpeg`, or `.webp`.
2. Create the build as `uploading`.
3. Delegate STEP upload to the existing CAD module.
4. Attach returned `model_id` and `revision_id`.
5. Save the drawing upload to `cad_spec_work_dir/uploads`.
6. Create the drawing task with the returned `revision_id`.
7. Attach `task_id`, set the build to `parsing_sources`, and schedule the complete drawing pipeline.

Use a background coroutine with a fresh DB session:

```python
async def run_drawing_pipeline(task_id: UUID, settings: Settings, *, target_code: str | None, target_dn: int | None):
    async with SessionLocal() as session:
        drawing = create_drawing_service(session, settings)
        layout = await drawing.start_layout(task_id)
        if layout["status"] == "layout_ready":
            await drawing.extract_drawing_facts(task_id, target_code=target_code, target_dn=target_dn)
```

Catch `DrawingError`, `VisionModelError`, and unexpected exceptions using the same persisted failure conventions as the existing drawing router.

- [ ] **Step 4: Implement query and role-specific retry routes**

`GET` routes return projected states, not raw ORM rows. Retry behavior:

- `drawing`: schedule the full drawing pipeline again for the existing `task_id`.
- `reference_step`: return HTTP 409 with code `step_reupload_required`, because the existing CAD module has no safe retry for a failed source revision.

This makes the first UI honest: failed STEP offers “重新上传 STEP”; failed drawing offers “重试解析”.

- [ ] **Step 5: Register the router and run backend API tests**

Add `app.include_router(component_build_router)` to `backend/app/main.py`.

Run:

```bash
python -m pytest tests/test_component_build_api.py tests/test_component_build_service.py -v
python -m pytest tests/test_cad_api.py tests/test_drawing_phase4a.py -q
```

Expected: new tests pass and existing CAD/drawing API tests remain green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/component_builds backend/app/main.py backend/tests/test_component_build_api.py
git commit -m "feat: add component build upload API"
```

### Task 3: Workbench API client and business file tree page

**Files:**
- Modify: `frontend/src/typings/api/cad.d.ts`
- Modify: `frontend/src/service/api/cad.ts`
- Create: `frontend/src/views/component-build/index.vue`
- Modify: `frontend/src/router/routes/index.ts`
- Modify: `frontend/src/router/elegant/imports.ts`
- Modify: `frontend/src/router/elegant/routes.ts`
- Modify: `frontend/src/router/elegant/transform.ts`
- Modify: `frontend/src/typings/elegant-router.d.ts`
- Modify: `frontend/src/locales/langs/zh-cn.ts`
- Modify: `frontend/src/locales/langs/en-us.ts`

**Interfaces:**
- Consumes backend tree nodes with `node_type`, `status`, `progress`, `disabled`, `children`, and optional `target`.
- Produces `/component-build` route and specialist navigation queries containing `revision_id`, `task_id`, and `build_id`.

- [ ] **Step 1: Add strict frontend contracts and request helpers**

Add:

```typescript
namespace ComponentBuild {
  type NodeType =
    | 'root'
    | 'family'
    | 'type'
    | 'subtype'
    | 'component'
    | 'build'
    | 'folder'
    | 'reference_step'
    | 'drawing'
    | 'fusion'
    | 'yaml'
    | 'future';

  interface TreeNode {
    id: string;
    label: string;
    node_type: NodeType;
    status: string;
    progress: number | null;
    disabled: boolean;
    build_id: string | null;
    target: { revision_id?: string; task_id?: string } | null;
    children: TreeNode[];
  }
}
```

Add request helpers `fetchComponentBuildTree`, `fetchComponentBuildStatus`, `createComponentBuild`, and `retryComponentBuild`.

- [ ] **Step 2: Create the workbench page**

Build a dense two-column operational UI:

- Toolbar: search, refresh, “新建图元”.
- Left: `ElTree`, 320px wide, node icons, status dots, progress text, expanded build restoration from `route.query.build_id`.
- Right default: selected build summary and the five-stage pipeline.
- Right source detail: file name, stage, progress, error text, retry/reupload action, and “查看解析结果”.
- Right future detail: disabled explanation only, with no active success action.
- Upload drawer: identity fields plus two required file pickers; submit once using `createComponentBuild`.
- Poll every two seconds while any visible build is `uploading` or `parsing_sources`; stop on unmount.

Completed STEP navigation:

```typescript
router.push({
  path: '/cad-model',
  query: { revision_id: node.target?.revision_id, build_id: node.build_id }
});
```

Review-ready drawing navigation:

```typescript
router.push({
  path: '/cad-spec',
  query: {
    revision_id: node.target?.revision_id,
    task_id: node.target?.task_id,
    build_id: node.build_id
  }
});
```

- [ ] **Step 3: Register the route and localized labels**

Add a custom route before the two specialist routes:

```typescript
{
  name: 'component-build',
  path: '/component-build',
  component: 'layout.base$view.component-build',
  meta: {
    title: '图元建库',
    icon: 'carbon:tree-view-alt',
    order: 1
  }
}
```

Move CAD and drawing pages to orders 2 and 3. Change the displayed `cad-spec` label to `二维图纸解析`; do not rename its route.

- [ ] **Step 4: Typecheck and visually smoke test**

Run from `frontend`:

```bash
pnpm typecheck
pnpm build:test
```

Expected: both commands exit 0.

Start the existing dev command, open `/component-build`, and verify:

- the tree fits at 1440x900 and 1920x1080;
- long filenames truncate without overlapping statuses;
- the drawer remains usable at 390px mobile width;
- disabled YAML/future nodes do not expose active actions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/typings/api/cad.d.ts frontend/src/service/api/cad.ts frontend/src/views/component-build frontend/src/router frontend/src/locales
git commit -m "feat: add component library workbench"
```

### Task 4: Exact specialist-page routing and return behavior

**Files:**
- Modify: `frontend/src/views/cad-model/index.vue`
- Modify: `frontend/src/views/cad-spec/index.vue`

**Interfaces:**
- Consumes query parameters `revision_id`, `task_id`, and `build_id`.
- Preserves current behavior when these parameters are absent.

- [ ] **Step 1: Make CAD selection revision-aware**

Use `useRoute()` and resolve the requested revision after loading models:

```typescript
const requestedRevisionId = computed(() => String(route.query.revision_id || ''));
const requestedModel = models.value.find(item => item.current_revision_id === requestedRevisionId.value);
await selectModel(requestedModel ?? models.value[0]);
```

Replace the existing plain-text “返回” behavior with a button shown only when `build_id` exists:

```typescript
router.push({ path: '/component-build', query: { build_id: route.query.build_id } });
```

- [ ] **Step 2: Make drawing selection task-aware**

Define `requestedTaskId` from the route. After `loadTaskOptions()`, call `selectTask(requestedTaskId)` when it exists in the loaded options; otherwise preserve the current blank/current-revision state.

Change the existing “返回 CAD 页面” command:

- with `build_id`: label “返回图元建库” and route to `/component-build?build_id=...`;
- without `build_id`: preserve `/cad-model`.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
pnpm typecheck
pnpm build:test
```

Manual route checks:

- `/cad-model?revision_id=<known revision>&build_id=<known build>` selects the requested model.
- `/cad-spec?revision_id=<known revision>&task_id=<known task>&build_id=<known build>` selects the requested drawing.
- direct `/cad-model` and `/cad-spec?revision_id=<known revision>` retain current behavior.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/cad-model/index.vue frontend/src/views/cad-spec/index.vue
git commit -m "feat: deep link component source viewers"
```

### Task 5: Full regression and acceptance evidence

**Files:**
- Modify only files required to fix failures introduced by Tasks 1-4.

**Interfaces:**
- Verifies the complete seam from aggregate upload to exact specialist viewer navigation.

- [ ] **Step 1: Run all backend tests**

Run from `backend`:

```bash
python -m pytest -q
```

Expected: all tests pass. Existing local modifications in `parser_runner.py` and its tests must not be reverted or overwritten while resolving failures.

- [ ] **Step 2: Run frontend static verification**

Run from `frontend`:

```bash
pnpm typecheck
pnpm build:test
```

Expected: both commands exit 0.

- [ ] **Step 3: Run browser acceptance**

With backend and frontend dev servers running:

1. Create a build using one valid STEP and one valid PNG/JPG/WEBP drawing.
2. Refresh the workbench and confirm the same build and source states return.
3. Open completed STEP and confirm the exact 3D model appears.
4. Open review-ready drawing and confirm the exact drawing task appears.
5. Return from each viewer and confirm the original build is selected.
6. Confirm YAML, generator, preview, thumbnail, and release nodes stay disabled.

- [ ] **Step 4: Review the final diff**

Run:

```bash
git diff --check
git status --short
```

Verify that only planned files and the user’s pre-existing modifications are present.
