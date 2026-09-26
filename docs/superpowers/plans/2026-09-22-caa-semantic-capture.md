# CAA semantic capture implementation plan

**Goal:** Capture typed parameters, composite properties and annotation text without changing existing tree identity or legacy property contracts.

**Architecture:** Keep the public orchestration interface small. A semantic-property module hides R21 interface discovery, units, per-field failures and ownership; its output is the existing PropertyFact. Parameter reading is shared by ordinary parameters and composite fields. FTA remains a separate module and retains its existing records while adding text evidence. Do not merge unrelated source values by matching display names.

**Tech stack:** CATIA V5R21, VS2008 C++03, portable x86/x64 caller, existing JSONL artifacts and Python acceptance tests. This machine validates native x86 only; x64 requires a matching compiler, runtime and native executable on its target host.

## Constraints and design decisions

- Preserve the dirty workspace and existing string keys, object IDs and occurrence relationships.
- Read only: no Set, Valuate, Update, Save or geometry creation calls; Chinese implementation comments explain unit/lifetime/compatibility rules.
- Empty string, zero, false, unsupported and failed are distinct. A successful QueryInterface is not successful extraction.
- Keep SI numeric values separate from CATIA display strings. Never infer units from names or substitute CATIInertia density for composite material density.
- Prefer typed composites interfaces over scraping UI text or hard-coded attributes. R21 L0 composites interfaces remain inside the adapter; runtime capability failure is recorded.
- Existing linked-part lifecycle captures properties before document close. Preserve the existing recursive root FTA scan so nested assemblies remain in scope. No production data replacement during acceptance runs.
- User requested direct execution, so implement locally without extra design-approval rounds. The requesting-code-review skill requires a read-only reviewer; no implementation work is delegated.

## Tasks

- [x] Add executable acceptance tests over real normalized bundles; establish baseline failures. Ten checks cover typed parameters, SI material units, four ply directions, palette, contour, area, raw native attributes and unchanged tree counts.
- [x] Add internal PropertyFact evidence helpers and FTA multiline text serialization core tests; run VS2008 core tests red/green. SDK-dependent readers are validated using actual native captures rather than fake interfaces.
- [x] Add CaaSemanticPropertyExtractor with shared typed parameter reader and composites/axis readers. Wire once per live native binding. Keep existing graphics/inertia code unchanged.
- [x] Extend FTA text capture without changing recursive scan scope; separate actual text, validation and diagnostics. Record supported-but-unread statuses explicitly.
- [x] Build x86 using installed SDK and capture the composite fixture into isolated acceptance directories. Test both caller targets using PE fixtures, including missing/mismatched targets. Native x64 execution remains unverified.
- [x] Compare the same ordinary part/product captured by the pre-change backup EXE and final EXE: eight checks pass for object identity/labels, tree hierarchy, old parameter values and assembly transforms. Existing database property projection also preserves new typed values and failures.
- [x] Independently review diffs, correct findings and document actual coverage and limits; do not claim full capture based on node counts.

## Verification commands

`D:\anaconda\envs\3dcad\python.exe caa_new/tests/test_semantic_bundle.py <bundle>`

`caa_new\tools\test_core_vs2008.bat`

`caa_new\tools\build_r21_x86.bat` with CAA_RADE_ROOT=D:\CATIA\Rade21 and CAA_PREREQ_ROOT=D:\CATIA.

`caa_new\tools\run_r21_x86.bat --input <fixture> --output <new-acceptance-directory>`

`python -m pytest tests/test_caa_runner_platforms.py tests/test_catia_worker_server.py tests/test_caa_new_linked_properties.py tests/test_native_property_store.py tests/test_native_tree_store.py -q` (backend directory)
