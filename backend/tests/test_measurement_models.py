from app.db.base import Base
from app.db.models import CadFeatureCandidate, CadMeasurement


def column_names(model):
    return {column.name for column in model.__table__.columns}


def test_phase2_tables_are_registered_with_required_columns():
    assert "cad_feature_candidates" in Base.metadata.tables
    assert "cad_measurements" in Base.metadata.tables

    assert {
        "id",
        "revision_id",
        "scope_entity_id",
        "feature_type",
        "source_entity_ids",
        "parameters",
        "axis",
        "center",
        "confidence",
        "algorithm",
        "algorithm_version",
        "status",
        "metadata",
        "created_at",
        "updated_at",
    }.issubset(column_names(CadFeatureCandidate))

    assert {
        "id",
        "revision_id",
        "scope_entity_id",
        "feature_id",
        "measurement_type",
        "raw_value",
        "normalized_value",
        "unit",
        "source_entity_ids",
        "method",
        "confidence",
        "algorithm_version",
        "metadata",
        "created_at",
    }.issubset(column_names(CadMeasurement))
