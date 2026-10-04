"""Feature Center Sidecar 的阶段编排服务。"""

from __future__ import annotations

import time
from typing import Any

from .contracts import FEATURE_CENTER_ALGORITHM_VERSION, FeatureCenterBundle, stable_id
from .eaag import EaagGraph
from .fusion import fuse_native_holes
from .geometry_recognition import RULE_VERSION, recognize_geometry
from .mesh import build_lightweight_mesh
from .readiness import build_readiness_probes
from .step_input import StepInputInfo
from .topology import build_stable_topology
from .visual_review import route_visual_review


def _associate_verified_geometry(fusion, recognition) -> None:
    """Join only exact same wall geometry; keep each source observation intact."""
    retained = []
    for geometric in recognition.canonical_features:
        if geometric.family != "hole" or geometric.review_state != "auto_verified":
            retained.append(geometric)
            continue
        wall_ids = set(geometric.typed_payload.get("geometry_recognition", {}).get("wall_face_ids", []))
        matches = [native for native in fusion.canonical_features
                   if native.family == "hole"
                   and native.typed_payload.get("geometry_verification", {}).get("status") == "verified"
                   and native.provenance.get("native_update_status") != "not_up_to_date"
                   and wall_ids
                   and wall_ids == set(native.typed_payload["geometry_verification"].get("body_wall_face_ids", []))]
        if len(matches) != 1:
            retained.append(geometric)
            continue
        native = matches[0]
        native.source_observation_ids.extend(geometric.source_observation_ids)
        native.typed_payload["geometry_recognition"] = geometric.typed_payload["geometry_recognition"]
        native.provenance["geometry_association"] = "exact_verified_wall_face_set"
        native.relations.append({"kind": "HAS_GEOMETRY_RECOGNITION", "target_id": geometric.source_observation_ids[0]})
        for measure in recognition.measurements:
            if measure.feature_center_id == geometric.feature_center_id:
                measure.feature_center_id = native.feature_center_id
                measure.measurement_id = stable_id("MEAS", native.feature_center_id, measure.name, "geometry_recognition")
        for link in recognition.feature_geometry_links:
            if link["feature_center_id"] == geometric.feature_center_id:
                link["feature_center_id"] = native.feature_center_id
                link["link_id"] = stable_id("FGL", native.feature_center_id, link["face_id"], link["role"], "geometry_recognition")
    recognition.canonical_features = retained


# 用途：把已验证 STEP 元数据和 FreeCAD 解析结果组装为不含伪特征的确定性 Bundle。
def build_bundle_from_parser_result(
    step_info: StepInputInfo,
    parser_result: dict[str, Any],
    native_features: list[dict[str, Any]] | None = None,
) -> FeatureCenterBundle:
    if parser_result.get("unit") != "mm":
        raise ValueError("BREP_KERNEL_UNIT_MISMATCH：FreeCAD 结果单位不是毫米")
    topology_started = time.perf_counter()
    topology = build_stable_topology(parser_result)
    topology_ms = (time.perf_counter() - topology_started) * 1000.0
    part_id = stable_id("PART", topology.shape_hash)
    part = {
        "part_id": part_id,
        "name": step_info.file_name.rsplit(".", 1)[0],
        "shape_hash": topology.shape_hash,
        "unit": "mm",
        "bounding_box": parser_result.get("bounding_box"),
        "tolerance_mm": topology.tolerance_mm,
    }
    fusion_started = time.perf_counter()
    graph = EaagGraph(topology.entities, topology.relations)
    fusion = fuse_native_holes(
        part_id,
        graph,
        native_features or [],
        topology.tolerance_mm,
        topology.shape_hash,
    )
    recognition = recognize_geometry(part_id, graph, topology.tolerance_mm, topology.shape_hash)
    _associate_verified_geometry(fusion, recognition)
    fusion_ms = (time.perf_counter() - fusion_started) * 1000.0
    all_links = fusion.feature_geometry_links + recognition.feature_geometry_links
    mesh_started = time.perf_counter()
    lightweight = build_lightweight_mesh(
        parser_result, topology, all_links
    )
    mesh_ms = (time.perf_counter() - mesh_started) * 1000.0
    readiness_probes = build_readiness_probes(
        part_id, topology.shape_hash, EaagGraph(topology.entities, topology.relations)
    )
    review_requests = []
    for feature in fusion.canonical_features + recognition.canonical_features:
        verification = feature.typed_payload.get("geometry_verification", {})
        decision = route_visual_review(
            topology.shape_hash,
            feature.feature_center_id,
            str(verification.get("status", "ambiguous")),
            feature.geometry_refs.face_ids,
            feature.provenance.get("native_update_status") == "not_up_to_date",
        )
        review_requests.append({
            "review_request_id": decision.review_request_id,
            "feature_center_id": feature.feature_center_id,
            "decision": decision.decision,
            "reason": decision.reason,
            "cache_key": decision.cache_key,
            "visual_call_count": decision.visual_call_count,
        })
    return FeatureCenterBundle(
        input_file_name=step_info.file_name,
        input_sha256=step_info.sha256,
        step_sha256=step_info.sha256,
        shape_hash=topology.shape_hash,
        unit="mm",
        coordinate_system={
            "source_unit": step_info.source_unit,
            "kernel_unit": step_info.kernel_unit,
            "source_to_kernel_scale": step_info.source_to_kernel_scale,
            "source_to_kernel_transform": step_info.source_to_kernel_transform,
        },
        runtime={
            "brep_parser": parser_result.get("parser_name", "FreeCAD"),
            "brep_parser_version": parser_result.get("parser_version", "unknown"),
            "brep_kernel": parser_result.get("kernel_name", "OpenCascade"),
            "brep_kernel_version": parser_result.get("kernel_version", "unknown"),
            "mesh_deflection_mm": parser_result.get("mesh_deflection", 0.1),
            "step_schema": step_info.step_schema,
        },
        algorithms={
            "stable_topology": FEATURE_CENTER_ALGORITHM_VERSION,
            "eaag": FEATURE_CENTER_ALGORITHM_VERSION,
            "lightweight_mesh": FEATURE_CENTER_ALGORITHM_VERSION,
            "geometry_recognition": RULE_VERSION,
        },
        parts=[part],
        topology_entities=topology.entities,
        topology_relations=topology.relations,
        observations=fusion.observations + recognition.observations,
        canonical_features=fusion.canonical_features + recognition.canonical_features,
        feature_geometry_links=all_links,
        measurements=fusion.measurements + recognition.measurements,
        diagnostics=fusion.diagnostics + recognition.diagnostics,
        readiness_probes=readiness_probes,
        review_requests=review_requests,
        performance={
            "topology_build_ms": round(topology_ms, 3),
            "geometry_verification_and_fusion_ms": round(fusion_ms, 3),
            "mesh_build_ms": round(mesh_ms, 3),
            "topology_entity_count": len(topology.entities),
            "topology_relation_count": len(topology.relations),
            "mesh_primitive_count": lightweight.primitive_count,
            "mesh_triangle_count": lightweight.triangle_count,
            "freecad_step_import_count": parser_result.get("parse_manifest", {}).get("step_import_count", "unknown"),
            "cylinder_evaluation_count": parser_result.get("parse_manifest", {}).get("cylinder_evaluation_count", "unknown"),
            "recognition_stats": {
                "native_definition_count": len(native_features or []),
                "native_typed_decoder_count": sum(1 for item in (native_features or [])
                                                   if item.get("decode_level") == "typed"),
                "geometry_observation_count": len(recognition.observations),
                "independent_geometry_feature_count": len(recognition.canonical_features),
                "associated_geometry_count": sum(1 for item in fusion.canonical_features
                                                 if item.provenance.get("geometry_association")),
                "candidate_count": sum(1 for item in fusion.canonical_features + recognition.canonical_features
                                       if item.review_state != "auto_verified"),
                "confirmed_localization_count": sum(1 for item in fusion.canonical_features + recognition.canonical_features
                                                    if item.review_state == "auto_verified" and item.geometry_refs.face_ids),
            },
        },
        lightweight={
            "model_glb": lightweight.model_glb,
            "face_mesh_map": lightweight.face_mesh_map,
            "feature_mesh_map": lightweight.feature_mesh_map,
            "selection_index": lightweight.selection_index,
            "primitive_count": lightweight.primitive_count,
            "vertex_count": lightweight.vertex_count,
            "triangle_count": lightweight.triangle_count,
        },
        vision_enabled=False,
        degraded=False,
        feature_recognition_scope="native_hole_guided;geometry_holes_straight_fillet_chamfer",
    )
