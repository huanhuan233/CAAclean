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

`caa` is the only layer that may touch CAA APIs. In this bootstrap, only `CaaRuntime.cpp` creates and deletes a CATIA CAA Session. Other CAA modules expose narrow future-ready interfaces and record explicit `not_implemented` diagnostics.

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
- `BuildCaa.cpp`
- `BuildReconstruction.cpp`
- `BuildOutput.cpp`
- `BuildModel.cpp`

These files contain only `#include` directives for implementation files in their module directories. They are build glue only and contain no business logic. Nested `.cpp` files must not be compiled separately at the same time, or duplicate definitions would result.
