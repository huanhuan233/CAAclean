"""Deterministic viewer selection index construction.

This module only indexes IDs that are already present in Feature Center output.
It does not infer CATIA history, native feature authorship, or cross-session
identity from names, colors, mesh order, or runtime object identity.
"""

from __future__ import annotations

from typing import Any


SELECTION_INDEX_SCHEMA_VERSION = "cad_viewer_selection_v1"


def build_selection_index(
    *,
    shape_hash: str,
    face_mesh_map: dict[str, Any],
    feature_mesh_map: dict[str, Any],
    topology_entities: list[dict[str, Any]] | None = None,
    topology_relations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    primitive_to_face = {
        str(primitive_id): str(face_id)
        for primitive_id, face_id in (face_mesh_map.get("primitive_to_face") or {}).items()
        if primitive_id and face_id
    }
    render_face_to_primitives: dict[str, list[str]] = {}
    for primitive_id, face_id in primitive_to_face.items():
        render_face_to_primitives.setdefault(face_id, []).append(primitive_id)
    for values in render_face_to_primitives.values():
        values.sort()

    recognized_feature_to_faces: dict[str, list[str]] = {}
    recognized_feature_to_primitives: dict[str, list[str]] = {}
    render_face_to_recognized_features: dict[str, list[str]] = {}
    for feature_id, entry in sorted((feature_mesh_map.get("features") or {}).items()):
        face_ids = sorted({str(face_id) for face_id in entry.get("face_ids", []) if face_id})
        primitive_ids = sorted({str(pid) for pid in entry.get("mesh_primitive_ids", []) if pid})
        recognized_feature_to_faces[str(feature_id)] = face_ids
        recognized_feature_to_primitives[str(feature_id)] = primitive_ids
        for face_id in face_ids:
            render_face_to_recognized_features.setdefault(face_id, []).append(str(feature_id))
    for values in render_face_to_recognized_features.values():
        values.sort()

    topology = _index_topology(topology_entities or [], topology_relations or [])
    exact_count = len(primitive_to_face)
    crosswalk = [
        {
            "source_face_id": face_id,
            "target_face_id": face_id,
            "mapping_status": "exact",
            "mapping_method": "feature_center_one_face_one_primitive",
            "authority": "feature_center_mesh_generation",
            "confidence": 1.0,
            "candidate_count": 1,
            "diagnostics": [],
        }
        for face_id in sorted(render_face_to_primitives)
    ]

    return {
        "schema_version": SELECTION_INDEX_SCHEMA_VERSION,
        "shape_hash": shape_hash,
        "mapping_summary": {
            "exact": exact_count,
            "runtime_current_revision": 0,
            "candidate": 0,
            "ambiguous": 0,
            "unavailable": 0,
        },
        "primitive_to_render_face": primitive_to_face,
        "render_face_to_primitives": render_face_to_primitives,
        "primitive_to_context": {
            primitive_id: {"render_face_id": face_id, "mapping_status": "exact"}
            for primitive_id, face_id in sorted(primitive_to_face.items())
        },
        "render_face_to_recognized_features": render_face_to_recognized_features,
        "recognized_feature_to_render_faces": recognized_feature_to_faces,
        "recognized_feature_to_primitives": recognized_feature_to_primitives,
        "native_feature_to_native_faces": {},
        "native_face_to_body": {},
        "render_face_crosswalk": crosswalk,
        "topology": topology,
        "bom_node_to_descendant_primitives": {},
    }


def _index_topology(
    topology_entities: list[dict[str, Any]],
    topology_relations: list[dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {
        "bodies": {},
        "solids": {},
        "faces": {},
        "loops": {},
        "wires": {},
        "coedges": {},
        "edges": {},
        "vertices": {},
    }
    aliases = {
        "body": "bodies",
        "solid": "solids",
        "lump": "solids",
        "face": "faces",
        "loop": "loops",
        "wire": "wires",
        "coedge": "coedges",
        "oriented_edge": "coedges",
        "edge": "edges",
        "vertex": "vertices",
    }
    for entity in topology_entities:
        entity_id = str(entity.get("entity_id") or entity.get("id") or "")
        if not entity_id:
            continue
        kind = str(entity.get("topology_type") or entity.get("entity_type") or entity.get("type") or "").lower()
        group = aliases.get(kind)
        if not group:
            continue
        groups[group][entity_id] = {
            "id": entity_id,
            "parent_id": str(entity.get("parent_id") or entity.get("parent_entity_id") or ""),
            "owning_body_id": str(entity.get("owning_body_id") or entity.get("body_id") or ""),
            "orientation": entity.get("orientation"),
            "raw": entity,
            "relations": [],
        }

    known_ids = {item_id for entries in groups.values() for item_id in entries}
    for relation in topology_relations:
        source_id = str(relation.get("source_entity_id") or relation.get("source_id") or "")
        target_id = str(relation.get("target_entity_id") or relation.get("target_id") or "")
        if source_id not in known_ids and target_id not in known_ids:
            continue
        relation_record = {
            "relation_id": str(relation.get("relation_id") or ""),
            "relation_type": str(relation.get("relation_type") or relation.get("type") or ""),
            "source_id": source_id,
            "target_id": target_id,
        }
        for entries in groups.values():
            if source_id in entries:
                entries[source_id]["relations"].append(relation_record)
            if target_id in entries and target_id != source_id:
                entries[target_id]["relations"].append(relation_record)

    return groups
