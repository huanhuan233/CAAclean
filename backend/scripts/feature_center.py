"""Feature Center Sidecar 的命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.cad.parser_runner import run_freecad_parser
from app.core.config import Settings
from app.feature_center.bundle import FeatureCenterBundleWriter, validate_bundle
from app.feature_center.fusion import read_jsonl
from app.feature_center.service import build_bundle_from_parser_result
from app.feature_center.step_input import StepInputError, inspect_step_input


# 用途：为同一 STEP Hash 生成稳定解析任务编号，使旧解析器中间结果也能双跑复现。
def _revision_id(step_sha256: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"cad-feature-center:{step_sha256}")


# 用途：执行 build 子命令，串联输入检查、FreeCAD 子进程、稳定拓扑和事务式发布。
async def _build(args: argparse.Namespace) -> int:
    if args.visual_review_mode != "disabled":
        print("FC_VISUAL_MODE_UNSUPPORTED：本轮只允许 disabled", file=sys.stderr)
        return 2
    try:
        step_info = inspect_step_input(args.step)
        settings = Settings()
        output = Path(args.output).resolve()
        with tempfile.TemporaryDirectory(prefix="feature-center-work-", dir=output.parent) as work:
            parser_result = await run_freecad_parser(
                Path(args.step).resolve(), _revision_id(step_info.sha256), Path(work), settings
            )
        native_features = None
        if args.native_bundle:
            native_path = Path(args.native_bundle).resolve() / "features.jsonl"
            if not native_path.is_file():
                raise ValueError("NATIVE_BUNDLE_FEATURES_MISSING")
            native_features = read_jsonl(native_path)
        bundle = build_bundle_from_parser_result(step_info, parser_result, native_features)
        FeatureCenterBundleWriter().write(bundle, output)
        errors = validate_bundle(output)
        if errors:
            print("FC_BUNDLE_VALIDATION_FAILED " + ";".join(errors), file=sys.stderr)
            return 3
        print(json.dumps({
            "status": "success",
            "output": output.name,
            "shape_hash": bundle.shape_hash,
            "topology_entity_count": len(bundle.topology_entities),
            "topology_relation_count": len(bundle.topology_relations),
            "canonical_feature_count": len(bundle.canonical_features),
            "vision_call_count": 0,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (StepInputError, FileExistsError, ValueError, OSError, RuntimeError) as exc:
        print(f"FC_BUILD_FAILED {exc}", file=sys.stderr)
        return 1


# 用途：执行 validate 子命令，结构或哈希损坏时返回非零退出码。
def _validate(args: argparse.Namespace) -> int:
    errors = validate_bundle(args.bundle)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "valid"}, ensure_ascii=False))
    return 0


# 用途：在 Canonical Feature JSONL 中按稳定编号查找单条记录，供人工定位和脚本验收。
def _inspect(args: argparse.Namespace) -> int:
    path = Path(args.bundle) / "canonical_features.jsonl"
    if not path.is_file():
        print("FC_INSPECT_FILE_MISSING", file=sys.stderr)
        return 1
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("feature_center_id") == args.feature_id:
            print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
    print("FC_INSPECT_FEATURE_NOT_FOUND", file=sys.stderr)
    return 1


# 用途：建立三个稳定子命令及其参数约束，不把本机绝对路径写入默认值。
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建和检查 Feature Center Bundle")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="从 STEP 和可选 CAA Bundle 构建结果")
    build.add_argument("--step", required=True)
    build.add_argument("--native-bundle")
    build.add_argument("--output", required=True)
    build.add_argument("--visual-review-mode", default="disabled", choices=["disabled"])
    build.add_argument("--tolerance-profile", default="scale_aware_v1")
    validate = commands.add_parser("validate", help="校验 Bundle 哈希和引用")
    validate.add_argument("--bundle", required=True)
    inspect = commands.add_parser("inspect", help="按编号查看 Canonical Feature")
    inspect.add_argument("--bundle", required=True)
    inspect.add_argument("--feature-id", required=True)
    return parser


# 用途：分派 CLI 子命令，并把异常转换为稳定进程退出码。
def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        return asyncio.run(_build(args))
    if args.command == "validate":
        return _validate(args)
    return _inspect(args)


if __name__ == "__main__":
    raise SystemExit(main())
