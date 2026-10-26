# 构建仓储负责持久化聚合及按 Revision 查询证据；内存实现仅提供测试所需的数据行为。
from __future__ import annotations

import uuid
import re

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CadDrawingRegion, CadDrawingFact, CadEntity, CadModel, CadModelRevision, CadNativeEvidence, CadNativePropertyFact, CadSpecSource, CadSpecTask, ComponentBuild, ComponentSpecDraft, utc_now
from app.component_builds.native_tree_store import NATIVE_SOURCE_PREFIX


# 以内存字典实现构建与规范草稿存取，可注入版本归属映射验证关联关系。
class MemoryComponentBuildRepository:
    # 创建构建和草稿索引，并保存可选模型版本及图纸任务归属映射。
    def __init__(self, *, revision_models: dict[uuid.UUID, uuid.UUID] | None = None, drawing_task_revisions: dict[uuid.UUID, uuid.UUID] | None = None):
        self.builds: dict[uuid.UUID, ComponentBuild] = {}
        self.component_specs: dict[uuid.UUID, ComponentSpecDraft] = {}
        self.revision_models = revision_models
        self.drawing_task_revisions = drawing_task_revisions

    # 补默认身份、草稿状态、版本和时间，将新构建存入内存索引。
    async def create_build(self, **fields) -> ComponentBuild:
        now = utc_now()
        fields.setdefault("id", uuid.uuid4())
        fields.setdefault("status", "draft")
        fields.setdefault("version", "1.0.0")
        fields.setdefault("created_at", now)
        fields.setdefault("updated_at", now)
        build = ComponentBuild(**fields)
        self.builds[build.id] = build
        return build

    # 按构建 UUID 查询内存记录，不存在时返回空值。
    async def get_build(self, build_id: uuid.UUID) -> ComponentBuild | None:
        return self.builds.get(build_id)

    async def list_native_evidence(self, revision_id: uuid.UUID, kind: str, offset: int, limit: int) -> list[dict]:
        """内存测试仓储不伪造数据库语义；生产实现只从 PostgreSQL 读取。"""
        return []

    # 内存实现不保存原生对象证据，因此返回空值。
    async def get_native_evidence_object(self, revision_id: uuid.UUID, kind: str, object_id: str) -> dict | None:
        return None

    # 内存实现不保存 Feature Center 证据，返回空列表。
    async def get_feature_evidence_by_id(self, revision_id: uuid.UUID, kind: str,
                                         feature_center_id: str) -> list[dict]:
        return []

    # 内存实现没有标注通道，以空页和零总数表示。
    async def list_mbd_annotations(self, revision_id: uuid.UUID, *, offset: int, limit: int,
                                   annotation_kind: str | None = None, set_id: str | None = None,
                                   view_id: str | None = None,
                                   read_status: str | None = None, search: str | None = None) -> tuple[list[dict], int]:
        return [], 0

    # 内存实现没有指定标注事实，返回空列表。
    async def get_mbd_annotation(self, revision_id: uuid.UUID, annotation_id: str) -> list[dict]:
        return []

    # 内存实现没有 PMI 节点事实，返回空列表。
    async def get_mbd_node(self, revision_id: uuid.UUID, pmi_id: str) -> list[dict]:
        return []

    # 内存实现没有 PMI 关联事实，返回空列表。
    async def list_mbd_relations(self, revision_id: uuid.UUID, endpoint_id: str) -> list[dict]:
        return []

    async def list_native_dependency_candidates(self, revision_id: uuid.UUID, object_id: str) -> list[dict]:
        """内存测试仓储没有持久化依赖事实。"""
        return []

    # 更新已存在的内存构建字段并刷新修改时间。
    async def update_build(self, build_id: uuid.UUID, **fields) -> ComponentBuild:
        build = await self._require_build(build_id)
        for name, value in fields.items():
            setattr(build, name, value)
        build.updated_at = utc_now()
        return build

    # 按创建时间与 UUID 倒序排列内存构建，保证稳定返回次序。
    async def list_builds(self) -> list[ComponentBuild]:
        return sorted(self.builds.values(), key=lambda build: (build.created_at, str(build.id)), reverse=True)

    async def list_structure_entities(self, revision_id: uuid.UUID) -> list:
        """用途：内存仓储没有 CAD 实体表时返回空结构，保持旧单元测试向前兼容。"""
        return []

    # 内存仓储没有原生树实体，返回空页。
    async def list_native_tree_entities(self, revision_id: uuid.UUID, parent_node_id: str | None = None, *, offset: int = 0, limit: int | None = None, include_supplemental: bool = True) -> list:
        return []

    # 内存仓储未存原生树，明确返回零节点。
    async def count_native_tree_entities(self, revision_id: uuid.UUID) -> int:
        return 0

    # 内存仓储没有可定位的原生树节点，返回空值。
    async def get_native_tree_entity(self, revision_id: uuid.UUID, node_id: str):
        return None

    # 内存仓储不持有采集属性事实，返回空列表。
    async def list_native_property_facts(self, revision_id: uuid.UUID, subject_ids: set[str], *, parameter_values_only: bool = False) -> list:
        return []

    # 根据当前内存构件编号分配指定前缀的下一个序号。
    async def next_component_id(self, prefix: str) -> str:
        return _next_component_id(prefix, (build.component_id for build in self.builds.values()))

    # 先验证构建存在，再按构建 ID 查找规范草稿。
    async def get_component_spec(self, build_id: uuid.UUID) -> ComponentSpecDraft | None:
        await self._require_build(build_id)
        return self.component_specs.get(build_id)

    # 按构建 ID 新建或替换版本 1.2 草稿数据，并刷新修改时间。
    async def save_component_spec(self, build_id: uuid.UUID, data: dict) -> ComponentSpecDraft:
        await self._require_build(build_id)
        now = utc_now()
        draft = self.component_specs.get(build_id)
        if draft is None:
            draft = ComponentSpecDraft(
                build_id=build_id,
                schema_version="1.2",
                data=data,
                created_at=now,
                updated_at=now,
            )
            self.component_specs[build_id] = draft
        else:
            draft.data = data
            draft.updated_at = now
        return draft

    # 校验模型版本归属；切换 Revision 时解除旧图纸任务，避免跨版本关联。
    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        if self.revision_models is not None and self.revision_models.get(revision_id) != model_id:
            raise ValueError("revision does not belong to model")
        # 图纸事实绑定具体 Revision，切换模型版本后必须解除旧图纸关联。
        if build.cad_revision_id != revision_id:
            build.drawing_task_id = None
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        build.updated_at = utc_now()
        return build

    # 要求构建已有模型版本，并按注入映射验证图纸任务属于该版本。
    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        if build.cad_revision_id is None or (
            self.drawing_task_revisions is not None and self.drawing_task_revisions.get(task_id) != build.cad_revision_id
        ):
            raise ValueError("drawing task does not belong to build revision")
        build.drawing_task_id = task_id
        build.updated_at = utc_now()
        return build

    # 同时保存构建状态、阶段消息及失败详情，刷新修改时间。
    async def set_status(
        self,
        build_id: uuid.UUID,
        *,
        status: str,
        message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        build = await self._require_build(build_id)
        build.status = status
        build.status_message = message
        build.error_code = error_code
        build.error_message = error_message
        build.updated_at = utc_now()

    # 只移除内存构建记录并返回删除前对象，供上层生成响应。
    async def delete_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        del self.builds[build.id]
        return build

    # 把查询不到构建的情况转换为统一 ValueError。
    async def _require_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self.get_build(build_id)
        if build is None:
            raise ValueError(f"component build not found: {build_id}")
        return build


# 持久化构建与草稿，并提供带版本边界的原生树、属性、MBD 和识别证据查询。
class SqlAlchemyComponentBuildRepository:
    # 保存外部注入的异步数据库会话，供聚合查询和写入共用。
    def __init__(self, session: AsyncSession):
        self.session = session

    # 新增构建并提交事务，再刷新数据库生成的默认值。
    async def create_build(self, **fields) -> ComponentBuild:
        build = ComponentBuild(**fields)
        self.session.add(build)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(build)
        return build

    # 使用构建主键查询 ORM 记录，不存在时返回空值。
    async def get_build(self, build_id: uuid.UUID) -> ComponentBuild | None:
        return await self.session.get(ComponentBuild, build_id)

    # 更新指定构建字段并提交，刷新后的记录作为返回值。
    async def update_build(self, build_id: uuid.UUID, **fields) -> ComponentBuild:
        build = await self._require_build(build_id)
        for name, value in fields.items():
            setattr(build, name, value)
        await self.session.commit()
        await self.session.refresh(build)
        return build

    # 按创建时间和主键倒序读取全部构建，供目录分组投影。
    async def list_builds(self) -> list[ComponentBuild]:
        result = await self.session.execute(select(ComponentBuild).order_by(ComponentBuild.created_at.desc(), ComponentBuild.id.desc()))
        return list(result.scalars().all())

    async def list_structure_entities(self, revision_id: uuid.UUID) -> list[CadEntity]:
        """用途：为统一 Viewer 读取真实结构节点，不把 Face/Edge 等海量拓扑塞入 BOM。"""
        result = await self.session.execute(
            select(CadEntity)
            .where(
                CadEntity.revision_id == revision_id,
                CadEntity.entity_type.in_({"root", "assembly", "subassembly", "part", "imported_object", "body", "solid"}),
            )
            .order_by(CadEntity.sort_order, CadEntity.id)
        )
        return list(result.scalars().all())

    # 用版本与父节点生成父实体 UUID，只查原生前缀节点，并支持可见性过滤与分页。
    async def list_native_tree_entities(
        self,
        revision_id: uuid.UUID,
        parent_node_id: str | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
        include_supplemental: bool = True,
    ) -> list[CadEntity]:
        parent_entity_id = uuid.uuid5(revision_id, parent_node_id) if parent_node_id else None
        visibility = [] if include_supplemental else [
            func.coalesce(CadEntity.metadata_json["presentation_status"].astext, "visible") == "visible"
        ]
        result = await self.session.execute(
            select(CadEntity)
            .where(
                CadEntity.revision_id == revision_id,
                CadEntity.source_ref.like(f"{NATIVE_SOURCE_PREFIX}%"),
                CadEntity.parent_entity_id == parent_entity_id,
                *visibility,
            )
            .order_by(CadEntity.source_index.nullslast(), CadEntity.sort_order, CadEntity.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    # 只统计指定 Revision 的原生树前缀记录，排除普通解析实体。
    async def count_native_tree_entities(self, revision_id: uuid.UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(CadEntity).where(
                    CadEntity.revision_id == revision_id,
                    CadEntity.source_ref.like(f"{NATIVE_SOURCE_PREFIX}%"),
                )
            )
            or 0
        )

    # 用版本和节点 ID 定位稳定 UUID，并再次验证版本归属和原生来源前缀。
    async def get_native_tree_entity(self, revision_id: uuid.UUID, node_id: str) -> CadEntity | None:
        entity = await self.session.get(CadEntity, uuid.uuid5(revision_id, node_id))
        if entity is None or entity.revision_id != revision_id or not str(entity.source_ref or "").startswith(NATIVE_SOURCE_PREFIX):
            return None
        return entity

    async def list_native_evidence(self, revision_id: uuid.UUID, kind: str, offset: int, limit: int) -> list[dict]:
        """按 Revision、类别和原始顺序从 PostgreSQL 分页读取语义。"""
        rows = await self.session.scalars(
            select(CadNativeEvidence).where(
                CadNativeEvidence.revision_id == revision_id,
                CadNativeEvidence.kind == kind,
            ).order_by(CadNativeEvidence.ordinal).offset(offset).limit(limit)
        )
        return [row.payload for row in rows]

    # 按版本、通道和对象身份精确查询，存在重复对象时拒绝任取一条。
    async def get_native_evidence_object(self, revision_id: uuid.UUID, kind: str, object_id: str) -> dict | None:
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == kind,
            CadNativeEvidence.payload["object_id"].astext == object_id,
        ).limit(2))
        matches = list(rows)
        if len(matches) > 1:
            raise ValueError(f"duplicate {kind} identity: {object_id}")
        return matches[0].payload if matches else None

    # 只允许规范特征或测量通道，按版本及 feature_center_id 读取有序证据。
    async def get_feature_evidence_by_id(self, revision_id: uuid.UUID, kind: str,
                                         feature_center_id: str) -> list[dict]:
        if kind not in {"canonical_features", "measurements"}:
            raise ValueError("unsupported recognized feature detail kind")
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == kind,
            CadNativeEvidence.payload["feature_center_id"].astext == feature_center_id,
        ).order_by(CadNativeEvidence.ordinal))
        return [row.payload for row in rows]

    # 分页筛选指定版本的 FTA 标注；视图筛选通过真实包含关系关联，并返回匹配总数。
    async def list_mbd_annotations(self, revision_id: uuid.UUID, *, offset: int, limit: int,
                                   annotation_kind: str | None = None, set_id: str | None = None,
                                   view_id: str | None = None,
                                   read_status: str | None = None, search: str | None = None) -> tuple[list[dict], int]:
        filters = [CadNativeEvidence.revision_id == revision_id,
                   CadNativeEvidence.kind == "fta_semantics"]
        payload = CadNativeEvidence.payload
        if annotation_kind:
            filters.append(payload["component_kind"].astext == annotation_kind)
        if set_id:
            filters.append(payload["fta_set_id"].astext == set_id)
        if view_id:
            relation = aliased(CadNativeEvidence)
            filters.append(exists(select(1).select_from(relation).where(
                relation.revision_id == revision_id,
                relation.kind == "pmi_associations",
                relation.payload["pmi_id"].astext == view_id,
                relation.payload["target_id"].astext == payload["fta_semantic_id"].astext,
                relation.payload["association_kind"].astext.in_(("view_contains_annotation", "capture_contains_annotation")),
            )))
        if read_status:
            filters.append(payload["read_status"].astext == read_status)
        if search:
            needle = f"%{search}%"
            filters.append(or_(payload["fta_semantic_id"].astext.ilike(needle),
                               payload["annotation_text"].astext.ilike(needle),
                               payload["native_alias"].astext.ilike(needle),
                               payload["semantic_payload"]["native_alias"].astext.ilike(needle)))
        total = int(await self.session.scalar(select(func.count()).select_from(CadNativeEvidence).where(*filters)) or 0)
        rows = await self.session.scalars(select(CadNativeEvidence).where(*filters)
                                          .order_by(CadNativeEvidence.ordinal).offset(offset).limit(limit))
        return [row.payload for row in rows], total

    # 按版本及标注身份最多读取两条，供服务层识别重复身份。
    async def get_mbd_annotation(self, revision_id: uuid.UUID, annotation_id: str) -> list[dict]:
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "fta_semantics",
            CadNativeEvidence.payload["fta_semantic_id"].astext == annotation_id,
        ).order_by(CadNativeEvidence.ordinal).limit(2))
        return [row.payload for row in rows]

    # 按版本及 PMI 节点身份最多读取两条，供服务层校验唯一性。
    async def get_mbd_node(self, revision_id: uuid.UUID, pmi_id: str) -> list[dict]:
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "pmi_entities",
            CadNativeEvidence.payload["pmi_id"].astext == pmi_id,
        ).order_by(CadNativeEvidence.ordinal).limit(2))
        return [row.payload for row in rows]

    # 读取指定版本中以该身份为任一端点的所有 PMI 关系。
    async def list_mbd_relations(self, revision_id: uuid.UUID, endpoint_id: str) -> list[dict]:
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "pmi_associations",
            or_(CadNativeEvidence.payload["pmi_id"].astext == endpoint_id,
                CadNativeEvidence.payload["target_id"].astext == endpoint_id),
        ).order_by(CadNativeEvidence.ordinal))
        return [row.payload for row in rows]

    # 按定义级 object_id 读取当前版本原生语义，树实例共用同一对象证据。
    async def get_native_feature(self, revision_id: uuid.UUID, object_id: str) -> dict | None:
        """Read one definition-level semantic fact for a selected tree occurrence."""
        row = await self.session.scalar(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "native_features",
            CadNativeEvidence.payload["object_id"].astext == object_id,
        ).order_by(CadNativeEvidence.ordinal).limit(1))
        return row.payload if row else None

    async def list_native_dependency_candidates(self, revision_id: uuid.UUID, object_id: str) -> list[dict]:
        """在数据库端筛选选中对象的依赖关系，不把整包依赖传回每次点击。"""
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "feature_dependencies",
            or_(CadNativeEvidence.payload["from_object_id"].astext == object_id,
                CadNativeEvidence.payload["object_id"].astext == object_id),
        ).order_by(CadNativeEvidence.ordinal))
        return [row.payload for row in rows]

    # 按版本和主体集合读取属性，可仅筛参数显示值以减少树查询负担。
    async def list_native_property_facts(
        self, revision_id: uuid.UUID, subject_ids: set[str], *, parameter_values_only: bool = False
    ) -> list[CadNativePropertyFact]:
        if not subject_ids:
            return []
        result = await self.session.execute(
            select(CadNativePropertyFact)
            .where(
                CadNativePropertyFact.revision_id == revision_id,
                CadNativePropertyFact.subject_id.in_(subject_ids),
                *([CadNativePropertyFact.payload["key"].astext == "catia_parameter_value_text"]
                  if parameter_values_only else []),
            )
            .order_by(CadNativePropertyFact.sort_order, CadNativePropertyFact.id)
        )
        return list(result.scalars().all())

    # 读取现有业务编号并计算指定前缀下的下一序号。
    async def next_component_id(self, prefix: str) -> str:
        result = await self.session.execute(select(ComponentBuild.component_id))
        return _next_component_id(prefix, result.scalars().all())

    # 验证构建存在后按其主键读取规范草稿，未保存时返回空值。
    async def get_component_spec(self, build_id: uuid.UUID) -> ComponentSpecDraft | None:
        await self._require_build(build_id)
        return await self.session.get(ComponentSpecDraft, build_id)

    # 新建或替换构建对应的版本 1.2 草稿，并提交后刷新记录。
    async def save_component_spec(self, build_id: uuid.UUID, data: dict) -> ComponentSpecDraft:
        await self._require_build(build_id)
        draft = await self.session.get(ComponentSpecDraft, build_id)
        if draft is None:
            draft = ComponentSpecDraft(build_id=build_id, schema_version="1.2", data=data)
            self.session.add(draft)
        else:
            draft.data = data
            draft.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(draft)
        return draft

    # 校验 Revision 属于所给模型；切换版本时清空旧图纸任务，再提交关联。
    async def attach_step(self, build_id: uuid.UUID, *, model_id: uuid.UUID, revision_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        revision = await self.session.get(CadModelRevision, revision_id)
        if revision is None or revision.model_id != model_id:
            raise ValueError("revision does not belong to model")
        # 图纸事实绑定具体 Revision，切换模型版本后必须解除旧图纸关联。
        if build.cad_revision_id != revision_id:
            build.drawing_task_id = None
        build.cad_model_id = model_id
        build.cad_revision_id = revision_id
        await self.session.commit()
        await self.session.refresh(build)
        return build

    # 校验图纸任务与构建的当前 Revision 一致，再提交图纸关联。
    async def attach_drawing(self, build_id: uuid.UUID, *, task_id: uuid.UUID) -> ComponentBuild:
        build = await self._require_build(build_id)
        task = await self.session.get(CadSpecTask, task_id)
        if build.cad_revision_id is None or task is None or task.revision_id != build.cad_revision_id:
            raise ValueError("drawing task does not belong to build revision")
        build.drawing_task_id = task_id
        await self.session.commit()
        await self.session.refresh(build)
        return build

    # 持久化构建状态和错误详情；具体来源处理进度由各自任务维护。
    async def set_status(
        self,
        build_id: uuid.UUID,
        *,
        status: str,
        message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        build = await self._require_build(build_id)
        build.status = status
        build.status_message = message
        build.error_code = error_code
        build.error_message = error_message
        await self.session.commit()

    # 提交构建记录删除并返回删除前对象；文件清理由服务层执行。
    async def delete_build(self, build_id: uuid.UUID) -> ComponentBuild:
        """Delete a component build record. Returns the build before deletion."""
        build = await self._require_build(build_id)
        await self.session.delete(build)
        await self.session.commit()
        return build

    # 用途：为 service.delete_build 提供资源清理所需的查询方法。

    # 读取图纸任务源文件位置，供删除流程清理落盘文件。
    async def list_drawing_sources(self, task_id: uuid.UUID) -> list[dict]:
        result = await self.session.execute(
            select(CadSpecSource).where(CadSpecSource.task_id == task_id)
        )
        rows = result.scalars().all()
        return [{"id": str(r.id), "file_path": r.file_path, "file_name": r.file_name} for r in rows]

    # 读取图纸区域的裁剪文件路径，供删除流程逐个清理。
    async def list_drawing_regions(self, task_id: uuid.UUID) -> list[dict]:
        result = await self.session.execute(
            select(CadDrawingRegion).where(CadDrawingRegion.task_id == task_id)
        )
        rows = result.scalars().all()
        return [{"id": str(r.id), "crop_file_path": r.crop_file_path} for r in rows]

    # 按主键返回完整模型版本对象，供清单投影与资源清理使用。
    async def get_raw_revision(self, revision_id: uuid.UUID) -> CadModelRevision | None:
        return await self.session.get(CadModelRevision, revision_id)

    # 查询共享同一 CAD 模型的构建，可排除当前构建以判断模型能否删除。
    async def list_builds_by_model(self, model_id: uuid.UUID, *, exclude_build_id: uuid.UUID | None = None) -> list[ComponentBuild]:
        stmt = select(ComponentBuild).where(ComponentBuild.cad_model_id == model_id)
        if exclude_build_id:
            stmt = stmt.where(ComponentBuild.id != exclude_build_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # 统一拒绝对不存在构建执行更新、关联或删除。
    async def _require_build(self, build_id: uuid.UUID) -> ComponentBuild:
        build = await self.get_build(build_id)
        if build is None:
            raise ValueError(f"component build not found: {build_id}")
        return build


# 只匹配当前前缀加数字的编号，以最大序号加一生成至少三位的新编号。
def _next_component_id(prefix: str, component_ids) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    sequence = 0
    for component_id in component_ids:
        match = pattern.match(component_id)
        if match:
            sequence = max(sequence, int(match.group(1)))
    return f"{prefix}-{sequence + 1:03d}"
