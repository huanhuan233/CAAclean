"""将 CAA 采集包作为单个数据库快照发布；格式规则只由 Bundle Reader 负责。"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from uuid import UUID

from app.cad.repository import CadRepository
from app.component_builds.caa_new_bundle import CaaNewBundleReader
from app.component_builds.native_property_store import iter_native_property_rows
from app.component_builds.native_tree_store import native_tree_rows
from app.feature_center.bundle import validate_bundle


NATIVE_ASSET_FILES = {
    "manifest": "manifest.json", "capture_report": "capture_report.json",
    "reconstruction_plan": "reconstruction_plan.json", "object_entities": "object_entities.jsonl",
    "tree_occurrences": "tree_occurrences.jsonl", "features": "features.jsonl",
    "native_features": "native_features.jsonl", "parameters": "parameters.jsonl",
    "property_facts": "property_facts.jsonl", "semantic_facets": "semantic_facets.jsonl",
    "feature_dependencies": "feature_dependencies.jsonl", "topology_entities": "topology_entities.jsonl",
    "topology_relations": "topology_relations.jsonl", "geometry_entities": "geometry_entities.jsonl",
    "pmi_entities": "pmi_entities.jsonl", "pmi_associations": "pmi_associations.jsonl",
    "fta_sets": "fta_sets.jsonl", "fta_semantics": "fta_semantics.jsonl",
    "diagnostics": "diagnostics.jsonl", "coverage": "coverage.json",
    "capability_matrix": "capability_matrix.json", "topology_bodies": "native_topology_bodies.jsonl",
    "topology_cells": "native_topology_cells.jsonl", "topology_wires": "native_topology_wires.jsonl",
    "topology_coedges": "native_topology_coedges.jsonl", "mesh_face_map": "native_mesh_face_map.jsonl",
    "mesh_triangles": "native_mesh_triangles.jsonl", "feature_results": "native_feature_results.jsonl",
    "feature_result_cells": "native_feature_result_cells.jsonl",
    "feature_topology_links": "native_feature_topology_links.jsonl",
    "product_references": "product_references.jsonl", "product_occurrences": "product_occurrences.jsonl",
    "document_links": "document_links.jsonl", "product_instances": "product_instances.jsonl",
    "capabilities": "capabilities.json",
}


def available_native_assets(bundle: Path | None) -> dict[str, str]:
    """只发布实际存在的受控资产路径，不将本机路径写入 API 清单。"""
    if bundle is None:
        return {}
    return {key: f"native-caa/{name}" for key, name in NATIVE_ASSET_FILES.items()
            if (bundle / name).is_file()}


def _count_records(path: Path) -> int:
    """按有效 JSONL 行统计旧页面的树出现位置口径。"""
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as stream:
        return sum(bool(line.strip()) for line in stream)


async def publish_native_capture(repository: CadRepository, revision_id: UUID, bundle: Path) -> dict:
    """原子发布树、属性、原生证据及 complete 标记，失败保留上一数据库快照。"""
    assets = available_native_assets(bundle)
    if not assets:
        return {}
    reader = CaaNewBundleReader(bundle)
    native_manifest = reader.manifest
    has_tree = any((bundle / name).is_file() for name in
                   ("tree_occurrences.jsonl", "features.jsonl", "product_occurrences.jsonl"))
    has_properties = (bundle / "property_facts.jsonl").is_file()
    semantic_summary = reader.semantic_summary() if (bundle / "native_features.jsonl").is_file() else None
    streams = reader.native_evidence_streams()
    if not has_tree and not has_properties and not streams:
        return {}
    async with repository.native_publish_transaction():
        stored_count = None
        if has_tree:
            tree_payload = reader.build_tree(include_supplemental=True)
            rows = native_tree_rows(revision_id, tree_payload)
            expected_count = int(tree_payload.get("node_count") or len(rows))
            stored_count = await repository.replace_native_tree_entities(revision_id, rows, expected_count)
            if stored_count != expected_count:
                raise ValueError(f"native tree database count mismatch: expected={expected_count}, stored={stored_count}")
        property_count = None
        if has_properties:
            property_count = await repository.replace_native_property_facts(
                revision_id, iter_native_property_rows(revision_id, reader.iter_property_facts()),
            )
        # New native material, order or contour facts invalidate every derived
        # coverage result even when the final B-Rep hash remains stable.
        publish_streams = {**streams, **({"composite_coverage": []} if "composite_structure" in streams else {})}
        published_counts = await repository.replace_native_evidence(
            revision_id, publish_streams, replace_all=False,
        ) if publish_streams else {}
        evidence_counts = {kind: count for kind, count in published_counts.items() if kind != "composite_coverage"}
        result = {
            "native_semantics": {"available": True, **assets},
            "native_capture": {
                "available": True,
                "status": native_manifest.get("capture_status") or "ready",
                "schema_version": native_manifest.get("schema_version"),
                "parser_version": native_manifest.get("parser_version"),
                "document_kind": native_manifest.get("document_kind"),
                "selected_reconstruction_route": native_manifest.get("selected_reconstruction_route"),
                "exact_brep_body_count": native_manifest.get("exact_brep_body_count"),
                "incomplete_brep_body_count": native_manifest.get("incomplete_brep_body_count"),
                **({"has_tree": True} if has_tree else {}),
                **({"has_properties": True} if has_properties else {}),
                "has_topology": "topology_entities" in assets,
                "has_geometry": "geometry_entities" in assets,
                "has_mesh": "mesh_triangles" in assets,
                "capture_engine": "caa_new", "capture_platform": "intel_a", "capture_bitness": 32,
            },
            "viewer_summary": {
                **({"native_feature_count": _count_records(bundle / "features.jsonl")}
                   if (bundle / "features.jsonl").is_file() else {}),
                **({"native_semantic_status": "captured"} if semantic_summary is not None else {}),
                **({
                    "native_definition_count": semantic_summary["definition_count"],
                    "native_typed_count": semantic_summary["typed_count"],
                    "native_type_only_count": semantic_summary["type_only_count"],
                    "native_generic_count": semantic_summary["generic_count"],
                    "native_failed_count": semantic_summary["failed_count"],
                    "native_unavailable_count": semantic_summary["unavailable_count"],
                    "native_typed_by_decoder": semantic_summary["typed_by_decoder"],
                } if semantic_summary is not None else {}),
            },
        }
        if stored_count is not None:
            result["native_tree_storage"] = {"backend": "postgresql", "node_count": stored_count, "complete": True}
        if property_count is not None:
            result["native_property_storage"] = {"backend": "postgresql", "fact_count": property_count, "complete": True}
        if streams:
            result["native_evidence_storage"] = {"backend": "postgresql", "counts": evidence_counts, "complete": True}
        if "composite_structure" in streams:
            result["composite_coverage_storage"] = {"backend": "postgresql", "counts": {},
                                                     "complete": False, "status": "source_changed"}
        await repository.update_revision_manifest(revision_id, result)
    return result


FEATURE_EVIDENCE_FILES = {
    "canonical_features": "canonical_features.jsonl",
    "measurements": "measurements.jsonl",
    "topology_faces": "topology_faces.jsonl",
    "feature_geometry_links": "feature_geometry_links.jsonl",
}


def feature_evidence_streams(bundle: Path):
    """只暴露校验过的 Feature Center 记录，不给调用器扩散文件清单。"""
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    output_files = manifest.get("output_files") or {}
    streams = {}
    for kind, name in FEATURE_EVIDENCE_FILES.items():
        path = bundle / name
        if not path.is_file():
            if kind in {"canonical_features", "measurements", "feature_geometry_links"}:
                raise ValueError(f"required Feature Center evidence missing: {name}")
            continue
        expected = (output_files.get(name) or {}).get("sha256")
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Feature Center evidence hash mismatch: {name}")
        streams[kind] = _read_jsonl(path)
    selection = bundle / "lightweight" / "selection_index.json"
    if selection.is_file():
        expected = (output_files.get("lightweight/selection_index.json") or {}).get("sha256")
        if expected and hashlib.sha256(selection.read_bytes()).hexdigest() != expected:
            raise ValueError("Feature Center evidence hash mismatch: lightweight/selection_index.json")
        streams["selection_index"] = iter([json.loads(selection.read_text(encoding="utf-8"))])
    return streams


def _read_jsonl(path: Path):
    """流式读取 Feature Center JSONL，坏行使当前数据库事务整体回滚。"""
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{number}: expected object")
            yield value


async def publish_feature_evidence(
    repository: CadRepository, revision_id: UUID, bundle: Path, *, manifest_values: dict | None = None,
) -> dict[str, int]:
    """验证并幂等替换一笔 Revision 的 Feature Center 数据，不触碰原生证据。"""
    errors = validate_bundle(bundle)
    if errors:
        raise ValueError("Feature Center bundle invalid: " + "; ".join(errors))
    async with repository.native_publish_transaction():
        counts = await repository.replace_native_evidence(
            revision_id, feature_evidence_streams(bundle), replace_all=False,
        )
        await repository.update_revision_manifest(revision_id, {
            **(manifest_values or {}),
            "feature_evidence_storage": {"backend": "postgresql", "counts": counts, "complete": True},
        })
    return counts
