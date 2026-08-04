"""扩展属性邻接图的内存查询与引用校验。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class EaagGraph:
    """为 Hole 映射和后续复杂结构探针提供统一图查询，不依赖 Face 序号。"""

    # 用途：建立实体、出边、入边和曲面类型索引；输入列表不会被修改。
    def __init__(self, entities: list[dict[str, Any]], relations: list[dict[str, Any]]) -> None:
        self.entities = {item["entity_id"]: item for item in entities}
        self.relations = list(relations)
        self._outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._surface_faces: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relation in self.relations:
            self._outgoing[relation["source_entity_id"]].append(relation)
            self._incoming[relation["target_entity_id"]].append(relation)
        for entity in self.entities.values():
            if entity.get("entity_type") == "face":
                self._surface_faces[str(entity.get("geometry_type", "other"))].append(entity)
        for faces in self._surface_faces.values():
            faces.sort(key=lambda item: item["entity_id"])

    # 用途：按真实 Kernel 曲面类别返回稳定排序的 Face 节点。
    def faces_by_surface(self, surface_type: str) -> list[dict[str, Any]]:
        return list(self._surface_faces.get(surface_type, []))

    # 用途：返回指定面的双向邻接面编号，并自动去重。
    def face_neighbors(self, face_id: str) -> list[str]:
        result: set[str] = set()
        for relation in self._outgoing.get(face_id, []):
            if relation["relation_type"] == "adjacent_to":
                result.add(relation["target_entity_id"])
        for relation in self._incoming.get(face_id, []):
            if relation["relation_type"] == "adjacent_to":
                result.add(relation["source_entity_id"])
        return sorted(result)

    # 用途：通过两面共同的 bounded_by_edge 关系返回共享边，不依赖边序号。
    def shared_edge_ids(self, left_face_id: str, right_face_id: str) -> list[str]:
        def bounded_edges(face_id: str) -> set[str]:
            return {
                relation["target_entity_id"]
                for relation in self._outgoing.get(face_id, [])
                if relation["relation_type"] == "bounded_by_edge"
            }
        return sorted(bounded_edges(left_face_id).intersection(bounded_edges(right_face_id)))

    # 用途：返回归属于指定面的 Wire/Loop 编号，供开口环和岛屿拓扑继续分析。
    def wire_ids(self, face_id: str) -> list[str]:
        return sorted(
            relation["target_entity_id"]
            for relation in self._outgoing.get(face_id, [])
            if relation["relation_type"] == "has_wire"
        )

    # 用途：检查每条关系的起终点均存在；返回问题列表而不是静默丢弃正式 Bundle。
    def validate_references(self) -> list[str]:
        errors: list[str] = []
        for relation in self.relations:
            if relation["source_entity_id"] not in self.entities:
                errors.append(f"missing source:{relation['relation_id']}")
            if relation["target_entity_id"] not in self.entities:
                errors.append(f"missing target:{relation['relation_id']}")
        return errors
