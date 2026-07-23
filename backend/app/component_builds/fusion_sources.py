from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.component_builds.fusion import FusionSources
from app.db.models import CadDrawingFact, CadFeatureCandidate, CadMeasurement, CadModelRevision, ComponentBuild


class SqlAlchemyFusionSourceReader:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def read(self, build: ComponentBuild) -> FusionSources:
        drawing_facts = []
        measurements = []
        features = []
        revision_data = None

        if build.drawing_task_id is not None:
            result = await self.session.execute(
                select(CadDrawingFact)
                .where(
                    CadDrawingFact.task_id == build.drawing_task_id,
                    CadDrawingFact.status == "current",
                )
                .order_by(CadDrawingFact.created_at, CadDrawingFact.id)
            )
            drawing_facts = [self._drawing_fact(row) for row in result.scalars().all()]

        if build.cad_revision_id is not None:
            revision = await self.session.get(CadModelRevision, build.cad_revision_id)
            if revision is not None:
                revision_data = self._revision(revision)

            measurement_result = await self.session.execute(
                select(CadMeasurement)
                .where(CadMeasurement.revision_id == build.cad_revision_id)
                .order_by(CadMeasurement.created_at, CadMeasurement.id)
            )
            measurements = [self._measurement(row) for row in measurement_result.scalars().all()]

            feature_result = await self.session.execute(
                select(CadFeatureCandidate)
                .where(CadFeatureCandidate.revision_id == build.cad_revision_id)
                .order_by(CadFeatureCandidate.created_at, CadFeatureCandidate.id)
            )
            features = [self._feature(row) for row in feature_result.scalars().all()]

        return FusionSources(
            drawing_facts=drawing_facts,
            measurements=measurements,
            features=features,
            revision=revision_data,
        )

    @staticmethod
    def _revision(row: CadModelRevision) -> dict:
        return {
            "id": str(row.id),
            "source_file_name": row.source_file_name,
            "source_sha256": row.source_sha256,
            "parser_name": row.parser_name,
            "parser_version": row.parser_version,
            "unit": row.unit,
            "object_count": row.object_count,
            "solid_count": row.solid_count,
            "face_count": row.face_count,
            "edge_count": row.edge_count,
            "vertex_count": row.vertex_count,
            "bounding_box": row.bounding_box,
            "summary": row.summary or {},
        }

    @staticmethod
    def _drawing_fact(row: CadDrawingFact) -> dict:
        return {
            "id": str(row.id),
            "fact_key": row.fact_key,
            "fact_type": row.fact_type,
            "symbol": row.symbol,
            "label": row.label,
            "operator": row.operator,
            "raw_value": row.raw_value,
            "normalized_value": row.normalized_value,
            "value_type": row.value_type,
            "unit": row.unit,
            "confidence": row.confidence,
            "needs_review": row.needs_review,
            "metadata": row.metadata_json or {},
        }

    @staticmethod
    def _measurement(row: CadMeasurement) -> dict:
        return {
            "id": str(row.id),
            "measurement_type": row.measurement_type,
            "normalized_value": row.normalized_value,
            "unit": row.unit,
            "confidence": row.confidence,
            "metadata": row.metadata_json or {},
        }

    @staticmethod
    def _feature(row: CadFeatureCandidate) -> dict:
        return {
            "id": str(row.id),
            "feature_type": row.feature_type,
            "parameters": row.parameters or {},
            "axis": row.axis,
            "center": row.center,
            "confidence": row.confidence,
            "status": row.status,
            "metadata": row.metadata_json or {},
        }
