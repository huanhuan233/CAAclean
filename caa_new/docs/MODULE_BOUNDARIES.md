# Module Boundaries

Only `src/caa` may include CATIA/CAA headers. `src/model`, `src/reconstruction`, `src/output`, `src/engine` public headers, and `src/app` must remain CAA-free.

`CaaRuntime` owns CAA Session creation and cleanup. Its callers only see `Open`, `Close`, and `IsOpen`.

`ModelCaptureEngine.h` exposes only portable C++ types and project data types. It does not expose `CATDocument`, `CATBaseUnknown`, `CATISpecObject`, `HRESULT`, `IUnknown`, or `CATUnicodeString`.

`ObjectEntity` represents a captured native object or logical document object. `ObjectOccurrence` represents one placement or appearance of an object in a document/product tree. One object may have many occurrences.

Facets should be added as focused model records such as semantic, geometry, topology, PMI, or property facts. Avoid a universal context object and avoid collapsing all facts into `map<string,string>`.

The old schema should later be produced by `LegacyArtifactProjection`, not by making CAA extractors write legacy files directly.
