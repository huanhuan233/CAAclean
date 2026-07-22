from __future__ import annotations

from app.measurement.analytic_groups import build_analytic_measurements
from app.measurement.axis_detector import detect_main_axis
from app.measurement.circular_patterns import detect_circular_patterns
from app.measurement.envelope import build_envelope_measurements
from app.measurement.hole_detector import detect_hole_candidates
from app.measurement.plane_groups import build_parallel_plane_measurements
from app.measurement.schemas import EntityFact, MeasurementBuildResult, stable_uuid


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
