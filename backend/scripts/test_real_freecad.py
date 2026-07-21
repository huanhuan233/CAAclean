from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.cad.parser_runner import run_freecad_parser
from app.core.config import Settings


DEFAULT_STEP_PATH = Path(r"D:\3D解析\XMS06-DN80.stp")


def validate_step_path(path: Path) -> Path:
    if path.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("file must be a STEP/STP file")
    if not path.exists():
        raise ValueError(f"file does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"file is empty: {path}")
    return path


async def run_real_parse(step_path: Path) -> dict:
    source_path = validate_step_path(step_path)
    settings = Settings()
    revision_id = uuid4()
    work_root = Path(settings.cad_work_dir)
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cad-real-parse-", dir=work_root) as temp_dir:
        temp_source = Path(temp_dir) / f"source{source_path.suffix.lower()}"
        shutil.copyfile(source_path, temp_source)
        result = await run_freecad_parser(temp_source, revision_id, Path(temp_dir), settings)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FreeCAD parser against a real STEP/STP file.")
    parser.add_argument("step_path", nargs="?", type=Path, default=DEFAULT_STEP_PATH)
    args = parser.parse_args()

    result = asyncio.run(run_real_parse(args.step_path))
    print(
        json.dumps(
            {
                "parser_name": result.get("parser_name"),
                "parser_version": result.get("parser_version"),
                "schema_version": result.get("schema_version"),
                "summary": result.get("summary"),
                "entity_count": len(result.get("entities", [])),
                "relation_count": len(result.get("relations", [])),
                "mesh_count": len(result.get("meshes", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
