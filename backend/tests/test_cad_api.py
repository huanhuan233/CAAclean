from uuid import uuid4

from fastapi.testclient import TestClient

from app.cad.router import get_cad_service
from app.main import app


class FakeCadService:
    def __init__(self):
        self.revision_id = uuid4()
        self.model_id = uuid4()

    async def create_model_from_upload(self, file, name):
        content = await file.read()
        if not content:
            raise ValueError("empty STEP/STP file is not allowed")
        return {
            "model_id": self.model_id,
            "revision_id": self.revision_id,
            "status": "queued",
        }

    async def get_revision_status(self, revision_id):
        return {
            "status": "processing",
            "progress": 45,
            "status_message": "extracting_faces",
            "error_code": None,
            "error_message": None,
        }

    async def list_models(self, page, page_size):
        return {
            "items": [
                {
                    "id": str(self.model_id),
                    "name": "XMS06-DN80",
                    "current_revision_id": str(self.revision_id),
                    "status": "completed",
                    "progress": 100,
                }
            ],
            "total": 1,
            "page": page,
            "page_size": page_size,
        }

    async def get_revision_tree(self, revision_id):
        return [
            {
                "id": str(uuid4()),
                "parent_entity_id": None,
                "entity_type": "root",
                "label": "XMS06-DN80",
                "source_ref": None,
                "geometry_type": None,
                "children": [
                    {
                        "id": str(uuid4()),
                        "parent_entity_id": None,
                        "entity_type": "solid",
                        "label": "Solid1",
                        "source_ref": "Solid1",
                        "geometry_type": None,
                        "children": [],
                    }
                ],
            }
        ]

    async def get_structure_tree(self, revision_id):
        return [
            {
                "id": str(uuid4()),
                "parent_entity_id": None,
                "entity_type": "root",
                "label": "source.step",
                "source_ref": None,
                "geometry_type": None,
                "children": [
                    {
                        "id": str(uuid4()),
                        "parent_entity_id": None,
                        "entity_type": "imported_object",
                        "label": "XMS06-DN80",
                        "source_ref": "XMS06-DN80",
                        "geometry_type": None,
                        "children": [
                            {
                                "id": str(uuid4()),
                                "parent_entity_id": None,
                                "entity_type": "solid",
                                "label": "Solid1",
                                "source_ref": "Solid1",
                                "geometry_type": None,
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]

    async def list_revision_entities(self, revision_id, **params):
        return {
            "items": [
                {
                    "id": str(uuid4()),
                    "revision_id": str(revision_id),
                    "parent_entity_id": None,
                    "entity_type": params.get("entity_type") or "face",
                    "source_ref": "Face11",
                    "source_index": 10,
                    "name": None,
                    "label": None,
                    "tree_path": "/root/0/solid-0/face-10",
                    "sort_order": 10,
                    "geometry_type": params.get("geometry_type") or "plane",
                    "area": 12.5,
                    "volume": None,
                    "length": None,
                    "center": [0, 0, 0],
                    "bounding_box": {"min": [0, 0, 0], "max": [1, 1, 1]},
                    "placement": None,
                    "geometry": {"normal": [0, 0, 1]},
                    "metadata": {},
                }
            ],
            "total": 1,
            "page": params.get("page", 1),
            "page_size": params.get("page_size", 20),
        }

    async def list_revision_meshes(self, revision_id, **params):
        return {
            "items": [
                {
                    "id": str(uuid4()),
                    "revision_id": str(revision_id),
                    "entity_id": str(uuid4()),
                    "mesh_type": "face",
                    "positions": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                    "indices": [[0, 1, 2]],
                    "normals": None,
                    "color": None,
                    "linear_deflection": 0.1,
                    "angular_deflection": 0.5,
                    "vertex_count": 3,
                    "triangle_count": 1,
                }
            ],
            "total": 1,
            "page": params.get("page", 1),
            "page_size": params.get("page_size", 1000),
        }

    async def get_face_topology(self, revision_id, face_id):
        return {
            "edges": [{"id": str(uuid4()), "source_ref": "Face11.Edge2", "geometry_type": "line"}],
            "adjacent_faces": [{"id": str(uuid4()), "source_ref": "Face12", "geometry_type": "plane"}],
        }

    async def get_edge_topology(self, revision_id, edge_id):
        return {
            "vertices": [{"id": str(uuid4()), "source_ref": "Vertex1", "geometry": {"point": [0, 0, 0]}}],
            "faces": [{"id": str(uuid4()), "source_ref": "Face11", "geometry_type": "plane"}],
        }


def make_client():
    service = FakeCadService()
    app.dependency_overrides[get_cad_service] = lambda: service
    return TestClient(app), service


def test_upload_rejects_non_step_file():
    client, _ = make_client()

    response = client.post(
        "/api/cad/models",
        files={"file": ("bad.txt", b"not step", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "only STEP/STP files are supported"


def test_upload_rejects_empty_step_file():
    client, _ = make_client()

    response = client.post(
        "/api/cad/models",
        files={"file": ("empty.stp", b"", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "empty STEP/STP file is not allowed"


def test_upload_accepts_stp_file():
    client, service = make_client()

    response = client.post(
        "/api/cad/models",
        files={"file": ("XMS06-DN80.stp", b"ISO-10303-21;", "application/octet-stream")},
        data={"name": "XMS06-DN80"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "model_id": str(service.model_id),
        "revision_id": str(service.revision_id),
        "status": "queued",
    }


def test_revision_status_response():
    client, service = make_client()

    response = client.get(f"/api/cad/revisions/{service.revision_id}/status")

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert response.json()["progress"] == 45


def test_model_list_response():
    client, service = make_client()

    response = client.get("/api/cad/models")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["current_revision_id"] == str(service.revision_id)


def test_revision_tree_response():
    client, service = make_client()

    response = client.get(f"/api/cad/revisions/{service.revision_id}/tree")

    assert response.status_code == 200
    assert response.json()[0]["entity_type"] == "root"
    assert response.json()[0]["children"][0]["entity_type"] == "solid"


def test_structure_tree_excludes_brep_leaf_entities():
    client, service = make_client()

    response = client.get(f"/api/cad/revisions/{service.revision_id}/structure-tree")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["label"] == "source.step"
    assert payload[0]["children"][0]["children"][0]["entity_type"] == "solid"


def test_revision_entities_supports_face_query():
    client, service = make_client()

    response = client.get(
        f"/api/cad/revisions/{service.revision_id}/entities",
        params={"entity_type": "face", "keyword": "Face11", "page": 1, "page_size": 20},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["source_ref"] == "Face11"


def test_revision_meshes_response():
    client, service = make_client()

    response = client.get(f"/api/cad/revisions/{service.revision_id}/meshes")

    assert response.status_code == 200
    assert response.json()["items"][0]["mesh_type"] == "face"


def test_face_topology_response():
    client, service = make_client()

    response = client.get(f"/api/cad/revisions/{service.revision_id}/faces/{uuid4()}/topology")

    assert response.status_code == 200
    assert response.json()["edges"][0]["source_ref"] == "Face11.Edge2"


def test_edge_topology_response():
    client, service = make_client()

    response = client.get(f"/api/cad/revisions/{service.revision_id}/edges/{uuid4()}/topology")

    assert response.status_code == 200
    assert response.json()["vertices"][0]["geometry"]["point"] == [0, 0, 0]


def test_v2_export_is_reserved():
    client, service = make_client()

    response = client.post(f"/api/cad/revisions/{service.revision_id}/exports/v2")

    assert response.status_code == 501
    assert response.json() == {
        "detail": {
            "code": "v2_integration_not_implemented",
            "message": "V2 integration is reserved for a later phase.",
        }
    }
