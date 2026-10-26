# 按同作用域、同轴向和同半径分组，以中心角间隔筛选圆周阵列候选，不读取原生阵列历史。
from __future__ import annotations

import math
from collections import defaultdict

from app.measurement.axis_detector import normalize
from app.measurement.schemas import EntityFact, FeatureCandidateFact


# 优先从圆柱组提取阵列；只有圆柱未产生任何阵列时才退回圆曲线组。
def detect_circular_patterns(entities: list[EntityFact], member_features: list[FeatureCandidateFact]) -> list[FeatureCandidateFact]:
    cylinders = [entity for entity in entities if entity.geometry_type == "cylinder" and _circle_ready(entity)]
    circles = [entity for entity in entities if entity.geometry_type == "circle" and _circle_ready(entity)]
    return _detect_patterns(cylinders, member_features) or _detect_patterns(circles, member_features)


# 至少三个同组成员才评估角间隔，最大间隔偏差超过五度则丢弃；结果仍保持候选状态。
def _detect_patterns(circles: list[EntityFact], member_features: list[FeatureCandidateFact]) -> list[FeatureCandidateFact]:
    groups: dict[tuple, list[EntityFact]] = defaultdict(list)
    for circle in circles:
        axis = normalize([float(value) for value in circle.geometry["axis"]])
        radius = round(float(circle.geometry["radius"]), 6)
        scope_id = circle.parent_entity_id or circle.id
        if axis is None:
            continue
        groups[(scope_id, tuple(axis), radius)].append(circle)

    patterns: list[FeatureCandidateFact] = []
    for (scope_id, axis, radius), members in groups.items():
        if len(members) < 3:
            continue
        centers = [member.geometry["center"] for member in members]
        basis_u, basis_v = _plane_basis(list(axis))
        center = _fit_center(centers, basis_u, basis_v)
        radial_distances = [_distance_in_plane(point, center, basis_u, basis_v) for point in centers]
        pitch_radius = sum(radial_distances) / len(radial_distances)
        if pitch_radius <= 1e-9:
            continue
        angles = sorted(_angle_in_plane(point, center, basis_u, basis_v) for point in centers)
        spacings = [(angles[(index + 1) % len(angles)] - angles[index]) % 360.0 for index in range(len(angles))]
        expected = 360.0 / len(angles)
        residual = max(abs(spacing - expected) for spacing in spacings)
        # 当前筛选只限制角间隔残差，未检验各成员等半径分布或中心共面性。
        if residual > 5.0:
            continue
        member_feature_ids = [
            str(feature.id)
            for feature in member_features
            if set(feature.source_entity_ids).intersection(member.id for member in members)
        ]
        patterns.append(
            FeatureCandidateFact(
                revision_id=members[0].revision_id,
                scope_entity_id=scope_id,
                feature_type="circular_pattern",
                source_entity_ids=[member.id for member in members],
                parameters={
                    "count": len(members),
                    "member_diameter": round(radius * 2.0, 9),
                    "pitch_circle_diameter": round(pitch_radius * 2.0, 9),
                    "center": [round(value, 9) for value in center],
                    "axis": list(axis),
                    "angular_spacing": round(expected, 9),
                    "start_angle": round(angles[0], 9),
                    "fit_residual": round(residual, 9),
                    "member_feature_ids": member_feature_ids,
                    "source_entity_ids": [str(member.id) for member in members],
                },
                axis=list(axis),
                center=[round(value, 9) for value in center],
                confidence=max(0.3, 0.85 - residual / 10.0),
                algorithm="circular_patterns",
            )
        )
    return patterns


# 检查分组所需轴、中心和半径字段是否存在，后续数值转换由检测流程承担。
def _circle_ready(entity: EntityFact) -> bool:
    return isinstance(entity.geometry.get("axis"), list) and isinstance(entity.geometry.get("center"), list) and entity.geometry.get("radius") is not None


# 选择不接近平行的参考轴，用两次叉积构造垂直于阵列轴的二维投影基。
def _plane_basis(axis: list[float]) -> tuple[list[float], list[float]]:
    reference = [1.0, 0.0, 0.0] if abs(axis[0]) < 0.9 else [0.0, 1.0, 0.0]
    basis_u = _normalize(_cross(axis, reference))
    basis_v = _normalize(_cross(axis, basis_u))
    return basis_u, basis_v


# 使用成员中心的算术均值估计阵列中心；当前未进行最小二乘圆拟合，基向量参数未参与计算。
def _fit_center(points: list[list[float]], basis_u: list[float], basis_v: list[float]) -> list[float]:
    mean = [sum(float(point[index]) for point in points) / len(points) for index in range(3)]
    return [round(value, 9) for value in mean]


# 将中心相对位移投影到平面基后计算径向距离，忽略轴向分量。
def _distance_in_plane(point: list[float], center: list[float], basis_u: list[float], basis_v: list[float]) -> float:
    relative = [float(point[index]) - float(center[index]) for index in range(3)]
    u = sum(relative[index] * basis_u[index] for index in range(3))
    v = sum(relative[index] * basis_v[index] for index in range(3))
    return math.sqrt(u * u + v * v)


# 用平面投影的 atan2 得到零至三百六十度范围的极角。
def _angle_in_plane(point: list[float], center: list[float], basis_u: list[float], basis_v: list[float]) -> float:
    relative = [float(point[index]) - float(center[index]) for index in range(3)]
    u = sum(relative[index] * basis_u[index] for index in range(3))
    v = sum(relative[index] * basis_v[index] for index in range(3))
    return math.degrees(math.atan2(v, u)) % 360.0


# 计算三维叉积，用于构造阵列平面的正交方向。
def _cross(left: list[float], right: list[float]) -> list[float]:
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


# 将构造出的基向量缩放为单位向量，调用方通过参考轴选择避免零长度。
def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(component * component for component in vector))
    return [component / length for component in vector]
