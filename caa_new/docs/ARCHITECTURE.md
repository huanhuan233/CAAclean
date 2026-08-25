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

## R21 mkmk Source Discovery

The first real R21 mkmk run in this environment did not recursively compile implementation files under `src\app`, `src\engine`, `src\caa`, `src\reconstruction`, or `src\output`. It linked only generated CAA files and failed with a missing executable entry point.

To keep the logical source tree intact, `src` contains an R21 compatibility layer:

- `BuildApp.cpp`
- `BuildEngine.cpp`
- `BuildCaa.cpp`
- `BuildReconstruction.cpp`
- `BuildOutput.cpp`

These files contain only `#include` directives for implementation files in their module directories. They are build glue only and contain no business logic. Nested `.cpp` files must not be compiled separately at the same time, or duplicate definitions would result.
