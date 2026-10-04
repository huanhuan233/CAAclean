from app.feature_center.contracts import CanonicalFeature, GeometryRefs, Measurement, Observation
from app.feature_center.fusion import HoleFusionResult
from app.feature_center.geometry_recognition import RecognitionResult
from app.feature_center.service import _associate_verified_geometry


def _native(status: str = "up_to_date") -> CanonicalFeature:
    return CanonicalFeature(
        feature_center_id="native-1", part_id="part", family="hole", subtype="blind_hole",
        source_observation_ids=["native-observation"],
        geometry_refs=GeometryRefs(face_ids=["wall", "bottom"]),
        typed_payload={"native_hole": {"diameter_mm": 10},
                       "geometry_verification": {"status": "verified", "body_wall_face_ids": ["wall"]}},
        provenance={"native_update_status": status},
    )


def _geometry(wall: str = "wall") -> RecognitionResult:
    return RecognitionResult(
        observations=[Observation("geometry-observation", "part", "geometry_recognition",
                                  "rule", "1", "hole")],
        canonical_features=[CanonicalFeature(
            feature_center_id="geometric-1", part_id="part", family="hole", subtype="blind_hole",
            source_observation_ids=["geometry-observation"], review_state="auto_verified",
            geometry_refs=GeometryRefs(face_ids=[wall]),
            typed_payload={"geometry_recognition": {"wall_face_ids": [wall], "diameter_mm": 10.01}},
        )],
        feature_geometry_links=[{"feature_center_id": "geometric-1", "face_id": wall,
                                 "role": "body_wall", "link_id": "old"}],
        measurements=[Measurement("old-measure", "geometric-1", "diameter", 10.01,
                                  "mm", 0.01, "geometry_recognition", "analytic", "1")],
    )


def test_exact_same_wall_retains_both_sources_and_both_parameter_values() -> None:
    fusion = HoleFusionResult(canonical_features=[_native()])
    recognition = _geometry()
    _associate_verified_geometry(fusion, recognition)
    assert recognition.canonical_features == []
    assert len(recognition.observations) == 1
    assert fusion.canonical_features[0].source_observation_ids == ["native-observation", "geometry-observation"]
    assert fusion.canonical_features[0].typed_payload["native_hole"]["diameter_mm"] == 10
    assert fusion.canonical_features[0].typed_payload["geometry_recognition"]["diameter_mm"] == 10.01
    assert recognition.measurements[0].feature_center_id == "native-1"


def test_stale_or_other_wall_does_not_claim_association() -> None:
    for native, geometry in ((_native("not_up_to_date"), _geometry()), (_native(), _geometry("other-wall"))):
        fusion = HoleFusionResult(canonical_features=[native])
        _associate_verified_geometry(fusion, geometry)
        assert len(geometry.canonical_features) == 1
        assert "geometry_recognition" not in native.typed_payload
