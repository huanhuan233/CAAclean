import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from uuid import UUID

import pytest

from app.cad.repository import CadRepository
from app.cad.parser_runner import run_freecad_parser
from app.cad.result_validator import validate_parser_result
from app.core.config import Settings
from app.db.models import CadEntity, CadMesh


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
STEP_PATH = REPO_DIR / "XMS06-DN80.stp"
GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "xms06-topology-v2-golden.json"
FIXED_REVISION_ID = UUID("11111111-1111-1111-1111-111111111111")


class CapturingSession:
    def __init__(self, revision_id):
        self.revision = type("Revision", (), {"id": revision_id})()
        self.rows = []

    def begin(self):
        class Tx:
            async def __aenter__(tx_self):
                return self

            async def __aexit__(tx_self, exc_type, exc, tb):
                self.transaction_committed = exc_type is None
                return False

        return Tx()

    async def get(self, model, key):
        return self.revision

    async def execute(self, statement):
        return None

    def add_all(self, rows):
        self.rows.extend(rows)

    async def flush(self):
        return None


async def parse_xms06(revision_id=FIXED_REVISION_ID):
    cad_script_dir = Path("freecad_scripts") if Path.cwd().resolve() == BACKEND_DIR else Path("backend/freecad_scripts")
    settings = Settings(cad_script_dir=cad_script_dir)
    work_dir = Path(tempfile.mkdtemp(prefix="xms06-phase1-"))
    try:
        return await run_freecad_parser(STEP_PATH, revision_id, work_dir, settings)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def entities_by_type(result, entity_type):
    return [entity for entity in result["entities"] if entity["entity_type"] == entity_type]


def relations_by_type(result, relation_type):
    return [relation for relation in result["relations"] if relation["relation_type"] == relation_type]


@pytest.mark.asyncio
async def test_xms06_counts_match_revision_entities_meshes_and_golden_fixture():
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    result = await parse_xms06()
    faces = entities_by_type(result, "face")
    edges = entities_by_type(result, "edge")
    vertices = entities_by_type(result, "vertex")
    shells = entities_by_type(result, "shell")
    wires = entities_by_type(result, "wire")
    face_meshes = [mesh for mesh in result["meshes"] if mesh["mesh_type"] == "face"]
    summary = result["summary"]

    assert result["schema_version"] == golden["schema_version"]
    assert summary["face_count"] == len(faces) == len(face_meshes) == golden["face_count"] == 38
    assert summary["edge_count"] == len(edges) == golden["edge_count"]
    assert summary["vertex_count"] == len(vertices) == golden["vertex_count"]
    assert summary["shell_count"] == len(shells) == golden["shell_count"]
    assert summary["wire_count"] == len(wires) == golden["wire_count"]
    assert len(result["entities"]) == golden["entity_count"]
    assert len(result["relations"]) == golden["relation_count"]
    assert len(result["meshes"]) == golden["mesh_count"]


@pytest.mark.asyncio
async def test_xms06_persisted_revision_face_count_matches_face_entities_and_meshes():
    result = validate_parser_result(await parse_xms06())
    session = CapturingSession(result.revision_id)

    await CadRepository(session).persist_parser_result(result.revision_id, result)

    face_entities = [row for row in session.rows if isinstance(row, CadEntity) and row.entity_type == "face"]
    face_meshes = [row for row in session.rows if isinstance(row, CadMesh) and row.mesh_type == "face"]
    assert session.revision.face_count == len(face_entities) == len(face_meshes) == 38
    assert session.revision.edge_count == len([row for row in session.rows if isinstance(row, CadEntity) and row.entity_type == "edge"])
    assert session.revision.vertex_count == len([row for row in session.rows if isinstance(row, CadEntity) and row.entity_type == "vertex"])
    assert session.transaction_committed is True


@pytest.mark.asyncio
async def test_xms06_topology_relations_are_complete_and_reference_existing_entities():
    result = await parse_xms06()
    entity_by_id = {entity["id"]: entity for entity in result["entities"]}
    faces = entities_by_type(result, "face")
    edges = entities_by_type(result, "edge")
    vertices = entities_by_type(result, "vertex")
    bounded_by_edge = relations_by_type(result, "bounded_by_edge")
    has_vertex = relations_by_type(result, "has_vertex")

    for relation in result["relations"]:
        assert relation["source_entity_id"] in entity_by_id
        assert relation["target_entity_id"] in entity_by_id

    face_edge_counts = defaultdict(int)
    edge_face_counts = defaultdict(int)
    for relation in bounded_by_edge:
        face_edge_counts[relation["source_entity_id"]] += 1
        edge_face_counts[relation["target_entity_id"]] += 1

    edge_vertex_counts = defaultdict(int)
    for relation in has_vertex:
        edge_vertex_counts[relation["source_entity_id"]] += 1

    assert all(face_edge_counts[face["id"]] >= 1 for face in faces)
    assert all(edge_face_counts[edge["id"]] >= 1 for edge in edges)
    assert all(edge_vertex_counts[edge["id"]] >= 1 for edge in edges)

    solids = entities_by_type(result, "solid")
    for solid in solids:
        solid_edges = [edge for edge in edges if edge["parent_entity_id"] == solid["id"]]
        solid_vertices = [vertex for vertex in vertices if vertex["parent_entity_id"] == solid["id"]]
        assert len({edge["source_ref"] for edge in solid_edges}) == len(solid_edges)
        assert len({vertex["source_ref"] for vertex in solid_vertices}) == len(solid_vertices)


@pytest.mark.asyncio
async def test_xms06_same_revision_rerun_keeps_topology_uuids_and_relation_counts_stable():
    first = await parse_xms06()
    second = await parse_xms06()

    for entity_type in ("face", "edge", "vertex"):
        first_ids = [entity["id"] for entity in entities_by_type(first, entity_type)]
        second_ids = [entity["id"] for entity in entities_by_type(second, entity_type)]
        assert first_ids == second_ids
        assert len(first_ids) == len(second_ids)

    assert len(first["relations"]) == len(second["relations"])
