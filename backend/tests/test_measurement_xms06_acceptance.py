import shutil
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.cad.parser_runner import run_freecad_parser
from app.core.config import Settings
from app.db.models import CadFeatureCandidate, CadMeasurement
from app.measurement.fact_builder import build_measurement_facts
from app.measurement.repository import MeasurementRepository
from app.measurement.schemas import EntityFact


REPO_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_DIR / "backend"
STEP_PATH = REPO_DIR / "XMS06-DN80.stp"
REVISION_ID = UUID("55555555-5555-5555-5555-555555555555")


async def parse_xms06_entities():
    cad_script_dir = Path("freecad_scripts") if Path.cwd().resolve() == BACKEND_DIR else Path("backend/freecad_scripts")
    settings = Settings(cad_script_dir=cad_script_dir)
    work_dir = Path(tempfile.mkdtemp(prefix="xms06-measurement-"))
    try:
        result = await run_freecad_parser(STEP_PATH, REVISION_ID, work_dir, settings)
        return [
            EntityFact(
                id=entity["id"],
                revision_id=entity["revision_id"],
                parent_entity_id=entity["parent_entity_id"],
                entity_type=entity["entity_type"],
                geometry_type=entity["geometry_type"],
                geometry=entity["geometry"] or {},
                center=entity["center"] if isinstance(entity["center"], list) else None,
                bounding_box=entity["bounding_box"],
                area=entity["area"],
                length=entity["length"],
                source_ref=entity["source_ref"],
            )
            for entity in result["entities"]
        ]
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def measurement_value(facts, measurement_type):
    matches = [measurement for measurement in facts.measurements if measurement.measurement_type == measurement_type]
    assert matches, measurement_type
    return matches[0].normalized_value["value"]


def assert_close(actual, expected, tolerance=0.1):
    assert abs(float(actual) - expected) <= tolerance


@pytest.mark.asyncio
async def test_xms06_measurement_acceptance_values_and_sources():
    entities = await parse_xms06_entities()
    entity_ids = {entity.id for entity in entities}

    facts = build_measurement_facts(entities)
    axis_candidates = [feature for feature in facts.features if feature.feature_type == "main_axis_candidate"]
    top_confidence = max(feature.confidence for feature in axis_candidates)
    top_axes = [feature for feature in axis_candidates if feature.confidence == top_confidence]
    assert len(top_axes) == 1
    assert top_axes[0].confidence >= 0.90

    assert_close(measurement_value(facts, "maximum_radial_diameter"), 200.0)
    assert_close(measurement_value(facts, "overall_length_along_main_axis"), 50.0)

    patterns = [feature for feature in facts.features if feature.feature_type == "circular_pattern"]
    assert len(patterns) == 1
    pattern = patterns[0]
    assert pattern.parameters["count"] == 8
    assert_close(pattern.parameters["member_diameter"], 18.0)
    assert_close(pattern.parameters["pitch_circle_diameter"], 160.0)
    assert_close(pattern.parameters["angular_spacing"], 45.0)

    for measurement in facts.measurements:
        assert measurement.method
        assert measurement.algorithm_version
        assert measurement.source_entity_ids
        assert all(source_id in entity_ids for source_id in measurement.source_entity_ids)
        assert measurement.unit
        assert measurement.raw_value is not measurement.normalized_value
        assert measurement.raw_value == measurement.normalized_value


def box_entity(x=10, y=20, z=30):
    revision_id = uuid4()
    return EntityFact(
        id=uuid4(),
        revision_id=revision_id,
        parent_entity_id=None,
        entity_type="solid",
        geometry_type=None,
        geometry={},
        center=[0, 0, 0],
        bounding_box={"min": [0, 0, 0], "max": [x, y, z]},
        area=None,
        length=None,
        source_ref="Box",
    )


def circle_entity(revision_id, parent_id, center, radius=3):
    return EntityFact(
        id=uuid4(),
        revision_id=revision_id,
        parent_entity_id=parent_id,
        entity_type="edge",
        geometry_type="circle",
        geometry={"axis": [0, 0, 1], "center": center, "radius": radius},
        center=center,
        bounding_box=None,
        area=None,
        length=None,
        source_ref="Circle",
    )


def test_negative_shapes_do_not_create_circular_pattern():
    box = box_entity()
    assert not [feature for feature in build_measurement_facts([box]).features if feature.feature_type == "circular_pattern"]

    cylinder = EntityFact(
        id=uuid4(),
        revision_id=box.revision_id,
        parent_entity_id=box.id,
        entity_type="face",
        geometry_type="cylinder",
        geometry={"axis": [0, 0, 1], "center": [0, 0, 0], "radius": 5},
        center=[0, 0, 0],
        bounding_box=None,
        area=100,
        length=None,
        source_ref="Cylinder",
    )
    assert not [feature for feature in build_measurement_facts([box, cylinder]).features if feature.feature_type == "circular_pattern"]

    random_holes = [
        box,
        circle_entity(box.revision_id, box.id, [2, 3, 0]),
        circle_entity(box.revision_id, box.id, [8, 17, 0]),
    ]
    assert not [feature for feature in build_measurement_facts(random_holes).features if feature.feature_type == "circular_pattern"]


class ReplacingMemorySession:
    def __init__(self):
        self.features = []
        self.measurements = []

    def begin(self):
        class Tx:
            async def __aenter__(tx_self):
                return self

            async def __aexit__(tx_self, exc_type, exc, tb):
                return False

        return Tx()

    async def execute(self, statement):
        text = str(statement)
        if "cad_measurements" in text:
            self.measurements = []
        if "cad_feature_candidates" in text:
            self.features = []

    def add_all(self, rows):
        for row in rows:
            if isinstance(row, CadFeatureCandidate):
                self.features.append(row)
            if isinstance(row, CadMeasurement):
                self.measurements.append(row)


@pytest.mark.asyncio
async def test_measurement_repository_rerun_is_idempotent_for_counts_and_uuids():
    entities = await parse_xms06_entities()
    facts = build_measurement_facts(entities)
    session = ReplacingMemorySession()
    repo = MeasurementRepository(session)

    await repo.replace_results(REVISION_ID, facts.features, facts.measurements, algorithm_version="phase2.v1")
    first_feature_ids = [feature.id for feature in session.features]
    first_measurement_ids = [measurement.id for measurement in session.measurements]
    await repo.replace_results(REVISION_ID, facts.features, facts.measurements, algorithm_version="phase2.v1")

    assert [feature.id for feature in session.features] == first_feature_ids
    assert [measurement.id for measurement in session.measurements] == first_measurement_ids
    assert len(session.features) == len(first_feature_ids)
    assert len(session.measurements) == len(first_measurement_ids)
