# Component Geometry Fusion Design

## Goal

Use parsed STEP feature candidates and flange-domain rules to populate the
coordinate-system, geometry recipe, output, and validation sections of the
ComponentSpec draft. The result must be useful for review while clearly
distinguishing derived values from confirmed source data.

## Coordinate Convention

- Normalize rotational components to a right-handed local coordinate system.
- Use the detected main axis as local +Z after normalization.
- Use the circular-pattern center as the local origin when a reliable bolt-hole
  pattern exists; otherwise use the main-axis origin.
- Derive local +X from the pattern center to a deterministic first member.
  When member centers are unavailable, choose a stable perpendicular vector.
- Compute local +Y as `Z cross X`.
- For a weld-neck flange, describe the origin as the sealing-face center, +Z as
  pointing from the sealing face toward the weld-neck end, and zero rotation as
  the first bolt-hole direction. These semantic descriptions require review.

The ComponentSpec stores the local frame expressed in the current STEP model
coordinates. For XMS06-DN80, local +Z therefore follows the detected STEP main
axis instead of being hard-coded to global +Z. This keeps the metadata aligned
with the geometry currently shown by the CAD viewer.

## Geometry Recipe

For a weld-neck flange:

- representation: `parametric_recipe`
- modeling kernel: `OpenCascade`
- generator mode: `dsl_or_script`
- preferred engine: `CadQuery`
- compatible engine version: `2.x`
- target script contract: `flange-weld-neck.py:build_component`
- construction:
  1. revolve the main body profile around local Z;
  2. cut the circular bolt-hole pattern;
  3. apply the hub-to-flange root fillet when the radius exists.
- output: STEP AP242, preserve names and colors, deterministic filename template.

These generator values define the target implementation contract and are
marked for review. `script_required_for_release` remains true, so a draft may
be edited without the file but release validation must fail until the real
generator artifact is attached.

## Validation Defaults

- Require complete required parameters, valid enums, and constraints.
- Require one positive-volume solid with a closed, manifold shell and no
  self-intersection.
- Use 0.01 mm dimensional tolerance and 0.1 degree angular tolerance.
- Derive the expected through-hole count from `bolt_hole_count`.
- Express the expected bounding box with flange diameter and overall height
  parameters.
- Enable coordinate-frame and interface validation.
- Require STEP AP242 round-trip with product name, colors, and units preserved.
- Block release while review remains pending.

## Merge Policy

Default fusion fills empty fields only. Overwrite fusion refreshes fields owned
by the fusion rules but still does not fabricate people, dates, hashes, or
generator files. Derived semantic fields are marked for review in the fusion
report.

## Verification

- Unit tests cover axis normalization, fallback orientation, flange geometry
  recipe, validation defaults, and non-destructive merge behavior.
- The XMS06-DN80 build is fused against its linked drawing and STEP revision.
- The ComponentSpec page is checked for populated coordinate, geometry, and
  validation sections.
