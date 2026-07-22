from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.cad.repository import CadRepository
from app.db.models import CadMesh


class FailingTransactionSession:
    def __init__(self):
        self.revision = SimpleNamespace(
            id=uuid4(),
            status="processing",
            progress=10,
            status_message="running_freecad",
            error_code=None,
            error_message=None,
        )
        self.rolled_back = False
        self.failed_committed = False
        self.transaction_entries = 0
        self.added = []

    async def get(self, model, key):
        return self.revision

    def begin(self):
        session = self

        class Tx:
            async def __aenter__(self):
                session.transaction_entries += 1
                return session

            async def __aexit__(self, exc_type, exc, tb):
                if exc_type:
                    session.rolled_back = True
                return False

        return Tx()

    async def execute(self, statement):
        return None

    def add_all(self, rows):
        self.added.extend(rows)
        if rows:
            raise RuntimeError("entity insert failed")

    async def flush(self):
        return None

    async def commit(self):
        self.failed_committed = True


class FailingMeshTransactionSession(FailingTransactionSession):
    def __init__(self):
        super().__init__()
        self.committed_rows = []
        self.staged_rows = []

    def add_all(self, rows):
        rows = list(rows)
        if rows and isinstance(rows[0], CadMesh):
            raise RuntimeError("mesh batch 2 failed")
        self.staged_rows.extend(rows)


def parser_result(revision_id):
    entity_id = uuid4()
    return SimpleNamespace(
        parser_name="FreeCAD",
        parser_version="1.1.0",
        schema_version="cad_parse_v2",
        unit="mm",
        bounding_box=None,
        summary={},
        parse_manifest={},
        entities=[
            SimpleNamespace(
                id=entity_id,
                revision_id=revision_id,
                parent_entity_id=None,
                entity_type="root",
                source_ref=None,
                source_index=None,
                name=None,
                label=None,
                tree_path="/root",
                sort_order=0,
                geometry_type=None,
                area=None,
                volume=None,
                length=None,
                center=None,
                bounding_box=None,
                placement=None,
                geometry={},
                metadata={},
                fingerprint=None,
            )
        ],
        relations=[],
        meshes=[],
    )


def parser_result_with_mesh(revision_id):
    result = parser_result(revision_id)
    entity_id = result.entities[0].id
    result.meshes = [
        SimpleNamespace(
            id=uuid4(),
            revision_id=revision_id,
            entity_id=entity_id,
            mesh_type="face",
            positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            indices=[[0, 1, 2]],
            normals=None,
            color=None,
            linear_deflection=0.1,
            angular_deflection=0.5,
            vertex_count=3,
            triangle_count=1,
        )
    ]
    return result


@pytest.mark.asyncio
async def test_persist_parser_result_rolls_back_and_marks_revision_failed_on_write_error():
    session = FailingTransactionSession()
    repo = CadRepository(session)

    with pytest.raises(RuntimeError, match="entity insert failed"):
        await repo.persist_parser_result(session.revision.id, parser_result(session.revision.id))

    assert session.rolled_back is True
    assert session.revision.status == "failed"
    assert session.revision.error_code == "persist_failed"
    assert session.revision.status_message == "failed"
    assert session.failed_committed is True


@pytest.mark.asyncio
async def test_persist_parser_result_mesh_write_failure_leaves_no_partial_parser_rows():
    session = FailingMeshTransactionSession()
    repo = CadRepository(session)

    with pytest.raises(RuntimeError, match="mesh batch 2 failed"):
        await repo.persist_parser_result(session.revision.id, parser_result_with_mesh(session.revision.id))

    assert session.rolled_back is True
    assert session.committed_rows == []
    assert session.revision.status == "failed"
    assert session.revision.error_code == "persist_failed"
