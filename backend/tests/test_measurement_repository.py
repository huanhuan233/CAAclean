from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.measurement.repository import MeasurementRepository
from app.measurement.service import MeasurementService
from app.measurement.schemas import FeatureCandidateFact, MeasurementFact


class MemorySession:
    def __init__(self):
        self.features = []
        self.measurements = []
        self.deleted_versions = []

    def begin(self):
        class Tx:
            async def __aenter__(tx_self):
                return self

            async def __aexit__(tx_self, exc_type, exc, tb):
                return False

        return Tx()

    async def execute(self, statement):
        self.deleted_versions.append(str(statement))
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    def add_all(self, rows):
        for row in rows:
            if row.__class__.__name__ == "CadFeatureCandidate":
                self.features.append(row)
            if row.__class__.__name__ == "CadMeasurement":
                self.measurements.append(row)


def make_facts(revision_id, algorithm_version):
    scope_id = uuid4()
    entity_id = uuid4()
    feature = FeatureCandidateFact(
        revision_id=revision_id,
        scope_entity_id=scope_id,
        feature_type="main_axis_candidate",
        source_entity_ids=[entity_id],
        parameters={"axis_origin": [0, 0, 0]},
        axis=[0, 0, 1],
        center=[0, 0, 0],
        confidence=0.8,
        algorithm="axis_detector",
        algorithm_version=algorithm_version,
        status="candidate",
        metadata={},
    )
    measurement = MeasurementFact(
        revision_id=revision_id,
        scope_entity_id=scope_id,
        feature_id=None,
        measurement_type="overall_length_along_main_axis",
        raw_value={"value": 20},
        normalized_value={"value": 20},
        unit="mm",
        source_entity_ids=[entity_id],
        method="projection",
        confidence=0.8,
        algorithm_version=algorithm_version,
        metadata={},
    )
    return [feature], [measurement]


@pytest.mark.asyncio
async def test_repository_uses_stable_ids_and_recomputes_only_matching_algorithm_version():
    revision_id = uuid4()
    session = MemorySession()
    repo = MeasurementRepository(session)
    features, measurements = make_facts(revision_id, "phase2.v1")

    await repo.replace_results(revision_id, features, measurements, algorithm_version="phase2.v1")
    await repo.replace_results(revision_id, features, measurements, algorithm_version="phase2.v1")
    next_features, next_measurements = make_facts(revision_id, "phase2.v2")
    await repo.replace_results(revision_id, next_features, next_measurements, algorithm_version="phase2.v2")

    assert session.features[0].id == session.features[1].id
    assert session.measurements[0].id == session.measurements[1].id
    assert session.features[2].algorithm_version == "phase2.v2"
    assert session.features[2].id != session.features[0].id


@pytest.mark.asyncio
async def test_service_explicit_recompute_records_requested_algorithm_version_with_matching_ids():
    revision_id = uuid4()
    session = MemorySession()
    repo = MeasurementRepository(session)

    async def list_entity_facts(_revision_id):
        return []

    repo.list_entity_facts = list_entity_facts
    await MeasurementService(repo, algorithm_version="phase2.v2").recompute_revision(revision_id)

    assert session.features == []
    assert session.measurements == []
    assert session.deleted_versions
