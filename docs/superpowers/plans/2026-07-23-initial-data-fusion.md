# Initial Component Data Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the component-library “数据融合” node to populate an editable ComponentSpec v1.2 draft from build metadata, drawing facts, and STEP measurements, with XMS06-DN80 as the acceptance example.

**Architecture:** Add a pure deterministic fusion module with no database dependencies, then adapt SQLAlchemy rows into its inputs through a focused source reader. `ComponentBuildService` orchestrates reading, fusion, normalization, and saving through the existing draft repository. The frontend calls one synchronous endpoint, renders the returned report, and links to the existing ComponentSpec editor.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic, pytest, Vue 3, TypeScript, Element Plus, pnpm.

## Global Constraints

- Default fusion fills only empty fields and never overwrites user values.
- Explicit overwrite mode replaces only fields owned by deterministic fusion rules.
- The first release has flange-specific dimension rules; generic identity and artifact rules apply to all component types.
- No AI calls, external standard lookup, new database table, or asynchronous queue.
- Missing or ambiguous target DN must never select an arbitrary drawing row.
- Source links are build-scoped; data from another component must never be reused.
- ComponentSpec output remains normalized by the existing v1.2 template.

---

## File Structure

- Create `backend/app/component_builds/fusion.py`: pure fusion types, merge policy, target selection, flange mapping, and report generation.
- Create `backend/app/component_builds/fusion_sources.py`: SQLAlchemy source reader that loads build-scoped drawing facts, measurements, and features.
- Modify `backend/app/component_builds/service.py`: fusion orchestration and enabled tree node.
- Modify `backend/app/component_builds/router.py`: wire source reader and expose the fusion endpoint.
- Modify `backend/app/component_builds/schemas.py`: fusion request schema.
- Create `backend/tests/test_component_spec_fusion.py`: rule-level tests.
- Modify `backend/tests/test_component_build_service.py`: orchestration and tree-node tests.
- Modify `backend/tests/test_component_build_api.py`: endpoint and persistence tests.
- Modify `frontend/src/service/api/cad.ts`: fusion request function.
- Modify `frontend/src/typings/api/cad.d.ts`: fusion report types.
- Modify `frontend/src/views/component-build/index.vue`: fusion page, actions, and tree behavior.

### Task 1: Pure ComponentSpec Fusion Rules

**Files:**
- Create: `backend/app/component_builds/fusion.py`
- Create: `backend/tests/test_component_spec_fusion.py`

**Interfaces:**
- Consumes: plain dictionaries for build metadata, current ComponentSpec, drawing facts, STEP measurements, and STEP features.
- Produces:

```python
@dataclass(frozen=True)
class FusionSources:
    drawing_facts: list[dict]
    measurements: list[dict]
    features: list[dict]

@dataclass(frozen=True)
class FusionResult:
    data: dict
    summary: dict[str, int]
    fields: list[dict]
    warnings: list[str]

def fuse_component_spec(
    *,
    build: dict,
    current: dict,
    sources: FusionSources,
    overwrite: bool = False,
) -> FusionResult: ...
```

- [ ] **Step 1: Write failing identity and target-DN tests**

```python
def test_fusion_populates_generic_identity_without_overwriting_manual_values():
    current = blank_spec()
    current["identity"]["name"] = "人工名称"
    result = fuse_component_spec(
        build={
            "component_id": "flange-001",
            "component_name": "XMS06-DN80",
            "component_type": "flange",
            "family": "connection-fastening",
            "standard_number": "HG/T 20592-2009",
            "version": "1.0.0",
        },
        current=current,
        sources=FusionSources(drawing_facts=product_facts(), measurements=[], features=[]),
    )
    assert result.data["identity"]["id"] == "flange-001"
    assert result.data["identity"]["name"] == "人工名称"
    assert result.data["identity"]["subtype"] == "weld_neck"
    assert result.data["identity"]["standard"]["edition"] == "2009"
    assert any(item["path"] == "identity.name" and item["decision"] == "preserved" for item in result.fields)


def test_fusion_does_not_choose_a_dimension_row_when_target_dn_is_unknown():
    result = fuse_component_spec(
        build={"component_name": "未命名法兰", "component_type": "flange"},
        current=blank_spec(),
        sources=FusionSources(drawing_facts=dn15_and_dn80_facts(), measurements=[], features=[]),
    )
    assert parameter_default(result.data, "flange_outer_diameter") is None
    assert "target_dn_unresolved" in result.warnings
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend\tests\test_component_spec_fusion.py -q -p no:cacheprovider
```

Expected: collection fails because `app.component_builds.fusion` does not exist.

- [ ] **Step 3: Implement path-aware non-destructive merge**

Implement helpers in `fusion.py`:

```python
def _is_empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _assign(result, path, value, *, source, confidence, needs_review=False, overwrite=False):
    current = _get_path(result.data, path)
    if not overwrite and not _is_empty(current):
        result.record(path, current, source, confidence, "preserved", needs_review)
        return
    _set_path(result.data, path, value)
    result.record(path, value, source, confidence, "filled", needs_review)
```

Add target DN resolution in this order: existing ComponentSpec `DN`, `DN(\d+)` in component name, then build `default_dn`.

- [ ] **Step 4: Run identity tests and verify GREEN**

Run the Task 1 test command. Expected: identity and unresolved-DN tests pass.

- [ ] **Step 5: Write failing XMS06-DN80 mapping tests**

The test fixture must include DN15 and DN80 rows so it proves row selection:

```python
def test_flange_fusion_maps_only_the_dn80_row_and_builds_preset():
    result = fuse_component_spec(
        build=xms06_build(),
        current=blank_spec(),
        sources=FusionSources(
            drawing_facts=xms06_product_facts() + xms06_dn15_facts() + xms06_dn80_facts(),
            measurements=xms06_step_measurements(),
            features=xms06_step_features(),
        ),
    )
    assert parameter_default(result.data, "DN") == 80
    assert parameter_default(result.data, "PN") == 16
    assert parameter_default(result.data, "flange_outer_diameter") == 200.0
    assert parameter_default(result.data, "bolt_circle_diameter") == 160.0
    assert parameter_default(result.data, "bolt_hole_count") == 8
    assert parameter_default(result.data, "bore_diameter") == 82.6
    assert result.data["presets"][0]["name"] == "DN80-PN16"
    assert result.data["presets"][0]["params"]["raised_face_diameter"] == 138.0
```

Add separate tests proving:

- `bore_diameter` remains empty without a matching 82.6 mm STEP candidate.
- `S >= 3.2` and `H1 ~= 10` are marked `needs_review`.
- default mode preserves a manually changed outer diameter.
- overwrite mode replaces that outer diameter and leaves unrelated fields unchanged.

- [ ] **Step 6: Run flange tests and verify RED**

Expected failures: parameter array still has only the blank placeholder and no flange mapping exists.

- [ ] **Step 7: Implement flange mapping and preset generation**

Use a single mapping table:

```python
FLANGE_SYMBOL_MAP = {
    "D": ("flange_outer_diameter", False),
    "K": ("bolt_circle_diameter", False),
    "n": ("bolt_hole_count", False),
    "L": ("bolt_hole_diameter", False),
    "C": ("flange_thickness", False),
    "A1": ("pipe_outer_diameter", False),
    "S": ("wall_thickness", True),
    "N": ("hub_small_end_diameter", True),
    "H1": ("hub_height", True),
    "H": ("overall_height", False),
    "d": ("raised_face_diameter", False),
    "f1": ("raised_face_height", False),
    "R": ("root_fillet_radius", False),
}
```

Create complete parameter objects with `name`, `label`, `type`, `unit`, `default`, `required`, `editable`, `affects_geometry`, and `standard_symbol`, while preserving any existing array items by parameter name.

Derive `bore_diameter = A1 - 2*S` only when a `circle_diameter` or `cylinder_diameter` STEP measurement matches within 0.1 mm.

- [ ] **Step 8: Run all fusion tests and verify GREEN**

Run the Task 1 command. Expected: all tests pass.

- [ ] **Step 9: Commit Task 1**

```powershell
git add backend/app/component_builds/fusion.py backend/tests/test_component_spec_fusion.py
git commit -m "feat: add deterministic component spec fusion rules"
```

### Task 2: Build-Scoped Source Reader and Fusion API

**Files:**
- Create: `backend/app/component_builds/fusion_sources.py`
- Modify: `backend/app/component_builds/service.py`
- Modify: `backend/app/component_builds/router.py`
- Modify: `backend/app/component_builds/schemas.py`
- Modify: `backend/tests/test_component_build_service.py`
- Modify: `backend/tests/test_component_build_api.py`

**Interfaces:**
- `SqlAlchemyFusionSourceReader.read(build: ComponentBuild) -> FusionSources`
- `ComponentBuildService.fuse_component_spec(build_id: UUID, *, overwrite: bool = False) -> dict`
- `ComponentBuildFusionIn(overwrite: bool = False)`

- [ ] **Step 1: Write failing service tests**

Use a fake source reader that records the build IDs it receives:

```python
@pytest.mark.asyncio
async def test_fuse_component_spec_saves_normalized_draft_and_returns_report():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(**xms06_build_fields())
    reader = FakeFusionSourceReader(xms06_sources())
    service = ComponentBuildService(
        repository,
        source_status_reader=FakeSourceStatusReader(),
        fusion_source_reader=reader,
    )

    response = await service.fuse_component_spec(build.id)

    assert reader.build_ids == [build.id]
    assert response["status"] == "completed"
    assert response["component_spec"]["identity"]["id"] == "flange-001"
    assert (await repository.get_component_spec(build.id)).data["identity"]["id"] == "flange-001"
```

Add a test that an existing draft value is preserved and a test that no sources raises `FusionSourceUnavailable`.

- [ ] **Step 2: Run service tests and verify RED**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend\tests\test_component_build_service.py -q -p no:cacheprovider
```

Expected: service constructor and `fuse_component_spec` do not support fusion.

- [ ] **Step 3: Implement SQLAlchemy source reader**

Query only rows whose IDs are attached to the current build:

```python
select(CadDrawingFact).where(
    CadDrawingFact.task_id == build.drawing_task_id,
    CadDrawingFact.status == "current",
)
select(CadMeasurement).where(CadMeasurement.revision_id == build.cad_revision_id)
select(CadFeatureCandidate).where(CadFeatureCandidate.revision_id == build.cad_revision_id)
```

Convert rows to plain dictionaries and preserve drawing `metadata_json.row_dn`, symbol case (`D` versus `d`), operator, confidence, and normalized values.

- [ ] **Step 4: Implement service orchestration**

Read the current draft or `component_spec_template.blank_data()`, call `fuse_component_spec`, normalize through `component_spec_template.normalize`, save through the existing repository, and return:

```python
{
    "build_id": str(build.id),
    "status": "completed",
    "summary": result.summary,
    "fields": result.fields,
    "warnings": result.warnings,
    "component_spec": draft.data,
}
```

Raise `FusionSourceUnavailable("no_sources_available")` when neither source returns facts.

- [ ] **Step 5: Run service tests and verify GREEN**

Run the Task 2 service test command. Expected: all service tests pass.

- [ ] **Step 6: Write failing API tests**

```python
def test_component_fusion_endpoint_saves_xms06_draft(component_client):
    client, repository, service = component_client
    build = create_xms06_build(client)
    response = client.post(f"/api/component-builds/{build['id']}/fusion", json={"overwrite": False})
    assert response.status_code == 200
    assert response.json()["summary"]["filled"] > 0
    spec = client.get(f"/api/component-builds/{build['id']}/component-spec").json()
    assert find_parameter(spec["data"], "DN")["default"] == 80


def test_component_fusion_returns_409_without_sources(component_client):
    build = create_empty_build(component_client)
    response = component_client.post(f"/api/component-builds/{build['id']}/fusion", json={})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "no_sources_available"
```

- [ ] **Step 7: Run API tests and verify RED**

Expected: endpoint returns 404 because the route does not exist.

- [ ] **Step 8: Add schema, route, and dependency wiring**

Add:

```python
class ComponentBuildFusionIn(BaseModel):
    overwrite: bool = False
```

Wire `SqlAlchemyFusionSourceReader(session)` in `get_component_build_service` and map `FusionSourceUnavailable` to HTTP 409.

- [ ] **Step 9: Run API tests and full backend regression**

Run:

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend\tests\test_component_spec_fusion.py backend\tests\test_component_build_service.py backend\tests\test_component_build_api.py backend\tests\test_component_build_catalog.py backend\tests\test_parser_runner.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 10: Commit Task 2**

```powershell
git add backend/app/component_builds/fusion_sources.py backend/app/component_builds/service.py backend/app/component_builds/router.py backend/app/component_builds/schemas.py backend/tests/test_component_build_service.py backend/tests/test_component_build_api.py
git commit -m "feat: expose component data fusion endpoint"
```

### Task 3: Enable the Data Fusion Tree Node

**Files:**
- Modify: `backend/app/component_builds/service.py`
- Modify: `backend/tests/test_component_build_service.py`

**Interfaces:**
- Data fusion tree node:

```python
{
    "id": f"{build.id}:fusion",
    "build_id": str(build.id),
    "name": "数据融合",
    "label": "数据融合",
    "node_type": "data_fusion",
    "status": "completed" if component_spec else "ready",
    "status_label": "已生成草稿" if component_spec else "可开始",
    "disabled": not (build.cad_revision_id or build.drawing_task_id),
}
```

- [ ] **Step 1: Replace the existing future-node test with a failing enabled-node test**

```python
@pytest.mark.asyncio
async def test_tree_enables_fusion_when_a_build_has_at_least_one_source():
    repository = MemoryComponentBuildRepository()
    build = await repository.create_build(**build_fields())
    await repository.attach_step(build.id, model_id=model_id, revision_id=revision_id)
    service = make_service(repository)
    tree = await service.get_tree()
    fusion = find_build_node(tree, str(build.id))["children"][1]
    assert fusion["id"] == f"{build.id}:fusion"
    assert fusion["disabled"] is False
    assert fusion["status"] == "ready"
```

Add a second test that saving a ComponentSpec changes the node to `completed`.

- [ ] **Step 2: Run tree tests and verify RED**

Expected: the current node remains `future` and disabled.

- [ ] **Step 3: Implement the data fusion tree node**

Replace only the data-fusion child. Keep publish validation as a disabled future node.

- [ ] **Step 4: Run tree and backend regression tests**

Run the Task 2 full backend command. Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add backend/app/component_builds/service.py backend/tests/test_component_build_service.py
git commit -m "feat: enable component data fusion tree node"
```

### Task 4: Data Fusion Frontend

**Files:**
- Modify: `frontend/src/service/api/cad.ts`
- Modify: `frontend/src/typings/api/cad.d.ts`
- Modify: `frontend/src/views/component-build/index.vue`

**Interfaces:**
- `fuseComponentBuild(buildId: string, overwrite?: boolean): Promise<FusionResponse>`
- `Api.ComponentBuild.FusionResponse`
- `Api.ComponentBuild.FusionField`

- [ ] **Step 1: Add frontend API contract and call**

Define:

```ts
interface FusionField {
  path: string;
  value: unknown;
  source: 'build' | 'drawing' | 'step' | 'derived';
  confidence: number;
  decision: 'filled' | 'preserved' | 'conflict';
  needs_review: boolean;
}

interface FusionResponse {
  build_id: string;
  status: 'completed';
  summary: {
    filled: number;
    preserved: number;
    conflicts: number;
    needs_review: number;
  };
  fields: FusionField[];
  warnings: string[];
  component_spec: Record<string, any>;
}
```

Add a POST request to `/api/component-builds/${buildId}/fusion`.

- [ ] **Step 2: Enable fusion in tree normalization**

Change `isFutureNode` so it excludes `fusion`. Remove the unconditional `nodeType === 'fusion'` disable rule. Add `isFusionNode`.

- [ ] **Step 3: Implement fusion page state and actions**

Add refs:

```ts
const fusionLoading = ref(false);
const fusionReport = ref<Api.ComponentBuild.FusionResponse | null>(null);
```

Add:

```ts
async function runFusion(overwrite = false) {
  if (!selectedBuildId.value) return;
  fusionLoading.value = true;
  try {
    const { data, error } = await fuseComponentBuild(selectedBuildId.value, overwrite);
    if (error || !data) return;
    fusionReport.value = data;
    componentSpec.value = null;
    await loadTree({ preserveSelection: true });
    window.$message?.success(overwrite ? '重新融合完成' : '数据融合完成');
  } finally {
    fusionLoading.value = false;
  }
}
```

The default primary button calls `runFusion(false)`. The overwrite action uses an Element Plus confirmation dialog before `runFusion(true)`.

- [ ] **Step 4: Implement the fusion page**

Render:

- Build name and “数据融合” title.
- STEP and drawing source statuses.
- “只填空值，不覆盖人工修改” policy copy.
- Primary “开始数据融合” button.
- Secondary “重新融合并覆盖” action.
- Filled, preserved, conflict, and review counters after success.
- Conflict/review field table sorted before ordinary fields.
- “查看 ComponentSpec” button that selects `${buildId}:component_spec`.

Do not add a nested card layout. Use the existing detail section and definition-list patterns.

- [ ] **Step 5: Run frontend static verification**

Run:

```powershell
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit Task 4**

```powershell
git add frontend/src/service/api/cad.ts frontend/src/typings/api/cad.d.ts frontend/src/views/component-build/index.vue
git commit -m "feat: add component data fusion workspace"
```

### Task 5: XMS06-DN80 Real-Data Verification

**Files:**
- No production files expected.
- Update tests only if real-data verification reveals a missing deterministic rule.

**Interfaces:**
- Build ID: `14f8e7e9-d940-4625-a89f-9c85791e003d`
- Drawing task: `00fc241a-7c10-4a4c-9e22-79ce5e6f8e18`
- STEP revision: `2586911e-b5b4-4b26-8b08-c1fc73d69da3`

- [ ] **Step 1: Start backend in the `3dcad` environment and frontend**

```powershell
conda activate 3dcad
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 5181
```

Start the frontend on an unused port with `VITE_SERVICE_BASE_URL=http://127.0.0.1:5181`.

- [ ] **Step 2: Call real fusion endpoint in default mode**

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"overwrite":false}' `
  http://127.0.0.1:5181/api/component-builds/14f8e7e9-d940-4625-a89f-9c85791e003d/fusion
```

Verify `filled > 0`, `conflicts` is reported, and the response belongs to the expected build.

- [ ] **Step 3: Verify ComponentSpec values through the API**

Verify:

- Identity ID is `flange-001`.
- Standard is `HG/T 20592-2009`.
- DN and PN are 80 and 16.
- D/K/n/L/C are 200/160/8/18/20.
- Pipe OD, wall thickness, raised face diameter/height, and overall height are 89/3.2/138/2/50.
- Bore diameter is 82.6 only when STEP confirmation was found.
- Preset name is `DN80-PN16`.

- [ ] **Step 4: Verify non-destructive repeat**

Edit one fused field through the ComponentSpec PUT endpoint, call fusion again with `overwrite=false`, and verify the manual value remains. Restore the original value with `overwrite=true`.

- [ ] **Step 5: Verify the browser workflow**

In the 图元建库 tree:

1. Expand `/连接与紧固类/法兰/XMS06-DN80/1.0.0`.
2. Open “数据融合”.
3. Verify source status, start action, and result counters.
4. Open ComponentSpec and verify populated form fields.
5. Preview YAML and confirm template order and Chinese comments remain intact.

- [ ] **Step 6: Run final regressions**

```powershell
D:\anaconda\envs\3dcad\python.exe -m pytest backend\tests\test_component_spec_fusion.py backend\tests\test_component_build_service.py backend\tests\test_component_build_api.py backend\tests\test_component_build_catalog.py backend\tests\test_parser_runner.py -q -p no:cacheprovider
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit any verification-driven corrections**

Only if Step 2-6 required code changes:

```powershell
git add backend/app/component_builds/fusion.py backend/app/component_builds/fusion_sources.py backend/app/component_builds/service.py backend/app/component_builds/router.py backend/app/component_builds/schemas.py backend/tests/test_component_spec_fusion.py backend/tests/test_component_build_service.py backend/tests/test_component_build_api.py frontend/src/service/api/cad.ts frontend/src/typings/api/cad.d.ts frontend/src/views/component-build/index.vue
git commit -m "fix: align component fusion with XMS06 data"
```
