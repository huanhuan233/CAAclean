import subprocess
import sys
import json
from pathlib import Path
from types import SimpleNamespace

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
