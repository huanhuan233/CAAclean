# Decoder Extension Guide

Implement `IFeatureDecoder` in a focused source file. The decoder must expose a stable ASCII decoder ID, an explicit priority, a side-effect-free `Match`, and a `Decode` that only reads the supplied native view and populates the existing `FeatureRecord`. It must not traverse globally or retain a CAA pointer.

Match in this order when evidence permits: a verified registered interface key, documented StartUp/Late Type, documented super type, verified native type, container/family, and finally display name at low confidence. Do not probe arbitrary interfaces. Add each allowed probe to the native adapter with its header/framework evidence.

Priorities are explicit integers; choose a value relative to the core decoders and document the reason. Same-priority matches are legal but generate `DECODER_PRIORITY_TIE`; stable decoder ID wins, independent of registration order. Register the decoder in `RegisterCoreDecoders` for the MVP compile-time factory.

To add output fields, prefer an `attributes` entry for decoder-specific scalar data. Change the versioned core record/schema only when the field is broadly applicable. JSON must go through `JsonArtifactWriter` and `JsonEscape`; do not manually concatenate JSON in decoders.

Add a license-free fake-view test that names the failure it catches, watch it fail, then implement. If output changes, add or update a literal Golden Case. For a CATIA-backed decoder, also run a legal local sample without committing the CATPart.

If an interface, class, header, IID, or link library cannot be confirmed in local R21 PublicInterfaces, Encyclopedia, or `.edu` samples, do not guess it. Add `TODO(R21_API_VERIFY)`, record the gap in `CAA_R21_API_EVIDENCE.md`, and leave the object eligible for Generic/Opaque fallback.

Decoder failures and exceptions must remain object-local. Return a failed `DecodeResult` instead of aborting. Never remove or bypass the Registry's typed-to-Generic-to-Opaque chain, and never increment global coverage counts inside a decoder; the Registry owns those counters exactly once per enumerated object.
