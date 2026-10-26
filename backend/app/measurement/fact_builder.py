# 组织批量候选识别和尺寸提取，先为成员候选分配稳定编号，再构建引用成员的阵列候选。
from __future__ import annotations

from app.measurement.analytic_groups import build_analytic_measurements
from app.measurement.axis_detector import detect_main_axis
from app.measurement.circular_patterns import detect_circular_patterns
from app.measurement.envelope import build_envelope_measurements
from app.measurement.hole_detector import detect_hole_candidates
from app.measurement.plane_groups import build_parallel_plane_measurements
from app.measurement.schemas import EntityFact, MeasurementBuildResult, stable_uuid


# 依次生成主轴、孔和阵列候选，再合并包络、解析参数与平面间距测量。
def build_measurement_facts(entities: list[EntityFact]) -> MeasurementBuildResult:
    features = []
    main_axis = detect_main_axis(entities)
    if main_axis:
        features.append(main_axis)
    features.extend(detect_hole_candidates(entities))
    _assign_feature_ids(features)
    features.extend(detect_circular_patterns(entities, features))
    _assign_feature_ids(features)

    measurements = []
    measurements.extend(build_envelope_measurements(entities, main_axis))
    measurements.extend(build_analytic_measurements(entities))
    measurements.extend(build_parallel_plane_measurements(entities))
    _assign_measurement_ids(measurements)
    return MeasurementBuildResult(features=features, measurements=measurements)


# 由候选类型、作用域、排序后的来源编号与参数生成当前修订内的稳定身份。
def _assign_feature_ids(features):
    for feature in features:
        feature.id = stable_uuid(
            feature.revision_id,
            feature.algorithm_version,
            "feature",
            {
                "type": feature.feature_type,
                "scope": str(feature.scope_entity_id),
                "sources": sorted(str(source_id) for source_id in feature.source_entity_ids),
                "parameters": feature.parameters,
            },
        )


# 将规范值与计算方法纳入尺寸身份，避免相同来源上不同测量方法互相覆盖。
def _assign_measurement_ids(measurements):
    for measurement in measurements:
        measurement.id = stable_uuid(
            measurement.revision_id,
            measurement.algorithm_version,
            "measurement",
            {
                "type": measurement.measurement_type,
                "scope": str(measurement.scope_entity_id),
                "sources": sorted(str(source_id) for source_id in measurement.source_entity_ids),
                "value": measurement.normalized_value,
                "method": measurement.method,
            },
        )
