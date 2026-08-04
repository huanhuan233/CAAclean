"""复杂结构特征的 eAAG 就绪度探针，不生成生产识别结果。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import stable_id
from .eaag import EaagGraph


# 用途：统计 B-Rep/eAAG 当前可提供的证据，明确后续算法能否安全启动。
def build_readiness_probes(
    part_id: str,
    shape_hash: str,
    graph: EaagGraph,
) -> list[dict[str, Any]]:
    faces = [
        entity for entity in graph.entities.values()
        if entity.get("entity_type") == "face"
    ]
    surfaces = Counter(str(face.get("geometry_type", "other")) for face in faces)
    faces_with_curvature = sum(
        1 for face in faces
        if face.get("geometry", {}).get("curvature_sample") is not None
    )
    faces_with_wires = sum(1 for face in faces if graph.wire_ids(face["entity_id"]))
    adjacent_pairs = sum(len(graph.face_neighbors(face["entity_id"])) for face in faces) // 2

    definitions = [
        (
            "rib_web",
            "verifier_prerequisites_incomplete"
            if surfaces["plane"] >= 2 and adjacent_pairs else "insufficient_evidence",
            {
                "planar_face_count": surfaces["plane"],
                "adjacent_pair_count": adjacent_pairs,
                "relative_thickness_sampling_available": False,
                "attachment_graph_available": adjacent_pairs > 0,
            },
        ),
        (
            "cavity_island",
            "verifier_prerequisites_incomplete"
            if faces_with_wires and adjacent_pairs else "insufficient_evidence",
            {
                "face_with_wire_count": faces_with_wires,
                "adjacent_pair_count": adjacent_pairs,
                "edge_convexity_available": False,
                "external_reachability_available": False,
                "nested_loop_analysis_available": faces_with_wires > 0,
            },
        ),
        (
            "freeform_surface",
            "verifier_prerequisites_incomplete"
            if sum(surfaces[key] for key in ("bezier", "bspline", "offset")) > 0
            else "insufficient_evidence",
            {
                "bezier_face_count": surfaces["bezier"],
                "bspline_face_count": surfaces["bspline"],
                "offset_face_count": surfaces["offset"],
                "curvature_sample_face_count": faces_with_curvature,
                "continuity_analysis_available": False,
            },
        ),
    ]
    return [
        {
            "probe_id": stable_id("PROBE", shape_hash, family),
            "part_id": part_id,
            "family": family,
            "status": status,
            "evidence": evidence,
            "candidate_recognizer_enabled": False,
            "production_recognizer_enabled": False,
            "canonical_feature_created": False,
        }
        for family, status, evidence in definitions
    ]
