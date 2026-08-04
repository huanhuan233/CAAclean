import hashlib
import json
from pathlib import Path

import pytest

from app.feature_center.bundle import FeatureCenterBundleWriter, validate_bundle
from app.feature_center.contracts import (
    CanonicalFeature,
    FeatureCenterBundle,
    GeometryRefs,
    Measurement,
    Observation,
    stable_id,
)
from app.feature_center.service import build_bundle_from_parser_result
from app.feature_center.step_input import inspect_step_input


# 用途：构造最小但引用完整的 Feature Center 数据，供写出和确定性测试复用。
def _make_bundle(source_path: Path) -> FeatureCenterBundle:
    observation = Observation(
        observation_id=stable_id("OBS", "part-1", "native-hole-1"),
        part_id="PART000001",
        source_kind="native_caa",
        source_id="NativeHoleDecoder",
        source_version="1.0.0",
        proposed_family="hole",
        proposed_subtype="blind",
        geometry_refs=GeometryRefs(face_ids=["FACE000001"]),
        classification_confidence=1.0,
        localization_confidence=0.9,
        measurement_confidence=1.0,
        status="verified",
    )
    canonical = CanonicalFeature(
        feature_center_id=stable_id("FC", "part-1", "hole-1"),
        part_id="PART000001",
        family="hole",
        subtype="blind",
        source_observation_ids=[observation.observation_id],
        native_feature_ids=["F000001"],
        geometry_refs=GeometryRefs(face_ids=["FACE000001"]),
        review_state="auto_verified",
    )
    measurement = Measurement(
        measurement_id=stable_id("MEAS", canonical.feature_center_id, "diameter"),
        feature_center_id=canonical.feature_center_id,
        name="diameter",
        value=10.0,
        unit="mm",
        tolerance=0.01,
        source="brep_deterministic",
        method="cylinder_radius_twice",
        algorithm_version="1.0.0",
        input_face_ids=["FACE000001"],
        validity="valid",
    )
    return FeatureCenterBundle(
        input_file_name=source_path.name,
        input_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        parts=[{"part_id": "PART000001", "name": "测试零件"}],
        topology_entities=[{
            "entity_id": "FACE000001", "entity_type": "face", "geometry_type": "cylinder"
        }],
        observations=[observation],
        canonical_features=[canonical],
        measurements=[measurement],
    )


# 用途：验证稳定编号只由语义输入决定，不受调用顺序或进程地址影响。
def test_stable_id_is_reproducible() -> None:
    assert stable_id("FACE", "shape-a", "fingerprint-a") == stable_id(
        "FACE", "shape-a", "fingerprint-a"
    )
    assert stable_id("FACE", "shape-a", "fingerprint-a") != stable_id(
        "FACE", "shape-a", "fingerprint-b"
    )


# 用途：验证 Bundle 写出具有稳定顺序、文件哈希和默认路径脱敏。
def test_bundle_writer_is_deterministic_and_redacts_source_path(tmp_path: Path) -> None:
    source_dir = tmp_path / "含隐私的目录"
    source_dir.mkdir()
    source = source_dir / "样件.step"
    source.write_bytes(b"ISO-10303-21;END-ISO-10303-21;")
    bundle = _make_bundle(source)

    first = tmp_path / "run-1"
    second = tmp_path / "run-2"
    FeatureCenterBundleWriter().write(bundle, first)
    FeatureCenterBundleWriter().write(bundle, second)

    core_files = (
        "parts.jsonl",
        "observations.jsonl",
        "canonical_features.jsonl",
        "measurements.jsonl",
    )
    for relative in core_files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "cad_feature_center_v1"
    assert manifest["input"]["file_name"] == "样件.step"
    assert manifest["input"]["absolute_path_included"] is False
    assert str(source_dir) not in (first / "manifest.json").read_text(encoding="utf-8")
    assert manifest["output_files"]["observations.jsonl"]["sha256"] == hashlib.sha256(
        (first / "observations.jsonl").read_bytes()
    ).hexdigest()


# 用途：验证正式目录已存在时写出会明确失败，不会覆盖一份看似完整的旧结果。
def test_bundle_writer_refuses_to_overwrite_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "sample.step"
    source.write_bytes(b"step")
    output = tmp_path / "bundle"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        FeatureCenterBundleWriter().write(_make_bundle(source), output)
    assert (output / "keep.txt").read_text(encoding="utf-8") == "keep"


# 用途：验证直接 STEP 输入只产出确定性拓扑，不会凭空制造 Native Hole 或视觉结果。
def test_step_only_service_builds_topology_without_fake_features(tmp_path: Path) -> None:
    source = tmp_path / "part.step"
    source.write_text(
        "ISO-10303-21;HEADER;FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));ENDSEC;"
        "DATA;#1=SI_UNIT(.MILLI.,.METRE.);ENDSEC;END-ISO-10303-21;",
        encoding="ascii",
    )
    parser_result = {
        "parser_name": "FreeCAD",
        "parser_version": "1.1.3",
        "unit": "mm",
        "bounding_box": {"min": [0, 0, 0], "max": [10, 10, 10]},
        "entities": [
            {"id": "legacy-face", "revision_id": "any", "entity_type": "face",
             "geometry_type": "plane", "area": 100.0,
             "geometry": {"normal": [0.0, 0.0, 1.0]}},
        ],
        "relations": [],
        "meshes": [],
    }

    bundle = build_bundle_from_parser_result(inspect_step_input(source), parser_result)

    assert bundle.shape_hash
    assert len(bundle.topology_entities) == 1
    assert bundle.canonical_features == []
    assert bundle.observations == []
    assert bundle.vision_enabled is False
    assert bundle.feature_recognition_scope == "native_hole_guided_only"


# 用途：验证 Bundle 校验器能发现哈希篡改和 Canonical Feature 的悬空 Face 引用。
def test_bundle_validator_rejects_hash_and_reference_corruption(tmp_path: Path) -> None:
    source = tmp_path / "sample.step"
    source.write_bytes(b"step")
    output = tmp_path / "bundle"
    FeatureCenterBundleWriter().write(_make_bundle(source), output)
    assert validate_bundle(output) == []

    with (output / "canonical_features.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")
    errors = validate_bundle(output)
    assert any("BUNDLE_HASH_MISMATCH" in error for error in errors)


# 用途：验证 staging 引用损坏时不会发布正式目录，也不会留下半成品。
def test_bundle_writer_validates_before_transaction_publish(tmp_path: Path) -> None:
    source = tmp_path / "sample.step"
    source.write_bytes(b"step")
    bundle = _make_bundle(source)
    bundle.measurements[0].input_face_ids = ["FACE-MISSING"]
    output = tmp_path / "bundle"

    with pytest.raises(ValueError, match="FC_BUNDLE_STAGING_INVALID"):
        FeatureCenterBundleWriter().write(bundle, output)
    assert not output.exists()
