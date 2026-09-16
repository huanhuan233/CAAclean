# Progressive Native Tree Loading

## Goal

For CATPart and CATProduct builds, expose the CAA native tree as soon as the
CATIA worker has completed, without waiting for the slower FreeCAD Feature
Center and GLB generation stage. The center viewer continues loading in the
background and appears when its assets become ready.

## Design

The ingest pipeline publishes native CAA asset metadata immediately after the
worker bundle is downloaded and extracted. This intermediate publication does
not mark the revision complete; it only makes the immutable native bundle
discoverable while the revision remains in `feature_center_processing`.

The viewer contract becomes progressive:

- `native_capture` and `native_semantics` may be available while the overall
  status is still `processing`.
- `viewer_asset` remains `null` until the complete Feature Center bundle has
  passed its existing validation.
- The final ready contract remains backward compatible.

The Feature Center page consumes that contract in two phases:

1. When native tree data is available, load and render the left navigation
   immediately even if the contract is not ready.
2. Continue polling while processing. When viewer assets appear, load the GLB,
   mappings, and recognized features without clearing the already visible tree.

If Feature Center later fails, the native tree remains browseable and the
center panel reports that lightweight geometry is unavailable.

## Error Handling

Native tree publication validates the same CAA bundle files already required
by the native reader. A missing or invalid native bundle does not claim tree
availability. Feature Center failures retain the existing native-only fallback.

## Tests

- Backend ingest test: worker completion publishes native semantics before the
  Feature Center command returns.
- Backend service test: a processing revision with native assets returns a
  progressive viewer contract and serves the native tree.
- Frontend test: a processing contract loads the native tree, schedules the
  next poll, and does not require a viewer asset.
- Existing completed-viewer and failure tests remain green.
