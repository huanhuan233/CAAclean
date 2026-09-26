# CAA_NEW Web Integration Audit

Generated from local workspace `D:\CAAclean`.

## Summary

New CATPart/CATProduct upload parsing now uses `caa_new` through the shared `CaaNewRunner`.

- Capture engine: `caa_new`
- Runner: `caa_new\tools\run_r21_x86.bat`
- Platform: `intel_a`
- Bitness: `32`
- Parser executable: `caa_new\intel_a\code\bin\CadCapture.exe`
- Legacy parser executable `CadParseMvp.exe`: not used by new Web ingest or HTTP Worker production paths

## Active Production References

| file | old_behavior | replacement | status |
| --- | --- | --- | --- |
| `backend/app/component_builds/ingest.py` | Local CATIA route called `3DjiexiCAA\tools\run_r21_x64_host_intel_a.bat`. | Calls shared `CaaNewRunner` with `caa_new\tools\run_r21_x86.bat`, `intel_a`, `_MkmkOS_BitMode=32`. | replaced |
| `backend/app/component_builds/ingest.py` | CATProduct route called `_append_catpart_feature_trees`, scanned sibling CATPart files, matched by name, and wrote `product_feature_tree.jsonl`. | Removed the production call and deleted the helper. CATProduct tree comes from CAA_NEW normalized occurrence/product artifacts. | removed |
| `backend/app/catia_worker/server.py` | Worker assembled its own CAA command. | Worker calls the same shared `CaaNewRunner`; health reports `capture_engine=caa_new`, `capture_platform=intel_a`, `capture_bitness=32`. | replaced |
| `backend/app/component_builds/router.py` | Allowed `native-caa/part-feature-trees/` assets even when not listed in Viewer Contract. | Removed the special whitelist. Asset access must be listed in controlled contract URLs. | removed |
| `frontend/src/views/feature-center/index.vue` | Preferred `product_feature_tree_url` for CATProduct feature tree display. | Prefers CAA_NEW `tree_occurrences_url` plus `object_entities_url` and `product_instances_url`; legacy URLs remain fallback only. | replaced |

## Remaining Legacy-Compatible References

| file | reason | status |
| --- | --- | --- |
| `backend/app/component_builds/service.py` | Still exposes `product_feature_tree_url` if an old bundle already has it, so historical tasks remain readable. New ingest no longer generates it. | compatibility only |
| `frontend/src/typings/api/cad.d.ts` | Keeps legacy optional URL fields so older Viewer Contracts still typecheck. | compatibility only |
| `backend/app/catia_worker/server.py` and `backend/app/component_builds/ingest.py` | `3DjiexiCAA\tools\export_catpart_step.ps1` remains the existing CATIA Automation STEP export path for optional lightweight geometry. It is not the CAA parser. | optional geometry export |
| `backend/tests/test_catia_step_export_script.py` | Verifies the existing STEP export script path. | test |
| `caa_new/tools/*legacy*`, `compare_*`, `validate_*` | Use old parser as migration oracle/regression comparison. | regression only |
| `caa_new/docs/*`, `caa_new/README.md` | Historical migration docs still mention x64/legacy examples. | documentation debt |

## Notes

- New upload parsing must not execute `CadParseMvp.exe`.
- New upload parsing must not execute `run_r21_x64` or `run_r21_x64_host_intel_a`.
- STEP/GLB failure no longer discards a successful CAA_NEW native capture; Viewer Contract can return `viewer_asset=null` with `native_capture.available=true`.
- No production code returns local absolute parser paths to the frontend.
