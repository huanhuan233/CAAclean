# Native semantic capture and target architecture

## Module boundary

`CaaSemanticPropertyExtractor::Extract` publishes existing `PropertyFact` records. It hides interface discovery, typed values, units, references, ownership and per-channel failures. The engine does not need to know composite SDK classes. Private parameter, geometry and native-attribute readers keep SDK details behind this boundary. Chinese comments explain compatibility, lifetime and unit rules.

No source document updates, geometry creation, XML-value injection or database replacement are performed by these readers. Existing tree identities and legacy parameter keys remain intact. Linked-document properties are read while their document is alive; FTA keeps the existing recursive document scan.

## Captured channels

- Knowledge parameters: string, integer, boolean and real/dimension values; SI numeric value separately from CATIA display text (`0.00033 m` versus `0.33mm`). Empty string, false, zero, unsupported and failed are distinct.
- Native comments: `CATIAllowUserInfo.GetComment`.
- Composite materials: name/type, cured/uncured thickness, width, warning/limit angles, surface weight, density and material cost per mass.
- Plies/groups: orientation, rosette frame, reference surface, draping direction and native reference IDs where the referenced object was captured.
- Direction palette: numeric directions and native RGB values.
- Ply geometry: native contour vertices, total edge length, existing composite surface area and center. Vertices are explicitly marked as **native enumeration, not ordered outer/inner contour loops**.
- Native composite attributes: typed scalar values and SDK dumps of lists/references; unknown storage units remain unknown. Attributes such as `CPDContext` and `NonStructural` are retained without guessing their semantic enum mapping.
- FTA: independent text, flag-note and NOA text channels, plus separate validation and diagnostics. An interface being available does not mean complete annotation semantics were recovered.

## Validation and limits

The supplied composite CATPart produced 16,706 objects and 34,191 occurrences, unchanged from baseline. Ten acceptance checks passed against the final reviewed build, including four 1 m² ply surfaces and native contour vertices at ±500 mm. Material thickness is 0.00033 m, density 1500 kg/m³, and unit cost 23.8 USD/kg.

The pre-change backup executable and final executable were both run against the same ordinary `kuang.CATPart` and five-child `001-000.CATProduct`. Eight comparisons passed for object IDs/labels, occurrence hierarchy/paths, previously captured parameter values and assembly transforms. Their occurrence counts are 941 and 1,328 respectively. The relevant backend suite passed 34 tests, including preservation of units, empty/false values and failures through the existing database projection. C++ core/FTA serialization tests and the native x86 build passed. No production database was modified by these tests.

Do not call this a complete reproduction of `0917.xml`: ordered contour loop classification, translated stack/structural flags and native per-ply weight/cost are not yet exposed as equivalent typed XML fields. In particular, the XML's 0.000495 kg does not agree with 1 m² × 0.00033 m × 1500 kg/m³; the collector does not manufacture that number or substitute surface-inertia default mass. Raw native attributes are evidence, not asserted business semantics.

The available composite fixture has no FTA sets. Multiline FTA serialization is tested, but nonempty native FTA extraction still needs a representative source model. The R21 L0 composite interfaces are isolated here, not a promise of binary compatibility with every CATIA release. Unsupported channels are recorded without discarding ordinary part properties.

## 32-bit and 64-bit caller configuration

Choose the complete pair:

| Target | Platform | Bitness | Script | Native binary |
| --- | --- | --- | --- | --- |
| x86 | `intel_a` | `32` | `run_r21_x86.bat` | `intel_a/code/bin/CadCapture.exe` |
| x64 | `win_b64` | `64` | `run_r21_x64.bat` | `win_b64/code/bin/CadCapture.exe` |

For x64 deployment set `CAA_CAPTURE_PLATFORM=win_b64` and `CAA_CAPTURE_BITNESS=64`. Remove both optional `CAA_CAPTURE_RUNNER` and `CATIA_WORKER_CAA_RUN_SCRIPT` overrides to select the script automatically, or set both explicitly to the x64 script. Configure `CAA_RADE_ROOT` / `CAA_PREREQ_ROOT` for that host. Restart the idle worker after changing its configuration.

The caller checks platform/bitness agreement, known script mismatch, executable existence and the PE machine header before launch. Missing x64 output never silently runs x86. A custom wrapper must honor the selected target itself; PE validation is of the configured project executable.

This host retains its existing `intel_a/32` settings. Native x86 is compiled and exercised locally. Python target-selection tests use x86/x64 PE fixtures; they do not prove a real x64 CATIA launch. A real x64 build and matching CATIA runtime are still required on an equipped machine.

## Repeatable checks

Run `tools/test_core_vs2008.bat` for SDK-independent serialization/core behavior. Run `python tests/test_semantic_bundle.py <composite-bundle>` from `caa_new` for the provided native fixture. Run `python -m pytest tests/test_caa_runner_platforms.py` from `backend` for target selection.

Run `python tests/test_semantic_compatibility.py <before-bundle> <after-bundle>` from `caa_new` against captures of the same source to verify compatibility. Do not compare unrelated historical bundles or assume capture-local IDs are stable across different source documents.

Acceptance captures belong in new `test-output/semantic-*` directories. Never replace the user's existing imported result simply to test the new collector.
