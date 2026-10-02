"""Compare deterministic core artifacts before and after a parser change."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


CORE_ARTIFACTS = (
    "object_entities.jsonl",
    "tree_occurrences.jsonl",
    "property_facts.jsonl",
    "semantic_facets.jsonl",
    "topology_entities.jsonl",
    "geometry_entities.jsonl",
)


def digest(path: Path) -> str:
    """分块计算文件哈希，避免把数百 MB 的 JSONL 一次读进内存。"""
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def compare(before: Path, after: Path) -> list[str]:
    """返回核心产物中内容变化的文件名，缺失文件也视为变化。"""
    changed = []
    for name in CORE_ARTIFACTS:
        previous = before / name
        current = after / name
        if not previous.is_file() or not current.is_file() or digest(previous) != digest(current):
            changed.append(name)
    return changed


def main() -> None:
    """从命令行验收同一输入的确定性证据是否保持一致。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    changed = compare(args.before, args.after)
    if changed:
        raise SystemExit("changed artifacts: " + ", ".join(changed))
    print(f"{len(CORE_ARTIFACTS)} core artifacts identical")


if __name__ == "__main__":
    main()
