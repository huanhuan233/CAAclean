# 封装测量实体读取、候选与尺寸结果持久化，以及按修订和算法版本隔离的结果查询。
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadEntity, CadFeatureCandidate, CadMeasurement, ComponentBuild, CadModelRevision
from app.measurement.schemas import EntityFact, FeatureCandidateFact, MeasurementFact, stable_uuid


# 围绕一个异步会话读写尺寸与候选记录，重算结果按算法版本替换。
class MeasurementRepository:
    # 保存调用方提供的数据库会话，使同次服务调用复用事务上下文。
    def __init__(self, session: AsyncSession):
        self.session = session

    # 解析构建所指修订及首个根实体；缺少构建或修订时返回空上下文。
    async def get_build_context(self, build_id: uuid.UUID):
        build = await self.session.get(ComponentBuild, build_id)
        if build is None or build.cad_revision_id is None:
            return None
        revision = await self.session.get(CadModelRevision, build.cad_revision_id)
        if revision is None:
            return None
        root = await self.session.scalar(
            select(CadEntity).where(CadEntity.revision_id == revision.id,
                                    CadEntity.parent_entity_id.is_(None)).limit(1)
        )
        return build, revision, root

    # 按稳定编号幂等保存交互结果；并发唯一键冲突后回滚并读取已落库记录。
    async def save_interactive_result(self, fact: MeasurementFact) -> CadMeasurement:
        row = self._measurement_row(fact)
        existing = await self.session.get(CadMeasurement, row.id)
        if existing is not None:
            return existing
        try:
            self.session.add(row)
            await self.session.commit()
            return row
        except IntegrityError:
            await self.session.rollback()
            existing = await self.session.get(CadMeasurement, row.id)
            if existing is not None:
                return existing
            raise
        except Exception:
            await self.session.rollback()
            raise

    # 只查询两个受支持交互算法版本，按创建时间倒序返回指定数量。
    async def list_interactive_results(self, revision_id: uuid.UUID, limit: int = 50) -> list[CadMeasurement]:
        result = await self.session.execute(
            select(CadMeasurement).where(CadMeasurement.revision_id == revision_id,
                                         CadMeasurement.algorithm_version.in_(["interactive.p1.v1", "interactive.p1.v2"]))
            .order_by(CadMeasurement.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    # 按树路径读取当前修订拓扑，并转换为批量算法使用的纯数据记录。
    async def list_entity_facts(self, revision_id: uuid.UUID) -> list[EntityFact]:
        result = await self.session.execute(select(CadEntity).where(CadEntity.revision_id == revision_id).order_by(CadEntity.tree_path))
        return [
            EntityFact(
                id=entity.id,
                revision_id=entity.revision_id,
                parent_entity_id=entity.parent_entity_id,
                entity_type=entity.entity_type,
                geometry_type=entity.geometry_type,
                geometry=entity.geometry or {},
                center=entity.center if isinstance(entity.center, list) else None,
                bounding_box=entity.bounding_box,
                area=entity.area,
                length=entity.length,
                source_ref=entity.source_ref,
            )
            for entity in result.scalars().all()
        ]

    # 在一次事务中删除指定修订与算法版本的旧结果后插入新结果，失败即回滚。
    async def replace_results(
        self,
        revision_id: uuid.UUID,
        features: list[FeatureCandidateFact],
        measurements: list[MeasurementFact],
        *,
        algorithm_version: str,
    ) -> None:
        try:
            await self.session.execute(
                delete(CadMeasurement).where(
                    CadMeasurement.revision_id == revision_id,
                    CadMeasurement.algorithm_version == algorithm_version,
                )
            )
            await self.session.execute(
                delete(CadFeatureCandidate).where(
                    CadFeatureCandidate.revision_id == revision_id,
                    CadFeatureCandidate.algorithm_version == algorithm_version,
                )
            )
            self.session.add_all([self._feature_row(feature) for feature in features])
            self.session.add_all([self._measurement_row(measurement) for measurement in measurements])
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    # 按类型、作用域和最低置信度分页读取尺寸，同时返回相同筛选条件下的总数。
    async def list_measurements(
        self,
        revision_id: uuid.UUID,
        *,
        measurement_type: str | None = None,
        scope_entity_id: uuid.UUID | None = None,
        confidence_min: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        filters = [CadMeasurement.revision_id == revision_id]
        if measurement_type:
            filters.append(CadMeasurement.measurement_type == measurement_type)
        if scope_entity_id:
            filters.append(CadMeasurement.scope_entity_id == scope_entity_id)
        if confidence_min is not None:
            filters.append(CadMeasurement.confidence >= confidence_min)
        total = await self.session.scalar(select(func.count()).select_from(CadMeasurement).where(*filters))
        result = await self.session.execute(
            select(CadMeasurement)
            .where(*filters)
            .order_by(CadMeasurement.measurement_type, CadMeasurement.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    # 按尺寸主键读取单条记录，所属构建和版本约束由服务或接口继续检查。
    async def get_measurement(self, measurement_id: uuid.UUID) -> CadMeasurement | None:
        return await self.session.get(CadMeasurement, measurement_id)

    # 按特征类型、作用域和置信度分页读取候选，状态仍由记录自身表达。
    async def list_features(
        self,
        revision_id: uuid.UUID,
        *,
        feature_type: str | None = None,
        scope_entity_id: uuid.UUID | None = None,
        confidence_min: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        filters = [CadFeatureCandidate.revision_id == revision_id]
        if feature_type:
            filters.append(CadFeatureCandidate.feature_type == feature_type)
        if scope_entity_id:
            filters.append(CadFeatureCandidate.scope_entity_id == scope_entity_id)
        if confidence_min is not None:
            filters.append(CadFeatureCandidate.confidence >= confidence_min)
        total = await self.session.scalar(select(func.count()).select_from(CadFeatureCandidate).where(*filters))
        result = await self.session.execute(
            select(CadFeatureCandidate)
            .where(*filters)
            .order_by(CadFeatureCandidate.feature_type, CadFeatureCandidate.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), int(total or 0)

    # 按主键读取候选记录，缺失时返回空值。
    async def get_feature(self, feature_id: uuid.UUID) -> CadFeatureCandidate | None:
        return await self.session.get(CadFeatureCandidate, feature_id)

    # 保留已有候选编号，否则按语义生成编号，并将 UUID 来源列表转换为数据库 JSON 可存形式。
    def _feature_row(self, feature: FeatureCandidateFact) -> CadFeatureCandidate:
        feature_id = feature.id or stable_uuid(
            feature.revision_id,
            feature.algorithm_version,
            "feature",
            {
                "type": feature.feature_type,
                "scope": str(feature.scope_entity_id),
                "sources": sorted(str(source_id) for source_id in feature.source_entity_ids),
                "parameters": feature.parameters,
            },
        )
        return CadFeatureCandidate(
            id=feature_id,
            revision_id=feature.revision_id,
            scope_entity_id=feature.scope_entity_id,
            feature_type=feature.feature_type,
            source_entity_ids=[str(entity_id) for entity_id in feature.source_entity_ids],
            parameters=feature.parameters,
            axis=feature.axis,
            center=feature.center,
            confidence=feature.confidence,
            algorithm=feature.algorithm,
            algorithm_version=feature.algorithm_version,
            status=feature.status,
            metadata_json=feature.metadata,
        )

    # 将原始值、规范值和方法映射到数据库行，缺少编号时按尺寸内容生成稳定身份。
    def _measurement_row(self, measurement: MeasurementFact) -> CadMeasurement:
        measurement_id = measurement.id or stable_uuid(
            measurement.revision_id,
            measurement.algorithm_version,
            "measurement",
            {
                "type": measurement.measurement_type,
                "scope": str(measurement.scope_entity_id),
                "sources": sorted(str(source_id) for source_id in measurement.source_entity_ids),
                "value": measurement.normalized_value,
                "method": measurement.method,
            },
        )
        return CadMeasurement(
            id=measurement_id,
            revision_id=measurement.revision_id,
            scope_entity_id=measurement.scope_entity_id,
            feature_id=measurement.feature_id,
            measurement_type=measurement.measurement_type,
            raw_value=measurement.raw_value,
            normalized_value=measurement.normalized_value,
            unit=measurement.unit,
            source_entity_ids=[str(entity_id) for entity_id in measurement.source_entity_ids],
            method=measurement.method,
            confidence=measurement.confidence,
            algorithm_version=measurement.algorithm_version,
            metadata_json=measurement.metadata,
        )
