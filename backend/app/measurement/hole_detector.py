from __future__ import annotations

from app.measurement.schemas import EntityFact, FeatureCandidateFact


def detect_hole_candidates(entities: list[EntityFact]) -> list[FeatureCandidateFact]:
    features: list[FeatureCandidateFact] = []
    for entity in entities:
        if entity.geometry_type not in {"cylinder", "circle"}:
            continue
        radius = entity.geometry.get("radius")
        axis = entity.geometry.get("axis")
        center = entity.geometry.get("center") or entity.center
        if radius is None or not isinstance(axis, list):
            continue
        base_parameters = {"diameter": round(float(radius) * 2.0, 9)}
        features.append(
            FeatureCandidateFact(
                revision_id=entity.revision_id,
                scope_entity_id=entity.parent_entity_id or entity.id,
                feature_type="cylindrical_hole_candidate",
                source_entity_ids=[entity.id],
                parameters=base_parameters,
                axis=axis,
                center=center,
                confidence=0.55,
                algorithm="hole_detector",
            )
        )
        if entity.geometry_type == "cylinder":
            hole_kind = "through_hole_candidate" if _touches_two_bbox_sides(entity) else "blind_hole_candidate"
            features.append(
                FeatureCandidateFact(
                    revision_id=entity.revision_id,
                    scope_entity_id=entity.parent_entity_id or entity.id,
                    feature_type=hole_kind,
                    source_entity_ids=[entity.id],
                    parameters=base_parameters,
                    axis=axis,
                    center=center,
                    confidence=0.4,
                    algorithm="hole_detector",
                )
            )
    return features


def _touches_two_bbox_sides(entity: EntityFact) -> bool:
    bbox = entity.bounding_box
    if not bbox:
        return False
    spans = [abs(float(bbox["max"][index]) - float(bbox["min"][index])) for index in range(3)]
    return max(spans) > 0 and sorted(spans)[-1] > max(1e-9, sorted(spans)[0]) * 2
