from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadEntity, CadFeatureCandidate, CadMeasurement
from app.measurement.schemas import EntityFact, FeatureCandidateFact, MeasurementFact, stable_uuid


class MeasurementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_entity_facts(self, revision_id: uuid.UUID) -> list[EntityFact]:
        result = await self.session.execute(select(CadEntity).where(CadEntity.revision_id == revision_id).order_by(CadEntity.tree_path))
        return [
            EntityFact(
                id=entity.id,
                revision_id=entity.revision_id,
                parent_entity_id=entity.parent_entity_id,
                entity_type=entity.entity_type,
                geometry_type=entity.geometry_type,
                geometry=entity.geometry or {},
                center=entity.center if isinstance(entity.center, list) else None,
                bounding_box=entity.bounding_box,
                area=entity.area,
                length=entity.length,
                source_ref=entity.source_ref,
            )
            for entity in result.scalars().all()
        ]

    async def replace_results(
        self,
        revision_id: uuid.UUID,
        features: list[FeatureCandidateFact],
        measurements: list[MeasurementFact],
        *,
        algorithm_version: str,
    ) -> None:
        async with self.session.begin():
            await self.session.execute(
                delete(CadMeasurement).where(
                    CadMeasurement.revision_id == revision_id,
                    CadMeasurement.algorithm_version == algorithm_version,
                )
            )
            await self.session.execute(
                delete(CadFeatureCandidate).where(
                    CadFeatureCandidate.revision_id == revision_id,
                    CadFeatureCandidate.algorithm_version == algorithm_version,
                )
            )
            self.session.add_all([self._feature_row(feature) for feature in features])
            self.session.add_all([self._measurement_row(measurement) for measurement in measurements])

    def _feature_row(self, feature: FeatureCandidateFact) -> CadFeatureCandidate:
        feature_id = feature.id or stable_uuid(
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
        return CadFeatureCandidate(
            id=feature_id,
            revision_id=feature.revision_id,
            scope_entity_id=feature.scope_entity_id,
            feature_type=feature.feature_type,
            source_entity_ids=[str(entity_id) for entity_id in feature.source_entity_ids],
            parameters=feature.parameters,
            axis=feature.axis,
            center=feature.center,
            confidence=feature.confidence,
            algorithm=feature.algorithm,
            algorithm_version=feature.algorithm_version,
            status=feature.status,
            metadata_json=feature.metadata,
        )

    def _measurement_row(self, measurement: MeasurementFact) -> CadMeasurement:
        measurement_id = measurement.id or stable_uuid(
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
        return CadMeasurement(
            id=measurement_id,
            revision_id=measurement.revision_id,
            scope_entity_id=measurement.scope_entity_id,
            feature_id=measurement.feature_id,
            measurement_type=measurement.measurement_type,
            raw_value=measurement.raw_value,
            normalized_value=measurement.normalized_value,
            unit=measurement.unit,
            source_entity_ids=[str(entity_id) for entity_id in measurement.source_entity_ids],
            method=measurement.method,
            confidence=measurement.confidence,
            algorithm_version=measurement.algorithm_version,
            metadata_json=measurement.metadata,
        )
