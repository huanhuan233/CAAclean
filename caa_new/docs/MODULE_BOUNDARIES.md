# Module Boundaries

Only `src/caa` may include CATIA/CAA headers. `src/model`, `src/reconstruction`, `src/output`, `src/engine` public headers, and `src/app` must remain CAA-free.

SDK catalog files may mention every indexed PublicInterfaces header, but those mentions are data, not compile dependencies. Capability-family modules decide which verified headers they use internally.

`CaaRuntime` owns CAA Session creation and cleanup. Its callers only see `Open`, `Close`, and `IsOpen`.

`ModelCaptureEngine.h` exposes only portable C++ types and project data types. It does not expose `CATDocument`, `CATBaseUnknown`, `CATISpecObject`, `HRESULT`, `IUnknown`, or `CATUnicodeString`.

`ObjectEntity` represents a captured native object or logical document object. `ObjectOccurrence` represents one placement or appearance of an object in a document/product tree. One object may have many occurrences.

`ProductReferenceEntity` represents a shared CATProduct reference. `ProductOccurrence` represents one assembly instance of that reference and carries parent occurrence, source index, occurrence path, load status, and absolute transform. Product instances must not be modeled as one C++ module per CAA header; they belong to the ProductStructure capability family.

`ObjectIdentity.capture_id` is the current capture record ID. Phase 1A does not claim a persistent CATIA native identity; native object de-duplication is session-local and recorded as `identity_method=session_object_equivalence`.

`tree_path` is display-oriented and may include a readable disambiguation suffix for same-name siblings. `occurrence_path` is the machine-unique path and includes source indexes; it must not contain native pointers.

Facets should be added as focused model records such as semantic, geometry, topology, PMI, or property facts. Avoid a universal context object and avoid collapsing all facts into `map<string,string>`.

The old schema is produced by `LegacyArtifactProjection`, not by making CAA extractors write legacy files directly. Legacy features are occurrence projections, so `features.jsonl.feature_id` is an `occurrence_id` and `source_object_id` points back to `object_entities.jsonl`.

External linked-document resolution and CATPart definition projection under product instances are separate capabilities. Linked CATPart documents exposed by CATIA Public APIs are captured once as definitions and projected many times; broken/unloaded links remain explicit diagnostics instead of being mapped to the root document.
