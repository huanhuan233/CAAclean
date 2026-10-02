"""将已发布的 CAA/Feature Center 语义资产回填 PostgreSQL，不重新运行 CATIA。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

from app.cad.repository import CadRepository
from app.component_builds.ingest import FEATURE_EVIDENCE_KINDS, NATIVE_EVIDENCE_FILES, _iter_native_jsonl, _publish_native_progress, _verify_feature_evidence_assets
from app.core.config import Settings
from app.db import models  # noqa: F401 -- 让 create_all 知道全部表
from app.db.session import SessionLocal, init_db


async def backfill_revision(revision_id: UUID, work_root: Path) -> dict[str, dict[str, int]]:
    """只读取该 Revision 已发布的文件；每类导入完整后才发布对应 PostgreSQL 标记。"""
    root = work_root / str(revision_id)
    native = root / "native-caa"
    feature = root / "feature-center"
    result: dict[str, dict[str, int]] = {}
    async with SessionLocal() as session:
        repository = CadRepository(session)
        revision = await repository.get_revision(revision_id)
        if revision is None:
            raise ValueError(f"revision missing in PostgreSQL: {revision_id}")
        if (native / "manifest.json").is_file():
            manifest = json.loads((native / "manifest.json").read_text(encoding="utf-8"))
            if not str(manifest.get("schema_version") or "").startswith("caa_capture_"):
                raise ValueError(f"unsupported native bundle schema: {revision_id}")
            previous = revision.parse_manifest or {}
            if not (previous.get("native_tree_storage") or {}).get("complete") or not (
                previous.get("native_property_storage") or {}
            ).get("complete"):
                await _publish_native_progress(repository, revision_id, native)
            counts = await repository.replace_native_evidence(
                revision_id,
                {kind: _iter_native_jsonl(native / filename) for kind, filename in NATIVE_EVIDENCE_FILES.items()
                 if kind not in FEATURE_EVIDENCE_KINDS},
            )
            await repository.update_revision_manifest(revision_id, {
                "native_evidence_storage": {"backend": "postgresql", "counts": counts, "complete": True}
            })
            result["native"] = counts
        if (feature / "manifest.json").is_file():
            _verify_feature_evidence_assets(
                feature, json.loads((feature / "manifest.json").read_text(encoding="utf-8"))
            )
            payload = {
                "canonical_features": _iter_native_jsonl(feature / "canonical_features.jsonl"),
                "measurements": _iter_native_jsonl(feature / "measurements.jsonl"),
                "topology_faces": _iter_native_jsonl(feature / "topology_faces.jsonl"),
                "feature_geometry_links": _iter_native_jsonl(feature / "feature_geometry_links.jsonl"),
            }
            selection_index = feature / "lightweight" / "selection_index.json"
            if selection_index.is_file():
                payload["selection_index"] = iter([json.loads(selection_index.read_text(encoding="utf-8"))])
            counts = await repository.replace_native_evidence(revision_id, payload, replace_all=False)
            await repository.update_revision_manifest(revision_id, {
                "feature_evidence_storage": {"backend": "postgresql", "counts": counts, "complete": True}
            })
            result["feature"] = counts
    return result


async def main() -> int:
    """枚举当前配置工作目录中的合法 Revision 目录；失败时以非零退出码列出未完成项。"""
    await init_db()
    work_root = Path(Settings().cad_work_dir).resolve()
    failures: list[str] = []
    for directory in sorted(work_root.iterdir()):
        if not directory.is_dir():
            continue
        try:
            revision_id = UUID(directory.name)
        except ValueError:
            continue
        if not (directory / "native-caa" / "manifest.json").is_file() and not (
            directory / "feature-center" / "manifest.json"
        ).is_file():
            continue
        try:
            result = await backfill_revision(revision_id, work_root)
            summary = ", ".join(f"{group}={sum(counts.values())}" for group, counts in result.items())
            print(f"{revision_id}: {summary}")
        except Exception as exc:
            failures.append(f"{revision_id}: {exc}")
    for failure in failures:
        print(f"FAILED {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
