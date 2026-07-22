from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadSpecField, CadSpecFieldEvidence
from app.spec.bindings import SpecFieldBinding


class SpecFieldRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def replace_bindings(self, task_id: uuid.UUID, bindings: list[SpecFieldBinding]) -> None:
        try:
            await self.session.execute(
                update(CadSpecField)
                .where(CadSpecField.task_id == task_id, CadSpecField.status == "current")
                .values(status="superseded")
            )
            field_rows = [self._field_row(binding) for binding in bindings]
            self.session.add_all(field_rows)
            await self.session.flush()
            evidence_rows = []
            for field, binding in zip(field_rows, bindings, strict=True):
                evidence_rows.extend(self._evidence_rows(field.id, binding))
            self.session.add_all(evidence_rows)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    def _field_row(self, binding: SpecFieldBinding) -> CadSpecField:
        return CadSpecField(
            id=binding.id or uuid.uuid5(uuid.NAMESPACE_URL, f"{binding.task_id}:{binding.field_name}:{binding.symbol}"),
            task_id=binding.task_id,
            revision_id=binding.revision_id,
            field_name=binding.field_name,
            profile_id=binding.profile_id,
            profile_version=binding.profile_version,
            symbol=binding.symbol,
            drawing_value=binding.drawing_value,
            measured_value=binding.measured_value,
            normalized_measured_value=binding.normalized_measured_value,
            resolved_value=binding.resolved_value,
            unit=binding.unit,
            drawing_fact_id=binding.drawing_fact_id,
            measurement_id=binding.measurement_id,
            feature_id=binding.feature_id,
            source_entity_ids=binding.source_entity_ids,
            mapping_status=binding.mapping_status,
            geometry_match_status=binding.geometry_match_status,
            conformance_status=binding.conformance_status,
            review_status=binding.review_status,
            drawing_value_confidence=binding.drawing_value_confidence,
            measurement_confidence=binding.measurement_confidence,
            mapping_confidence=binding.mapping_confidence,
            reason=binding.reason,
            metadata_json=binding.metadata,
            status="current",
        )

    def _evidence_rows(self, field_id: uuid.UUID, binding: SpecFieldBinding) -> list[CadSpecFieldEvidence]:
        rows = []
        if binding.drawing_fact_id:
            rows.append(
                CadSpecFieldEvidence(
                    field_id=field_id,
                    task_id=binding.task_id,
                    revision_id=binding.revision_id,
                    evidence_type="drawing_fact",
                    drawing_fact_id=binding.drawing_fact_id,
                    measurement_id=None,
                    feature_id=None,
                    source_entity_ids=[],
                    value=binding.drawing_value,
                    confidence=binding.drawing_value_confidence,
                    metadata_json={"source": "drawing"},
                )
            )
        if binding.measurement_id:
            rows.append(
                CadSpecFieldEvidence(
                    field_id=field_id,
                    task_id=binding.task_id,
                    revision_id=binding.revision_id,
                    evidence_type="measurement",
                    drawing_fact_id=None,
                    measurement_id=binding.measurement_id,
                    feature_id=binding.feature_id,
                    source_entity_ids=binding.source_entity_ids,
                    value=binding.measured_value,
                    confidence=binding.measurement_confidence,
                    metadata_json={"source": "freecad"},
                )
            )
        return rows

