# CATIA V5R21 CAA Parser MVP Architecture

Schema version: `cad_parse_mvp_v0`.

The MVP is one CAA Framework and one load module because the repository started empty. Logical layers remain separated by C++ contracts and focused source files, without creating empty Frameworks that would complicate R21 IdentityCard maintenance.

## Runtime flow

`CadParseBatch` parses arguments, creates `SessionGuard`, opens a CATPart read-only through `DocumentGuard`, registers compile-time core decoders, and invokes `UniversalFeatureCrawler`. The crawler records the document and Part specification container, obtains the Part through `CATIPrtContainer`, recursively visits `CATISpecObject::ListComponents`, and supplements that entrance with verified `CATIContainer::ListMembersHere("CATISpecObject")` enumeration. A process-local pointer set prevents cycles; pointer values never enter IR.

Children are sorted by Late Type, display name, and internal name before traversal. IDs are assigned only after sorting and are revision-local (`F000001`, ...). If all three keys are equal, R21 exposes no verified persistent object key in the current PublicInterfaces; this limitation is diagnosed/documented rather than replaced by a pointer address.

Every enumerated object gets a base `FeatureRecord` before decoder selection. `FeatureTypeRegistry` chooses by explicit priority and stable decoder ID. A typed decoder failure or exception is isolated and falls back to `GenericFeatureDecoder`; a failed generic read becomes an `OpaqueObjectRecorder` record. The conservation invariant is checked before output.

## Logical module mapping

- CadParseInterfaces: `CadParseContracts.h` pure-data records and contracts.
- CadParseCommon / Diagnostics / Registry / DecodersCore: `CadParseCore.cpp`.
- CadParseIR / Relations: `CadParseIR.h/.cpp`; relationships are created by discovery only when both endpoints exist.
- CadParseRuntime / Discovery / native adapters: `CadParseCAA.h/.cpp`.
- CadParseBatch: `CadParseBatch.cpp`.
- License-free tests: `CadParseSelfTests.cpp` and `tests/CadParseCoreTestMain.cpp`.

No IR type owns or serializes a CAA pointer, address, session handle, or document handle. CAA objects are confined to the runtime/discovery translation unit.

## Current verified scope

The crawler covers the Part root, aggregation tree exposed by `ListComponents`, and CATISpecObject members exposed by the root `CATIContainer`. This is not a claim of universal CATPart coverage. ProtectedInterfaces are not used. `references` and `input_of` are not emitted because the current MVP does not yet have a verified, stable endpoint-resolution pass. `contains` and `parent_of` are emitted for verified aggregation edges.

`native_type` is empty for CATISpecObject records because no documented Public R21 native runtime-class-name getter has been verified. The documented Late Type is written to `startup_type`; this avoids mislabelling Late Type as native type. `TODO(R21_API_VERIFY)` applies to native runtime type, persistent stable feature keys, Body/HybridBody marker interfaces, and reference/input endpoint semantics.
