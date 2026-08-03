# CAA V5R21 API Evidence

All entries below were checked against the local V5R21 installation under its `PublicInterfaces` and/or an installed `.edu` sample. No ProtectedInterfaces are used.

| API/class | Header | Framework | Project use | Local evidence | Access | Status |
|---|---|---|---|---|---|---|
| `Create_Session`, `Delete_Session` | `CATSessionServices.h` | ObjectModelerBase | `SessionGuard` | Header plus `CAAAniExport.m/src/main.cpp` | Public L1 | compiled and smoke-tested |
| `CATDocumentServices::OpenDocument`, `Remove` | `CATDocumentServices.h` | ObjectModelerBase | `DocumentGuard` | Header plus `CAAAniExport.m/src/main.cpp` | Public L1 | compiled and smoke-tested read-only |
| `CATDocument::DisplayName` | `CATDocument.h` | ObjectModelerBase | document record | Public header | Public L1 | compiled and smoke-tested |
| `CATInit::GetRootContainer` | `CATInit.h` | ObjectModelerBase | Part root entrance | `CAAAuiCreateFixConstraintInPart.cpp` | Public | compiled and smoke-tested |
| `CATIPrtContainer::GetPart` | `CATIPrtContainer.h` | MecModInterfaces | Part entrance | Header plus AssemblyUI sample | Public L1/U3 | compiled and smoke-tested |
| `CATIContainer::ListMembersHere` | `CATIContainer.h` | ObjectModelerBase | root container member entrance | Header documentation and release example | Public L1/U3 | compiled and smoke-tested |
| `SEQUENCE(CATBaseUnknown_ptr)` indexing/length | `sequence_CATBaseUnknown_ptr.h` | ObjectModelerSystem | exception-safe release of every enumerated member | Public header plus indexed `CATIContainer` example; `length()` itself is marked nodoc | Public L1/U1 | compiled and smoke-tested; constrained to ownership cleanup |
| `CATISpecObject::GetName`, `GetDisplayName` | `CATISpecObject.h` | ObjectSpecsModeler | names and stable sort key | Public header | Public L1/U3 | compiled and smoke-tested |
| `CATISpecObject::GetType`, `GetSuperType` | `CATISpecObject.h` | ObjectSpecsModeler | Late Type and super types | Header explicitly describes Late Type | Public L1/U3 | compiled and smoke-tested |
| `CATISpecObject::GetFeatContainer`, `IsUpToDate` | `CATISpecObject.h` | ObjectSpecsModeler | generic base state | Public header | Public L1/U3 | compiled and smoke-tested |
| `CATISpecObject::ListComponents` | `CATISpecObject.h`, `CATLISTV_CATISpecObject.h` | ObjectSpecsModeler | aggregation traversal | Header specifies delete ownership and unordered result | Public L1/U3 | compiled and smoke-tested |
| `CATUnicodeString::ConvertToUTF8` | `CATUnicodeString.h` | System | UTF-8 IR output | Public header documents buffer sizing | Public L1 | compiled and smoke-tested |
| `QueryInterface` for `CATISpecObject`, `CATIPrtPart`, `CATIContainer`, `CATIPrtContainer` | corresponding headers | listed frameworks | registered interface probes only | local headers/IIDs | Public | compiled and smoke-tested |

## Evidence gaps

- `TODO(R21_API_VERIFY)`: no documented Public R21 getter for a feature's native implementation/runtime class name was confirmed. It is left empty, not guessed.
- `TODO(R21_API_VERIFY)`: no `CATIBody.h` or `CATIHybridBody.h` exists in the installed PublicInterfaces. The MVP Body/HybridBody decoders therefore match only conservative Late Type strings and perform base decoding.
- `TODO(R21_API_VERIFY)`: stable persistent feature identity is not exposed by the verified interfaces. IDs are deterministic for the verified traversal/sort inputs and revision-local.
- `TODO(R21_API_VERIFY)`: `GetReference` is documented, but formal `references`/`input_of` emission needs a second-pass endpoint map and semantics validation. It is not guessed in this version.
- CATIA Service Pack and Hot Fix programmatic APIs were not confirmed. Manifest fields are present and report `unknown`.
