# 事务化保存规格字段绑定及独立证据行，保留旧字段的 superseded 状态。
from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadSpecField, CadSpecFieldEvidence
from app.spec.bindings import SpecFieldBinding


# 将绑定计算结果映射为规格字段及图纸、测量两类证据记录。
class SpecFieldRepository:
    # 保存用于替换字段和证据的异步数据库会话。
    def __init__(self, session: AsyncSession):
        self.session = session

    # 先淘汰当前字段，再刷新新字段主键并插入证据；任一步失败均回滚事务。
    async def replace_bindings(self, task_id: uuid.UUID, bindings: list[SpecFieldBinding]) -> None:
        try:
            await self.session.execute(
                update(CadSpecField)
                .where(CadSpecField.task_id == task_id, CadSpecField.status == "current")
                .values(status="superseded")
            )
            field_rows = [self._field_row(binding) for binding in bindings]
            self.session.add_all(field_rows)
            # 先确保字段主键可用，再将两类证据分别关联到相应字段，和字段一起提交。
            await self.session.flush()
            evidence_rows = []
            for field, binding in zip(field_rows, bindings, strict=True):
                evidence_rows.extend(self._evidence_rows(field.id, binding))
            self.session.add_all(evidence_rows)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    # 复制绑定的值、状态和来源信息，未提供 ID 时按任务、字段及符号生成 UUID。
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

    # 仅在证据 ID 存在时分别建立图纸事实和测量证据，保留各自值与置信度。
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

