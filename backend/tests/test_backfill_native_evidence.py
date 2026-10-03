"""恢复计划不得把旧的空识别文件误报成已修复。"""

import json
from uuid import uuid4

import pytest

from scripts import backfill_native_evidence as recovery
from scripts.backfill_native_evidence import inspect_revision, parse_arguments


def test_recovery_inspection_requires_recompute_for_old_empty_hole_output(tmp_path):
    revision_id = uuid4()
    root = tmp_path / str(revision_id)
    native = root / "native-caa"
    feature = root / "feature-center"
    native.mkdir(parents=True)
    feature.mkdir()
    (native / "manifest.json").write_text(json.dumps({"schema_version": "caa_capture_v1"}), encoding="utf-8")
    (native / "native_features.jsonl").write_text(json.dumps({
        "feature_id": "O1", "decoder_id": "NativeHoleDecoder", "native_hole": {"diameter_mm": 10}
    }) + "\n", encoding="utf-8")
    (feature / "manifest.json").write_text("{}", encoding="utf-8")
    (feature / "canonical_features.jsonl").write_text("", encoding="utf-8")
    (root / "exported.stp").write_text("ISO-10303-21;", encoding="utf-8")

    plan = inspect_revision(revision_id, tmp_path)

    assert plan["native_typed_hole_count"] == 1
    assert plan["canonical_feature_count"] == 0
    assert plan["recommended_mode"] == "recompute"


def test_cli_defaults_to_read_only_and_requires_scope():
    args = parse_arguments(["--revision", str(uuid4())])
    assert args.apply is False
    assert args.recompute is False


def test_recovery_inspection_allows_native_bundle_without_optional_features(tmp_path):
    revision_id = uuid4()
    native = tmp_path / str(revision_id) / "native-caa"
    native.mkdir(parents=True)
    (native / "manifest.json").write_text('{"schema_version":"caa_capture_v1"}', encoding="utf-8")
    (native / "property_facts.jsonl").write_text("", encoding="utf-8")

    plan = inspect_revision(revision_id, tmp_path)

    assert plan["recommended_mode"] == "backfill"
    assert plan["native_definition_count"] == 0


@pytest.mark.asyncio
async def test_recompute_database_failure_restores_previous_bundle(tmp_path, monkeypatch):
    revision_id = uuid4()
    root = tmp_path / str(revision_id)
    old = root / "feature-center"
    staged = root / "feature-center-staged-test"
    old.mkdir(parents=True)
    staged.mkdir()
    (old / "marker").write_text("old", encoding="utf-8")
    (staged / "marker").write_text("new", encoding="utf-8")

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    class Repository:
        def __init__(self, _session):
            pass

        async def get_revision(self, _revision_id):
            return object()

    async def staged_build(_root, _native):
        return staged

    async def native_publish(_repository, _revision_id, _native):
        return {}

    async def fail_feature_publish(*_args, **_kwargs):
        raise ValueError("database failed")

    monkeypatch.setattr(recovery, "inspect_revision", lambda *_: {
        "recommended_mode": "recompute", "missing": [], "native_available": True,
        "feature_bundle_available": True, "exported_step_available": True,
    })
    monkeypatch.setattr(recovery, "SessionLocal", Session)
    monkeypatch.setattr(recovery, "CadRepository", Repository)
    monkeypatch.setattr(recovery, "_build_staged_feature_bundle", staged_build)
    monkeypatch.setattr(recovery, "publish_native_capture", native_publish)
    monkeypatch.setattr(recovery, "_feature_manifest_values", lambda _bundle: {})
    monkeypatch.setattr(recovery, "publish_feature_evidence", fail_feature_publish)

    with pytest.raises(ValueError, match="database failed"):
        await recovery.backfill_revision(revision_id, tmp_path, recompute=True)

    assert (old / "marker").read_text(encoding="utf-8") == "old"
    assert any((path / "marker").read_text(encoding="utf-8") == "new"
               for path in root.glob("feature-center-failed-*") if (path / "marker").is_file())
