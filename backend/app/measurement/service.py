from __future__ import annotations

import uuid

from app.measurement.fact_builder import build_measurement_facts
from app.measurement.repository import MeasurementRepository
from app.measurement.schemas import ALGORITHM_VERSION


class MeasurementService:
    def __init__(self, repository: MeasurementRepository, algorithm_version: str = ALGORITHM_VERSION):
        self.repository = repository
        self.algorithm_version = algorithm_version

    async def recompute_revision(self, revision_id: uuid.UUID) -> dict:
        entities = await self.repository.list_entity_facts(revision_id)
        facts = build_measurement_facts(entities)
        for feature in facts.features:
            feature.algorithm_version = self.algorithm_version
            feature.id = None
        for measurement in facts.measurements:
            measurement.algorithm_version = self.algorithm_version
            measurement.id = None
        await self.repository.replace_results(
            revision_id,
            facts.features,
            facts.measurements,
            algorithm_version=self.algorithm_version,
        )
        return {
            "revision_id": revision_id,
            "algorithm_version": self.algorithm_version,
            "feature_count": len(facts.features),
            "measurement_count": len(facts.measurements),
        }
