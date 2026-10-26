import subprocess
import sys
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


# 用途：验证 Sidecar 暴露 build、validate、inspect 三个稳定子命令。
def test_feature_center_cli_exposes_required_commands() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "feature_center.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "build" in completed.stdout
    assert "validate" in completed.stdout
    assert "inspect" in completed.stdout


@pytest.mark.asyncio
async def test_build_passes_new_capture_hole_payload_to_existing_fusion(tmp_path, monkeypatch):
    from scripts import feature_center as cli

    native = tmp_path / "native"
    native.mkdir()
    (native / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    (native / "object_entities.jsonl").write_text(json.dumps({"object_id": "object_49", "update_status": "up_to_date"}) + "\n", encoding="utf-8")
    (native / "tree_occurrences.jsonl").write_text(json.dumps({"occurrence_id": "occurrence_49", "object_id": "object_49"}) + "\n", encoding="utf-8")
    (native / "native_features.jsonl").write_text(json.dumps({"native_feature_id": "semantic_facet_49", "feature_id": "object_49", "decoder_id": "NativeHoleDecoder", "native_hole": {"diameter_mm": 10}}) + "\n", encoding="utf-8")
    (native / "features.jsonl").write_text(json.dumps({"feature_id": "occurrence_49"}) + "\n", encoding="utf-8")
    step = tmp_path / "part.step"
    step.write_text("STEP", encoding="utf-8")
    seen = []

    async def fake_parser(*_args):
        return object()

    monkeypatch.setattr(cli, "inspect_step_input", lambda _path: SimpleNamespace(sha256="abc"))
    monkeypatch.setattr(cli, "run_freecad_parser", fake_parser)
    monkeypatch.setattr(cli, "build_bundle_from_parser_result", lambda _step, _parser, native_features: seen.extend(native_features) or SimpleNamespace(shape_hash="shape", topology_entities=[], topology_relations=[], canonical_features=[]))
    monkeypatch.setattr(cli.FeatureCenterBundleWriter, "write", lambda *_args: None)
    monkeypatch.setattr(cli, "_write_step_curves_asset", lambda *_args: None)
    monkeypatch.setattr(cli, "validate_bundle", lambda *_args: [])

    result = await cli._build(SimpleNamespace(step=str(step), native_bundle=str(native), output=str(tmp_path / "output"), visual_review_mode="disabled"))

    assert result == 0
    assert len(seen) == 1
    assert seen[0]["feature_id"] == "object_49"
    assert seen[0]["decoder_id"] == "NativeHoleDecoder"
    assert seen[0]["native_hole"]["diameter_mm"] == 10


@pytest.mark.asyncio
async def test_build_reuses_existing_step_parse_and_brep_without_freecad(tmp_path, monkeypatch):
    from scripts import feature_center as cli

    step = tmp_path / "part.step"
    step.write_text(
        "ISO-10303-21;HEADER;FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));ENDSEC;"
        "DATA;#1=SI_UNIT(.MILLI.,.METRE.);ENDSEC;END-ISO-10303-21;",
        encoding="ascii",
    )
    revision_id = uuid4()
    face_id = uuid4()
    mesh_id = uuid4()
    parser_result = {
        "revision_id": str(revision_id),
        "parser_name": "FreeCAD",
        "parser_version": "1.1",
        "schema_version": "cad_parse_v2",
        "unit": "mm",
        "bounding_box": {"min": [0, 0, 0], "max": [1, 1, 0]},
        "summary": {"face_count": 1},
        "entities": [{
            "id": str(face_id), "revision_id": str(revision_id),
            "parent_entity_id": None, "entity_type": "face", "tree_path": "/root/face-0",
            "geometry_type": "plane", "area": 0.5,
            "geometry": {"normal": [0.0, 0.0, 1.0]},
        }],
        "relations": [],
        "meshes": [{
            "id": str(mesh_id), "revision_id": str(revision_id), "entity_id": str(face_id),
            "mesh_type": "face", "positions": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "indices": [[0, 1, 2]], "linear_deflection": 0.1,
            "vertex_count": 3, "triangle_count": 1,
        }],
        "parse_manifest": {},
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(parser_result), encoding="utf-8")
    brep_dir = tmp_path / "brep"
    brep_dir.mkdir()
    (brep_dir / f"{face_id}.brep").write_bytes(b"BREP fixture")

    async def forbidden_parser(*_args, **_kwargs):
        raise AssertionError("STEP must not be parsed a second time")

    monkeypatch.setattr(cli, "run_freecad_parser", forbidden_parser)
    output = tmp_path / "bundle"
    result = await cli._build(SimpleNamespace(
        step=str(step), native_bundle=None, output=str(output),
        visual_review_mode="disabled", parser_result=str(result_path), brep_dir=str(brep_dir),
    ))

    assert result == 0
    assert (output / "lightweight" / "model.glb").read_bytes()[:4] == b"glTF"
    assert (output / "geometry" / "index.json").is_file()
