"""只读检查、限定回填及既有 Hole 识别结果补算；不重新采集 CATIA。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

from app.cad.repository import CadRepository
from app.component_builds.caa_new_bundle import CaaNewBundleReader
from app.component_builds.native_persistence import publish_feature_evidence, publish_native_capture
from app.core.config import Settings
from app.db import models  # noqa: F401 -- init_db 需要注册全部模型
from app.db.session import SessionLocal, init_db
from app.feature_center.bundle import validate_bundle


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """写入必须显式选择范围和 --apply；无参数不扫描或修改整个工作目录。"""
    parser = argparse.ArgumentParser(description="检查并恢复 CAD Revision 的已保存结果")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--revision", type=UUID, help="限定一个 Revision")
    scope.add_argument("--all", action="store_true", help="扫描全部 Revision；写入还需 --apply")
    parser.add_argument("--apply", action="store_true", help="确认执行入库，默认只读")
    parser.add_argument("--recompute", action="store_true", help="从已有 STEP 补算 Feature Center；仅限单 Revision")
    parser.add_argument("--work-root", type=Path, help="可选隔离工作目录；默认读取配置")
    args = parser.parse_args(argv)
    if args.recompute and (not args.apply or not args.revision):
        parser.error("--recompute requires --revision and --apply")
    return args


def _count_jsonl(path: Path) -> int:
    """统计非空记录，不把不存在的通道解释为合法零记录。"""
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as stream:
        return sum(bool(line.strip()) for line in stream)


def inspect_revision(revision_id: UUID, work_root: Path) -> dict:
    """只读分析采集语义、旧识别记录及补算来源，给出明确恢复路径。"""
    root = work_root / str(revision_id)
    native = root / "native-caa"
    feature = root / "feature-center"
    native_present = (native / "manifest.json").is_file()
    feature_present = (feature / "manifest.json").is_file()
    definitions = list(CaaNewBundleReader(native).iter_canonical_native_features()) if (
        native_present and (native / "native_features.jsonl").is_file()
    ) else []
    typed_holes = sum(row.get("decoder_id") == "NativeHoleDecoder" and bool(row.get("native_hole"))
                      for row in definitions)
    canonical_count = _count_jsonl(feature / "canonical_features.jsonl") if feature_present else 0
    step_present = (root / "exported.stp").is_file()
    missing: list[str] = []
    if not native_present and not feature_present:
        missing.append("native-caa/manifest.json or feature-center/manifest.json")
    if typed_holes and canonical_count == 0 and not step_present:
        missing.append("exported.stp")
    if typed_holes and canonical_count == 0:
        mode = "recompute" if step_present else "insufficient_source"
    elif native_present or feature_present:
        mode = "backfill"
    else:
        mode = "insufficient_source"
    feature_errors = validate_bundle(feature) if feature_present else []
    return {
        "revision_id": str(revision_id), "native_available": native_present,
        "native_definition_count": len(definitions), "native_typed_hole_count": typed_holes,
        "feature_bundle_available": feature_present, "canonical_feature_count": canonical_count,
        "exported_step_available": step_present, "recommended_mode": mode,
        "missing": missing, "feature_bundle_errors": feature_errors,
    }


def _feature_manifest_values(bundle: Path) -> dict:
    """补算后同步显示资产和计数，避免数据库新语义继续指向旧 GLB 映射。"""
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    canonical_count = _count_jsonl(bundle / "canonical_features.jsonl")
    link_count = _count_jsonl(bundle / "feature_geometry_links.jsonl")
    return {
        "viewer_asset": {
            "bundle_root": "feature-center", "glb": "feature-center/lightweight/model.glb",
            "scene_manifest": "feature-center/manifest.json",
            "face_mesh_map": "feature-center/lightweight/face_mesh_map.json",
            "feature_mesh_map": "feature-center/lightweight/feature_mesh_map.json",
            "selection_index": "feature-center/lightweight/selection_index.json",
        },
        "viewer_summary": {"recognized_feature_count": canonical_count},
        "feature_center": {"available": canonical_count > 0, "bundle_available": True,
                           "mapping_available": link_count > 0, "feature_face_mapping_count": link_count},
        "feature_center_manifest": {"lightweight": manifest.get("lightweight") or {},
                                    "performance": manifest.get("performance") or {}},
    }


async def _build_staged_feature_bundle(root: Path, native: Path) -> Path:
    """从已保存 STEP 和 CAA 包调用既有 Sidecar，输出到不覆盖旧结果的暂存目录。"""
    output = root / f"feature-center-staged-{uuid4().hex}"
    command = [sys.executable, str(Path(__file__).with_name("feature_center.py")),
               "build", "--step", str(root / "exported.stp"), "--native-bundle", str(native),
               "--output", str(output), "--visual-review-mode", "disabled"]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.PIPE)
    _stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"Feature Center recompute failed ({process.returncode}): "
                           f"{stderr.decode(errors='replace')[-1000:]}")
    errors = validate_bundle(output)
    if errors:
        raise ValueError("staged Feature Center bundle invalid: " + "; ".join(errors))
    return output


async def backfill_revision(revision_id: UUID, work_root: Path, *, recompute: bool = False) -> dict:
    """限定 Revision 幂等发布；补算失败时保留旧文件与旧数据库记录。"""
    plan = inspect_revision(revision_id, work_root)
    if plan["recommended_mode"] == "insufficient_source":
        raise ValueError("source evidence insufficient: " + "; ".join(plan["missing"]))
    if recompute and not plan["exported_step_available"]:
        raise ValueError("recompute requires exported.stp")
    root = work_root / str(revision_id)
    native = root / "native-caa"
    feature = root / "feature-center"
    async with SessionLocal() as session:
        repository = CadRepository(session)
        if await repository.get_revision(revision_id) is None:
            raise ValueError(f"revision missing in PostgreSQL: {revision_id}")
        result: dict = {"mode": "recompute" if recompute else "backfill", "counts": {}, "skipped": [], "errors": []}
        if plan["native_available"]:
            try:
                native_manifest = await publish_native_capture(repository, revision_id, native)
                result["counts"]["native"] = (native_manifest.get("native_evidence_storage") or {}).get("counts") or {}
            except Exception as exc:
                result["errors"].append({"scope": "native", "reason": str(exc)})
        if not recompute:
            if plan["feature_bundle_available"] and not plan["feature_bundle_errors"]:
                try:
                    result["counts"]["feature"] = await publish_feature_evidence(repository, revision_id, feature)
                except Exception as exc:
                    result["errors"].append({"scope": "feature", "reason": str(exc)})
            elif plan["feature_bundle_errors"]:
                result["skipped"].append({"scope": "feature", "reason": plan["feature_bundle_errors"]})
            if plan["recommended_mode"] == "recompute":
                result["skipped"].append({"scope": "recognition_recompute", "reason": "requires explicit --recompute"})
            return result

        staged = await _build_staged_feature_bundle(root, native)
        backup = root / f"feature-center-previous-{uuid4().hex}"
        moved_old = feature.is_dir()
        if moved_old:
            feature.rename(backup)
        try:
            staged.rename(feature)
            result["counts"]["feature"] = await publish_feature_evidence(
                repository, revision_id, feature, manifest_values=_feature_manifest_values(feature),
            )
        except Exception:
            if feature.is_dir():
                feature.rename(root / f"feature-center-failed-{uuid4().hex}")
            if moved_old:
                backup.rename(feature)
            raise
        result["previous_feature_bundle"] = backup.name if moved_old else None
        return result


def _is_uuid(value: str) -> bool:
    """全量扫描仅接受 UUID 命名目录，不碰其他工作文件。"""
    try:
        UUID(value)
        return True
    except ValueError:
        return False


async def main(argv: list[str] | None = None) -> int:
    """默认只输出检查计划；显式 --apply 才连接数据库执行有范围的发布。"""
    args = parse_arguments(argv)
    work_root = (args.work_root or Path(Settings().cad_work_dir)).resolve()
    revisions = [args.revision] if args.revision else sorted(
        UUID(path.name) for path in work_root.iterdir() if path.is_dir() and _is_uuid(path.name)
    )
    if not args.apply:
        failed = False
        for revision_id in revisions:
            try:
                print(json.dumps(inspect_revision(revision_id, work_root), ensure_ascii=False, sort_keys=True))
            except Exception as exc:
                failed = True
                print(json.dumps({"revision_id": str(revision_id), "status": "failed", "reason": str(exc)},
                                 ensure_ascii=False), file=sys.stderr)
        return 1 if failed else 0
    await init_db()
    failed = False
    for revision_id in revisions:
        try:
            if args.all:
                plan = inspect_revision(revision_id, work_root)
                if plan["recommended_mode"] == "insufficient_source":
                    print(json.dumps({"revision_id": str(revision_id), "status": "skipped",
                                      "reason": "no publishable saved evidence"}, ensure_ascii=False))
                    continue
            result = await backfill_revision(revision_id, work_root, recompute=args.recompute)
            print(json.dumps({"revision_id": str(revision_id), **result}, ensure_ascii=False, sort_keys=True))
            failed = failed or bool(result["errors"])
        except Exception as exc:
            failed = True
            print(json.dumps({"revision_id": str(revision_id), "status": "failed", "reason": str(exc)},
                             ensure_ascii=False), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
