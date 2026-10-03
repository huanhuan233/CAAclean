# Architecture

本页描述 C++ 采集层内部依赖。采集包到 PostgreSQL、Feature Center 和 Vue 的本轮深模块边界见 [端到端状态](../../docs/END_TO_END_STATUS.md)。`LegacyArtifactProjection` 的 `features.jsonl` 是树兼容投影，不能当作专用 Hole/Pad/Pocket 语义入口；专用载荷在 `native_features.jsonl`，后端适配器负责统一新旧 Schema。

CadCapture is organized as deep modules. The public surface of each module is intentionally small, while implementation details remain inside the owning directory.

## Dependency Direction

```text
app
  -> engine
       -> model
       -> caa
       -> reconstruction
       -> output

caa -> model
reconstruction -> model
output -> model
model -> C++ standard library
```

`app` parses command-line arguments and calls `ModelCaptureEngine`. It does not include CATIA headers and does not know pipeline stages.

`engine` owns orchestration. `ModelCaptureEngine` validates the request, calls CAA-facing modules, runs reconstruction planning and validation, and commits artifacts.

`model` contains pure data structures only. It does not store CATIA pointers or include CAA headers.

`caa` is the only layer that may touch CAA APIs. It owns CATIA session lifetime, document lifetime, and capability-family extractors. Public CAA module headers expose project model types and opaque handles, not concrete `CATI*` interfaces.

`reconstruction` chooses and validates the reconstruction route from model data. It has no CAA dependency.

`output` hides file and JSON writing behind `ArtifactRepository`. It has no CAA dependency.

## SDK Catalog And Capability Coverage

`catalog/r21_api_catalog.json` indexes the R21 SDK PublicInterfaces headers discovered on this machine. `catalog/r21_framework_catalog.json` indexes Frameworks and their PublicInterfaces. This index is intentionally broader than the compiled code.

All headers are indexed. Only verified capabilities are compiled. Only fixture-verified capabilities may be declared implemented.

The capability status chain is:

```text
indexed
header_verified
compile_verified
runtime_verified
extractor_implemented
fixture_verified
reconstruction_verified
```

The architecture distinguishes these separate facts:

- the SDK contains a header;
- a small compile probe can include the interface;
- a real runtime object supports QueryInterface;
- an extractor exists in the capability-family module;
- a real fixture verifies the extractor;
- reconstruction validation has accepted the extracted facts.

Code modules are organized by capability family, not by CAA header. For example, `CaaProductEnumerator` may later use multiple ProductStructure headers internally, `CaaSketchExtractor` may use sketch and constraint headers internally, and `CaaPropertyExtractors` may use product, Knowledge, Inertia, or Visualization interfaces internally. External modules must not know the concrete `CATI*` interfaces used inside those extractors.

IdentityCard and Imakefile must include only Frameworks needed by capabilities that are compiled in the current stage. Indexed Frameworks are not automatically build dependencies.

## R21 mkmk Source Discovery

The first real R21 mkmk run in this environment did not recursively compile implementation files under `src\app`, `src\engine`, `src\caa`, `src\reconstruction`, or `src\output`. It linked only generated CAA files and failed with a missing executable entry point.

To keep the logical source tree intact, `src` contains an R21 compatibility layer:

- `BuildApp.cpp`
- `BuildEngine.cpp`
- `BuildCaaCapabilityBroker.cpp`
- `BuildCaaDocumentHandle.cpp`
- `BuildCaaDocumentScanner.cpp`
- `BuildCaaPartEnumerator.cpp`
- one matching `BuildCaa*.cpp` bridge for each compiled CAA module
- `BuildReconstruction.cpp`
- `BuildOutput.cpp`
- `BuildModel.cpp`

These files contain only `#include` directives for implementation files in their module directories. They are build glue only and contain no business logic. CAA uses one bridge compilation unit per CAA module so individual capability families can be added or removed without creating one huge CAA translation unit. Nested `.cpp` files must not be compiled separately at the same time, or duplicate definitions would result.

## Phase 1A CATPart Tree

Phase 1A opens native CATPart/CATProduct files read-only with `CATDocumentServices::OpenDocument`. CATPart tree capture starts from the real `CATDocument`, obtains the part container through `CATInit` and `CATIPrtContainer`, then walks `CATISpecObject::ListComponents` and supplemental `CATIContainer::ListMembersHere` members.

Each CATIA object is persisted as an `ObjectEntity`; each place it appears in the captured tree is persisted as an `ObjectOccurrence`. The retained fields include `display_name`, `internal_name`, `startup_type`, parent occurrence, `source_index`, `tree_path`, `occurrence_path`, occurrence role, enumeration source, presentation status, and `update_status`.

Primary tree traversal uses the active recursion path only to stop cycles; it does not globally suppress a second legal occurrence of the same entity. `CATIContainer::ListMembersHere` is supplemental discovery. Objects already present in the primary tree receive supplemental evidence on the entity; newly discovered objects are attached under the PartSpecContainer as `supplemental_discovery` with `presentation_status=non_primary`, never as extra roots.

Unknown objects are preserved with explicit status instead of being dropped. Normal output includes `object_entities.jsonl` and `tree_occurrences.jsonl`; `LegacyArtifactProjection` also emits compatible `features.jsonl` and `relations.jsonl`. Legacy features are occurrence projections so relation endpoints are referentially valid.

Native feature semantics are additive. `CaaNativeFeatureExtractors` maps captured `startup_type` values into type-only `SemanticFacet` records when the family is known and into opaque semantic records otherwise. This stage does not claim feature parameter payload extraction; `payload_extraction_status` records that boundary explicitly.

## Final Body Topology And Tessellation

For a root CATPart, `CaaTopologyExtractor` reopens the already loaded native document boundary and reads the final main solid through `CATIPrtPart::GetSolid`. It persists `TopologyEntity` rows for the final body and for each enumerated face, edge, vertex, and volume from `CATBody::GetAllCells`. The records keep revision-local identity, counts, dimensions, domain counts, available centers, face area, and edge length as pure data.

Face tessellation is recorded as `GeometryEntity` range summaries produced by `CATICGMBodyTessellator`. This stage captures point/strip/fan/polygon/triangle counts and Face to triangle-range evidence, but not triangle coordinate payloads.

Exact analytic surface/curve parameter decoding, full B-Rep adjacency/wire/coedge graph, and ResultOUT cell-to-final-body Face mapping remain separate capabilities until their fixtures are migrated and verified.

## Feature Result Identity

During root CATPart topology extraction, the spec tree is traversed again inside `CaaTopologyExtractor`. Shape features that expose `CATIShapeFeatureBody` are matched back to captured `ObjectEntity` rows by the same display/internal/startup identity tuple captured from the native spec tree. When `GetResultOUT` returns a geometrical result body, the extractor records a `feature_result_body` topology entity and a `has_resultout_body` row in `feature_dependencies.jsonl`.

This is identity evidence for a feature result body, not a claim that ResultOUT cells have been mapped to final-body faces.

## FTA/TPS Evidence

`CaaFtaExtractor` queries `CATITPSDocument` on the native document and records set-level PMI evidence from `CATITPSDocument::GetSets`. For each set that exposes `CATITPSSet`, the extractor records TPS component count and geometry reference count. It does not infer GD&T semantics and does not create FTA-to-topology links without a verified Public API path.

Documents with no TPS sets still produce empty `pmi_entities.jsonl` and `fta_sets.jsonl`; that means the scan completed with no set evidence, not that annotations were dropped.

## Phase 1B CATProduct Tree

Phase 1B keeps CATProduct structure as first-class model data instead of flattening it into object features. `ProductReferenceEntity` records the shared reference identity and `ProductOccurrence` records each instance placement, parent occurrence, source index, tree path, occurrence path, child count, load status, and absolute 4x4 transform.

The CAA-facing implementation opens the real CATProduct document read-only, obtains roots through `CATIDocRoots::GiveDocRoots`, queries `CATIProduct`, walks `CATIProduct::GetChildren("CATIProduct")`, and reads instance transforms through `CATIMovable::GetAbsPosition`. This is implemented inside `CaaProductEnumerator`; no external layer sees `CATIProduct`, `CATIMovable`, or other concrete `CATI*` interfaces.

`product_references.jsonl`, `product_occurrences.jsonl`, and `document_links.jsonl` are normalized outputs. `LegacyArtifactProjection` projects product occurrences into compatible `features.jsonl` and writes parent relations, while preserving referential validity.

Current verified coverage is native CATProduct BOM capture, reference/instance separation, absolute transforms, linked CATPart/CATProduct document graph evidence exposed by `CATILinkableObject`, and CATPart definition projection under product instances. Recovery of broken/unloaded external links and recursive parsing of linked CATProduct definitions remain separate future capabilities unless a fixture proves the Public API path.
