"""使用 Native Hole 参数和 eAAG 精确几何定位真实 B-Rep 面。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import product
from typing import Any

from .eaag import EaagGraph


@dataclass
class HoleFaceMatch:
    """保存一次 Hole 几何验证的面角色、残差、冲突和终态。"""

    native_feature_id: str
    status: str
    match_method: str = "native_hole_parameter_guided_eaag"
    match_score: float = 0.0
    body_wall_face_ids: list[str] = field(default_factory=list)
    head_wall_face_ids: list[str] = field(default_factory=list)
    transition_face_ids: list[str] = field(default_factory=list)
    bottom_face_ids: list[str] = field(default_factory=list)
    parameter_residuals: dict[str, float | None] = field(default_factory=dict)
    unmatched_expected_geometry: list[str] = field(default_factory=list)
    ambiguous_candidates: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    @property
    def matched_face_ids(self) -> list[str]:
        """返回去重后的全部面，角色列表本身仍保留用于 Viewer 和证据展示。"""
        return sorted(set(
            self.body_wall_face_ids + self.head_wall_face_ids +
            self.transition_face_ids + self.bottom_face_ids
        ))


# 用途：归一化三维方向；零向量和非有限值会被验证器明确拒绝。
def _normalized(vector: list[float]) -> list[float] | None:
    if len(vector) != 3 or not all(math.isfinite(float(value)) for value in vector):
        return None
    length = math.sqrt(sum(float(value) ** 2 for value in vector))
    if length <= 1.0e-12:
        return None
    return [float(value) / length for value in vector]


# 用途：计算两条平行轴线的径向距离，避免把 z 向采样偏移误认为原点残差。
def _axis_distance(origin: list[float], cylinder_center: list[float], axis: list[float]) -> float:
    delta = [cylinder_center[index] - origin[index] for index in range(3)]
    cross = [
        delta[1] * axis[2] - delta[2] * axis[1],
        delta[2] * axis[0] - delta[0] * axis[2],
        delta[0] * axis[1] - delta[1] * axis[0],
    ]
    return math.sqrt(sum(value * value for value in cross))


# 用途：把 Face 包围盒八角投影到孔轴，得到相对于设计原点的真实轴向覆盖区间。
def _axial_interval(face: dict[str, Any], origin: list[float], direction: list[float]) -> tuple[float, float]:
    box = face.get("bounding_box") or {}
    minimum = box.get("min", face.get("center", origin))
    maximum = box.get("max", face.get("center", origin))
    projections = []
    for choice in product((0, 1), repeat=3):
        point = [maximum[i] if choice[i] else minimum[i] for i in range(3)]
        projections.append(sum((float(point[i]) - origin[i]) * direction[i] for i in range(3)))
    return min(projections), max(projections)


class HoleGeometryVerifier:
    """只接受 NativeHoleDecoder 已确认对象，并用 B-Rep 参数残差决定面归属。"""

    # 用途：保存由模型尺度计算的统一毫米容差，禁止在算法中写死零件尺寸阈值。
    def __init__(self, tolerance_mm: float) -> None:
        self.tolerance_mm = max(float(tolerance_mm), 1.0e-9)

    # 用途：验证一个原生 Hole 并划分主体壁、头部壁、过渡面和底面角色。
    def verify(self, native_feature: dict[str, Any], graph: EaagGraph) -> HoleFaceMatch:
        feature_id = str(native_feature.get("feature_id", ""))
        result = HoleFaceMatch(native_feature_id=feature_id, status="rejected")
        if native_feature.get("decoder_id") != "NativeHoleDecoder" or not native_feature.get("native_hole"):
            result.diagnostics.append("NATIVE_HOLE_SEMANTIC_REQUIRED")
            return result
        hole = native_feature["native_hole"]
        origin = [float(value) for value in hole.get("origin_mm", [])]
        direction = _normalized(hole.get("direction", []))
        diameter = hole.get("diameter_mm")
        if len(origin) != 3 or direction is None or diameter is None or float(diameter) <= 0.0:
            result.status = "needs_review"
            result.diagnostics.append("NATIVE_HOLE_REQUIRED_PARAMETER_INVALID")
            return result

        body_radius = float(diameter) * 0.5
        bottom_limit = hole.get("bottom_limit", {})
        depth = bottom_limit.get("depth_mm")
        head = hole.get("head", {})
        head_depth = head.get("depth_mm") if head.get("kind") not in (None, "none") else None
        body_start = float(head_depth) if head_depth is not None else 0.0
        body_end = float(depth) if depth is not None else None
        body_faces, body_residuals = self._cylinder_faces(
            graph, origin, direction, body_radius, body_start, body_end
        )
        result.body_wall_face_ids = body_faces
        result.parameter_residuals.update(body_residuals)

        if head.get("kind") not in (None, "none") and head.get("diameter_mm") is not None:
            head_radius = float(head["diameter_mm"]) * 0.5
            result.head_wall_face_ids, _ = self._cylinder_faces(
                graph, origin, direction, head_radius, 0.0,
                float(head_depth) if head_depth is not None else None,
            )
            if not result.head_wall_face_ids:
                result.unmatched_expected_geometry.append("head_wall")

        if not body_faces:
            result.status = "needs_review"
            result.unmatched_expected_geometry.append("body_wall")
            result.diagnostics.append("HOLE_BODY_WALL_NOT_FOUND")
            return result

        if depth is not None:
            result.bottom_face_ids = self._planar_neighbors_at_depth(
                graph, body_faces, origin, direction, float(depth)
            )
            if not result.bottom_face_ids:
                result.unmatched_expected_geometry.append("bottom_face")
        else:
            result.parameter_residuals["depth_mm"] = None
            opening_context = {
                neighbor_id: graph.entities[neighbor_id]
                for wall_id in body_faces
                for neighbor_id in graph.face_neighbors(wall_id)
                if graph.entities.get(neighbor_id, {}).get("geometry_type") == "plane"
            }
            wall_intervals = [
                _axial_interval(graph.entities[wall_id], origin, direction)
                for wall_id in body_faces
            ]
            wall_min = min(interval[0] for interval in wall_intervals) if wall_intervals else None
            wall_max = max(interval[1] for interval in wall_intervals) if wall_intervals else None
            end_tolerance = max(self.tolerance_mm * 5.0, 1.0e-6)
            opening_projections = []
            minimum_opening_area = 3.141592653589793 * body_radius * body_radius * 1.05
            for plane in opening_context.values():
                center = plane.get("center")
                area = plane.get("area")
                if isinstance(center, list) and len(center) == 3 and isinstance(area, (int, float)) \
                        and float(area) >= minimum_opening_area:
                    opening_projections.append(sum(
                        (float(center[index]) - origin[index]) * direction[index]
                        for index in range(3)
                    ))
            has_two_axial_ends = (
                wall_min is not None and wall_max is not None
                and any(abs(value - wall_min) <= end_tolerance for value in opening_projections)
                and any(abs(value - wall_max) <= end_tolerance for value in opening_projections)
                and wall_max - wall_min > end_tolerance
            )
            if not has_two_axial_ends:
                result.unmatched_expected_geometry.append("through_opening_context")
                result.diagnostics.append("HOLE_UP_TO_LAST_OPENING_CONTEXT_INSUFFICIENT")

        if head_depth is not None:
            result.transition_face_ids = self._planar_neighbors_at_depth(
                graph, body_faces + result.head_wall_face_ids,
                origin, direction, float(head_depth),
            )

        required_complete = bool(body_faces) and (
            depth is None or bool(result.bottom_face_ids)
        ) and (not result.unmatched_expected_geometry)
        result.status = "verified" if required_complete else "needs_review"
        radius_residual = float(result.parameter_residuals.get("radius_mm") or 0.0)
        axis_residual = float(result.parameter_residuals.get("axis_alignment") or 0.0)
        origin_residual = float(result.parameter_residuals.get("axis_origin_mm") or 0.0)
        normalized_error = (
            radius_residual / self.tolerance_mm +
            origin_residual / self.tolerance_mm + axis_residual
        ) / 3.0
        result.match_score = max(0.0, min(1.0, 1.0 - normalized_error))
        return result

    # 用途：按半径、轴向、轴线位置和覆盖区间筛选全部接缝分片圆柱面。
    def _cylinder_faces(
        self,
        graph: EaagGraph,
        origin: list[float],
        direction: list[float],
        expected_radius: float,
        expected_start: float,
        expected_end: float | None,
    ) -> tuple[list[str], dict[str, float | None]]:
        matches: list[str] = []
        residual_rows: list[tuple[float, float, float, float | None]] = []
        for face in graph.faces_by_surface("cylinder"):
            geometry = face.get("geometry", {})
            axis = _normalized(geometry.get("axis", []))
            center = geometry.get("center")
            radius = geometry.get("radius")
            if axis is None or not isinstance(center, list) or len(center) != 3 or radius is None:
                continue
            radius_residual = abs(float(radius) - expected_radius)
            alignment_residual = 1.0 - abs(sum(axis[i] * direction[i] for i in range(3)))
            origin_residual = _axis_distance(origin, [float(value) for value in center], direction)
            axial_start, axial_end = _axial_interval(face, origin, direction)
            start_residual = abs(axial_start - expected_start)
            end_residual = abs(axial_end - expected_end) if expected_end is not None else None
            if radius_residual > self.tolerance_mm:
                continue
            if alignment_residual > 1.0e-6 or origin_residual > self.tolerance_mm:
                continue
            if start_residual > self.tolerance_mm:
                continue
            if end_residual is not None and end_residual > self.tolerance_mm:
                continue
            matches.append(face["entity_id"])
            residual_rows.append((radius_residual, alignment_residual, origin_residual, end_residual))
        matches.sort()
        return matches, {
            "radius_mm": max((row[0] for row in residual_rows), default=None),
            "axis_alignment": max((row[1] for row in residual_rows), default=None),
            "axis_origin_mm": max((row[2] for row in residual_rows), default=None),
            "depth_mm": max((row[3] for row in residual_rows if row[3] is not None), default=None),
        }

    # 用途：只在已匹配壁面的 eAAG 邻接面中寻找指定轴深处的平面，避免串到其他孔。
    def _planar_neighbors_at_depth(
        self,
        graph: EaagGraph,
        wall_face_ids: list[str],
        origin: list[float],
        direction: list[float],
        expected_depth: float,
    ) -> list[str]:
        candidates: set[str] = set()
        for wall_id in wall_face_ids:
            candidates.update(graph.face_neighbors(wall_id))
        matches: list[str] = []
        for face_id in candidates:
            face = graph.entities.get(face_id)
            if not face or face.get("geometry_type") != "plane":
                continue
            normal = _normalized(face.get("geometry", {}).get("normal", []))
            center = face.get("center")
            if normal is None or not isinstance(center, list) or len(center) != 3:
                continue
            alignment = abs(sum(normal[i] * direction[i] for i in range(3)))
            projection = sum((float(center[i]) - origin[i]) * direction[i] for i in range(3))
            if alignment >= 1.0 - 1.0e-6 and abs(projection - expected_depth) <= self.tolerance_mm:
                matches.append(face_id)
        return sorted(matches)
