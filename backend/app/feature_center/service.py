"""Feature Center Sidecar 的阶段编排服务。"""

from __future__ import annotations

import time
from typing import Any

from .contracts import FEATURE_CENTER_ALGORITHM_VERSION, FeatureCenterBundle, stable_id
from .eaag import EaagGraph
from .fusion import fuse_native_holes
from .mesh import build_lightweight_mesh
from .readiness import build_readiness_probes
from .step_input import StepInputInfo
from .topology import build_stable_topology
from .visual_review import route_visual_review


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
    fusion = fuse_native_holes(
        part_id,
        EaagGraph(topology.entities, topology.relations),
        native_features or [],
        topology.tolerance_mm,
        topology.shape_hash,
    )
    fusion_ms = (time.perf_counter() - fusion_started) * 1000.0
    mesh_started = time.perf_counter()
    lightweight = build_lightweight_mesh(
        parser_result, topology, fusion.feature_geometry_links
    )
    mesh_ms = (time.perf_counter() - mesh_started) * 1000.0
    readiness_probes = build_readiness_probes(
        part_id, topology.shape_hash, EaagGraph(topology.entities, topology.relations)
    )
    review_requests = []
    for feature in fusion.canonical_features:
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
            "step_schema": step_info.step_schema,
        },
        algorithms={
            "stable_topology": FEATURE_CENTER_ALGORITHM_VERSION,
            "eaag": FEATURE_CENTER_ALGORITHM_VERSION,
            "lightweight_mesh": FEATURE_CENTER_ALGORITHM_VERSION,
        },
        parts=[part],
        topology_entities=topology.entities,
        topology_relations=topology.relations,
        observations=fusion.observations,
        canonical_features=fusion.canonical_features,
        feature_geometry_links=fusion.feature_geometry_links,
        measurements=fusion.measurements,
        diagnostics=fusion.diagnostics,
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
        feature_recognition_scope="native_hole_guided_only",
    )
