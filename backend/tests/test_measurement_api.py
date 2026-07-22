from uuid import uuid4

from fastapi.testclient import TestClient

from app.cad.router import get_cad_service
from app.main import app


class FakeMeasurementCadService:
    def __init__(self):
        self.revision_id = uuid4()
        self.measurement_id = uuid4()
        self.feature_id = uuid4()
        self.scope_id = uuid4()
        self.source_id = uuid4()
        self.recomputed = False

    async def list_revision_measurements(self, revision_id, **params):
        assert params["measurement_type"] == "maximum_radial_diameter"
        assert params["confidence_min"] == 0.9
        return {
            "items": [
                {
                    "id": str(self.measurement_id),
                    "revision_id": str(revision_id),
                    "scope_entity_id": str(self.scope_id),
                    "feature_id": None,
                    "measurement_type": "maximum_radial_diameter",
                    "raw_value": {"value": 200.0},
                    "normalized_value": {"value": 200.0},
                    "unit": "mm",
                    "source_entity_ids": [str(self.source_id)],
                    "method": "analytic_radial_diameter",
                    "confidence": 0.95,
                    "algorithm_version": "phase2.v1",
                    "metadata": {},
                    "created_at": "2026-07-22T00:00:00+00:00",
                }
            ],
            "total": 1,
            "page": params["page"],
            "page_size": params["page_size"],
        }

    async def get_revision_measurement(self, revision_id, measurement_id):
        if measurement_id != self.measurement_id:
            raise LookupError("measurement not found")
        return {
            "id": str(measurement_id),
            "revision_id": str(revision_id),
            "scope_entity_id": str(self.scope_id),
            "feature_id": None,
            "measurement_type": "maximum_radial_diameter",
            "raw_value": {"value": 200.0},
            "normalized_value": {"value": 200.0},
            "unit": "mm",
            "source_entity_ids": [str(self.source_id)],
            "method": "analytic_radial_diameter",
            "confidence": 0.95,
            "algorithm_version": "phase2.v1",
            "metadata": {},
            "created_at": "2026-07-22T00:00:00+00:00",
        }

    async def list_revision_features(self, revision_id, **params):
        assert params["feature_type"] == "circular_pattern"
        return {
            "items": [
                {
                    "id": str(self.feature_id),
                    "revision_id": str(revision_id),
                    "scope_entity_id": str(self.scope_id),
                    "feature_type": "circular_pattern",
                    "source_entity_ids": [str(self.source_id)],
                    "parameters": {"count": 8, "member_diameter": 18, "pitch_circle_diameter": 160, "angular_spacing": 45},
                    "axis": [0, 1, 0],
                    "center": [0, -39, 0],
                    "confidence": 0.95,
                    "algorithm": "circular_patterns",
                    "algorithm_version": "phase2.v1",
                    "status": "candidate",
                    "metadata": {},
                    "created_at": "2026-07-22T00:00:00+00:00",
                    "updated_at": "2026-07-22T00:00:00+00:00",
                }
            ],
            "total": 1,
            "page": params["page"],
            "page_size": params["page_size"],
        }

    async def get_revision_feature(self, revision_id, feature_id):
        if feature_id != self.feature_id:
            raise LookupError("feature not found")
        return (await self.list_revision_features(revision_id, feature_type="circular_pattern", page=1, page_size=20))["items"][0]

    async def recompute_revision_measurements(self, revision_id):
        self.recomputed = True
        return {"revision_id": str(revision_id), "algorithm_version": "phase2.v1", "feature_count": 2, "measurement_count": 3}


def make_client():
    service = FakeMeasurementCadService()
    app.dependency_overrides[get_cad_service] = lambda: service
    return TestClient(app), service


def test_measurement_list_and_detail_endpoints():
    client, service = make_client()

    response = client.get(
        f"/api/cad/revisions/{service.revision_id}/measurements",
        params={"measurement_type": "maximum_radial_diameter", "confidence_min": 0.9, "page": 2, "page_size": 10},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["measurement_type"] == "maximum_radial_diameter"

    detail = client.get(f"/api/cad/revisions/{service.revision_id}/measurements/{service.measurement_id}")
    assert detail.status_code == 200
    assert detail.json()["source_entity_ids"] == [str(service.source_id)]


def test_feature_list_detail_and_recompute_endpoints():
    client, service = make_client()

    response = client.get(
        f"/api/cad/revisions/{service.revision_id}/features",
        params={"feature_type": "circular_pattern", "scope_entity_id": str(service.scope_id), "page": 1, "page_size": 5},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["parameters"]["count"] == 8

    detail = client.get(f"/api/cad/revisions/{service.revision_id}/features/{service.feature_id}")
    assert detail.status_code == 200
    assert detail.json()["feature_type"] == "circular_pattern"

    recompute = client.post(f"/api/cad/revisions/{service.revision_id}/measurements/recompute")
    assert recompute.status_code == 200
    assert recompute.json()["measurement_count"] == 3
    assert service.recomputed is True
