# Architecture

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
