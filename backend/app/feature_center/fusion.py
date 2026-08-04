"""Native CAA 与 B-Rep Hole Observation 的确定性融合。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import CanonicalFeature, GeometryRefs, Measurement, Observation, stable_id
from .eaag import EaagGraph
from .hole_mapping import HoleFaceMatch, HoleGeometryVerifier


@dataclass
class HoleFusionResult:
    """保存 Hole 融合新增的各类独立记录，不混入原始 CAA 对象守恒。"""

    observations: list[Observation] = field(default_factory=list)
    canonical_features: list[CanonicalFeature] = field(default_factory=list)
    feature_geometry_links: list[dict[str, Any]] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


# 用途：读取全部 JSONL 记录；空行忽略，语法错误由调用方作为 Bundle 级失败处理。
def read_jsonl(path) -> list[dict[str, Any]]:
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# 用途：从已验证圆柱壁直接计算 B-Rep 直径，不复用 CAA 参数作为权威测量。
def _brep_diameter(graph: EaagGraph, match: HoleFaceMatch) -> float | None:
    radii = [
        float(graph.entities[face_id].get("geometry", {}).get("radius"))
        for face_id in match.body_wall_face_ids
        if graph.entities.get(face_id, {}).get("geometry", {}).get("radius") is not None
    ]
    return (sum(radii) / len(radii)) * 2.0 if radii else None


# 用途：盲孔深度由 B-Rep 底面中心沿原生轴投影计算；贯穿孔不输出伪深度。
def _brep_blind_depth(
    graph: EaagGraph, match: HoleFaceMatch, native_hole: dict[str, Any]
) -> float | None:
    if native_hole.get("bottom_limit", {}).get("mode") != "offset" or not match.bottom_face_ids:
        return None
    origin = [float(value) for value in native_hole["origin_mm"]]
    direction = [float(value) for value in native_hole["direction"]]
    values = []
    for face_id in match.bottom_face_ids:
        center = graph.entities.get(face_id, {}).get("center")
        if isinstance(center, list) and len(center) == 3:
            values.append(sum((float(center[i]) - origin[i]) * direction[i] for i in range(3)))
    return sum(values) / len(values) if values else None


# 用途：为每个面写出显式角色链接，Viewer 不需要通过材质颜色反猜特征归属。
def _geometry_links(feature_center_id: str, match: HoleFaceMatch) -> list[dict[str, Any]]:
    roles = {
        "body_wall": match.body_wall_face_ids,
        "head_wall": match.head_wall_face_ids,
        "transition": match.transition_face_ids,
        "bottom": match.bottom_face_ids,
    }
    links = []
    for role, face_ids in roles.items():
        for face_id in face_ids:
            links.append({
                "link_id": stable_id("FGL", feature_center_id, face_id, role),
                "feature_center_id": feature_center_id,
                "face_id": face_id,
                "role": role,
                "source": "brep_deterministic",
            })
    return sorted(links, key=lambda item: item["link_id"])


# 用途：只融合 NativeHoleDecoder 的事实；Pocket、GSMTool 和普通圆柱几何均不会进入本链路。
def fuse_native_holes(
    part_id: str,
    graph: EaagGraph,
    native_features: list[dict[str, Any]],
    tolerance_mm: float,
    shape_hash: str,
) -> HoleFusionResult:
    result = HoleFusionResult()
    verifier = HoleGeometryVerifier(tolerance_mm)
    for feature in native_features:
        if feature.get("decoder_id") != "NativeHoleDecoder" or not feature.get("native_hole"):
            continue
        native_id = str(feature["feature_id"])
        native_hole = feature["native_hole"]
        match = verifier.verify(feature, graph)
        native_observation_id = stable_id("OBS", shape_hash, native_id, "native_caa")
        brep_observation_id = stable_id("OBS", shape_hash, native_id, "brep_deterministic")
        native_observation = Observation(
            observation_id=native_observation_id,
            part_id=part_id,
            source_kind="native_caa",
            source_id="NativeHoleDecoder",
            source_version="1.0.0",
            proposed_family="hole",
            proposed_subtype=str(native_hole.get("hole_type", "unknown")),
            classification_confidence=1.0,
            localization_confidence=0.0,
            measurement_confidence=0.0,
            status="verified",
            evidence_refs=[native_id],
        )
        brep_observation = Observation(
            observation_id=brep_observation_id,
            part_id=part_id,
            source_kind="brep_deterministic",
            source_id="HoleGeometryVerifier",
            source_version="1.0.0",
            proposed_family="hole",
            proposed_subtype=str(native_hole.get("hole_type", "unknown")),
            geometry_refs=GeometryRefs(face_ids=match.matched_face_ids),
            classification_confidence=1.0,
            localization_confidence=match.match_score,
            measurement_confidence=1.0 if match.status == "verified" else 0.5,
            status=match.status,
            diagnostics=list(match.diagnostics),
        )
        result.observations.extend([native_observation, brep_observation])

        feature_center_id = stable_id("FC", shape_hash, native_id, "part_design_hole")
        stale = feature.get("update_status") == "not_up_to_date"
        canonical = CanonicalFeature(
            feature_center_id=feature_center_id,
            part_id=part_id,
            family="hole",
            subtype=str(native_hole.get("hole_type", "unknown")),
            source_observation_ids=[native_observation_id, brep_observation_id],
            native_feature_ids=[native_id],
            geometry_refs=GeometryRefs(face_ids=match.matched_face_ids),
            typed_payload={
                "native_hole": native_hole,
                "geometry_verification": {
                    "status": match.status,
                    "match_method": match.match_method,
                    "match_score": match.match_score,
                    "parameter_residuals": match.parameter_residuals,
                    "body_wall_face_ids": match.body_wall_face_ids,
                    "head_wall_face_ids": match.head_wall_face_ids,
                    "transition_face_ids": match.transition_face_ids,
                    "bottom_face_ids": match.bottom_face_ids,
                    "unmatched_expected_geometry": match.unmatched_expected_geometry,
                },
            },
            relations=[
                {"kind": "DERIVED_FROM_NATIVE_FEATURE", "target_id": native_id},
                *({"kind": "HAS_FACE", "target_id": face_id} for face_id in match.matched_face_ids),
            ],
            review_state="auto_verified" if match.status == "verified" and not stale else "needs_review",
            provenance={
                "native_update_status": feature.get("update_status", "unknown"),
                "design_geometry_agreement": "stale_requires_review" if stale else match.status,
                "geometry_source": "exported_step_geometry",
            },
            diagnostics=list(match.diagnostics),
        )
        result.canonical_features.append(canonical)
        result.feature_geometry_links.extend(_geometry_links(feature_center_id, match))

        diameter = _brep_diameter(graph, match)
        if diameter is not None:
            result.measurements.append(Measurement(
                measurement_id=stable_id("MEAS", feature_center_id, "diameter"),
                feature_center_id=feature_center_id,
                name="diameter",
                value=diameter,
                unit="mm",
                tolerance=tolerance_mm,
                source="brep_deterministic",
                method="cylinder_radius_twice",
                algorithm_version="1.0.0",
                input_face_ids=match.body_wall_face_ids,
                validity="valid" if match.status == "verified" else "needs_review",
            ))
        depth = _brep_blind_depth(graph, match, native_hole)
        if depth is not None:
            result.measurements.append(Measurement(
                measurement_id=stable_id("MEAS", feature_center_id, "depth"),
                feature_center_id=feature_center_id,
                name="depth",
                value=depth,
                unit="mm",
                tolerance=tolerance_mm,
                source="brep_deterministic",
                method="axis_projection_to_verified_bottom_face",
                algorithm_version="1.0.0",
                input_face_ids=match.bottom_face_ids,
                validity="valid" if match.status == "verified" else "needs_review",
            ))
    result.observations.sort(key=lambda item: item.observation_id)
    result.canonical_features.sort(key=lambda item: item.feature_center_id)
    result.feature_geometry_links.sort(key=lambda item: item["link_id"])
    result.measurements.sort(key=lambda item: item.measurement_id)
    return result
