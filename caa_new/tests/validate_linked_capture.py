"""Validate a real CATProduct capture with linked CATPart evidence.

Run from caa_new: python tests/validate_linked_capture.py build_linked_after
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def records(bundle: Path, name: str) -> list[dict]:
    """读取一个 JSONL 产物，忽略空行并保留原始对象字段。"""
    with (bundle / name).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate(bundle: Path, *, min_typed: int, min_linked_bodies: int) -> dict[str, int]:
    """核对关联件类型化参数、拓扑和对象身份均来自同一完整证据包。"""
    objects = {item["object_id"]: item for item in records(bundle, "object_entities.jsonl")}
    references = records(bundle, "product_references.jsonl")
    facets = records(bundle, "semantic_facets.jsonl")
    topology = records(bundle, "topology_entities.jsonl")
    linked_documents = {
        item["referenced_document_id"]
        for item in references
        if item.get("reference_document_kind") == "catpart"
        and item.get("referenced_document_id")
    }
    assert linked_documents, "bundle has no linked CATPart documents"
    native = [
        facet
        for facet in facets
        if facet.get("facet_kind") in {"native_feature_type", "opaque_native_object"}
    ]
    identities = [(facet["subject_id"], facet["facet_kind"]) for facet in native]
    assert len(identities) == len(set(identities)), "duplicate native facets for one object"
    assert all(facet["subject_id"] in objects for facet in native), "facet subject missing"
    typed = [
        facet
        for facet in native
        if facet.get("decode_level") == "typed"
        and objects[facet["subject_id"]].get("document_id") in linked_documents
    ]
    linked_bodies = [
        entity
        for entity in topology
        if entity.get("topology_kind") == "body"
        and entity.get("subject_id") in linked_documents
    ]
    assert len(typed) >= min_typed, f"linked typed facets: {len(typed)} < {min_typed}"
    assert len(linked_bodies) >= min_linked_bodies, (
        f"linked topology bodies: {len(linked_bodies)} < {min_linked_bodies}"
    )
    return {
        "objects": len(objects),
        "linked_documents": len(linked_documents),
        "linked_typed_facets": len(typed),
        "linked_bodies": len(linked_bodies),
    }


def main() -> None:
    """解析验收参数，并以非零退出码报告证据不完整。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--min-typed", type=int, default=1)
    parser.add_argument("--min-linked-bodies", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(validate(args.bundle, min_typed=args.min_typed,
                              min_linked_bodies=args.min_linked_bodies), ensure_ascii=False))


if __name__ == "__main__":
    main()
