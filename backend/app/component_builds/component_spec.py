from __future__ import annotations

from copy import deepcopy
from io import StringIO
from pathlib import Path
import re
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString


TEMPLATE_PATH = Path(__file__).with_name("component-spec-v1.2-template.yaml")
SECTION_LABELS = {
    "schema_version": ("规范信息", "ComponentSpec 的版本与对象类型"),
    "identity": ("身份与版本", "图元身份、分类、标准及维护信息"),
    "coordinate_system": ("坐标系与建模基准", "局部坐标系、原点与轴向定义"),
    "parameters": ("参数定义", "可输入或由预设赋值的参数"),
    "derived_parameters": ("派生参数", "通过表达式计算的只读参数"),
    "constraints": ("参数约束", "参数之间的逻辑和尺寸约束"),
    "ports": ("装配接口", "图元对外连接端口与兼容关系"),
    "geometry": ("参数化几何生成", "建模引擎、生成步骤及导出配置"),
    "presets": ("预设规格", "标准或常用参数组合"),
    "validation": ("生成结果验证", "参数、拓扑、几何及发布校验"),
    "artifacts": ("交付文件与完整性", "基准模型、源文件、预览及缩略图"),
    "provenance": ("数据来源与审计", "标准引用、录入方式和核验记录"),
}
SECTION_NUMBERS = {
    "identity": "1",
    "coordinate_system": "2",
    "parameters": "3",
    "derived_parameters": "3",
    "constraints": "4",
    "ports": "5",
    "geometry": "6",
    "presets": "7",
    "validation": "8",
    "artifacts": "9",
    "provenance": "10",
}


def _comment_for(mapping: CommentedMap, key: str) -> str:
    parts = mapping.ca.items.get(key)
    if not parts or not parts[2]:
        return ""
    return parts[2].value.lstrip("#").strip()


def _annotation(comment: str, fallback: str) -> dict:
    required = "【必填】" in comment
    read_only = "（系统固定）" in comment
    source_match = re.search(r"（([^）]+)）", comment)
    source = source_match.group(1) if source_match else ""
    label = re.sub(r"【必填】|\[选填\]", "", comment)
    label = re.sub(r"^（[^）]+）\s*", "", label).strip()
    return {
        "label": label or fallback,
        "required": required,
        "read_only": read_only,
        "source": source,
        "comment": comment,
    }


def _value_type(values: list[Any]) -> str:
    value = next((item for item in values if item is not None), None)
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "text"


def _mapping_fields(mappings: list[CommentedMap], parent_path: str) -> list[dict]:
    keys: list[str] = []
    for mapping in mappings:
        for key in mapping:
            if key not in keys:
                keys.append(key)

    fields = []
    for key in keys:
        owners = [mapping for mapping in mappings if key in mapping]
        values = [mapping[key] for mapping in owners]
        comment = next((_comment_for(owner, key) for owner in owners if _comment_for(owner, key)), "")
        path = f"{parent_path}.{key}" if parent_path else str(key)
        fields.append(_field_schema(str(key), values, path, comment))
    return fields


def _field_schema(key: str, values: list[Any], path: str, comment: str) -> dict:
    field = {
        "key": key,
        "path": path,
        **_annotation(comment, key),
    }
    non_null = [value for value in values if value is not None]
    sample = non_null[0] if non_null else None

    if isinstance(sample, CommentedMap):
        mappings = [value for value in non_null if isinstance(value, CommentedMap)]
        field.update(kind="object", children=_mapping_fields(mappings, path))
        return field

    if isinstance(sample, (CommentedSeq, list)):
        sequences = [value for value in non_null if isinstance(value, (CommentedSeq, list))]
        items = [item for sequence in sequences for item in sequence]
        object_items = [item for item in items if isinstance(item, CommentedMap)]
        if object_items:
            field.update(
                kind="object_array",
                repeatable=True,
                item={
                    "kind": "object",
                    "children": _mapping_fields(object_items, f"{path}[]"),
                },
            )
        else:
            field.update(
                kind="scalar_array",
                repeatable=False,
                value_type=_value_type(items),
            )
        return field

    field.update(kind=_value_type(values), fixed_value=deepcopy(sample) if field["read_only"] else None)
    return field


def _blank_value(field: dict) -> Any:
    if field["read_only"]:
        return deepcopy(field.get("fixed_value"))
    if field["kind"] == "object":
        return {child["key"]: _blank_value(child) for child in field["children"]}
    if field["kind"] == "object_array":
        return [{child["key"]: _blank_value(child) for child in field["item"]["children"]}]
    if field["kind"] == "scalar_array":
        return []
    return None


def _normalize_value(field: dict, value: Any) -> Any:
    if field["read_only"]:
        return deepcopy(field.get("fixed_value"))
    if field["kind"] == "object":
        source = value if isinstance(value, dict) else {}
        normalized = {
            child["key"]: _normalize_value(child, source.get(child["key"]))
            for child in field["children"]
        }
        normalized.update({key: deepcopy(item) for key, item in source.items() if key not in normalized})
        return normalized
    if field["kind"] == "object_array":
        source = value if isinstance(value, list) else []
        normalized_items = []
        for item in source:
            item_source = item if isinstance(item, dict) else {}
            normalized = {
                child["key"]: _normalize_value(child, item.get(child["key"]) if isinstance(item, dict) else None)
                for child in field["item"]["children"]
            }
            normalized.update({key: deepcopy(entry) for key, entry in item_source.items() if key not in normalized})
            normalized_items.append(normalized)
        return normalized_items
    if field["kind"] == "scalar_array":
        return value if isinstance(value, list) else []
    return value


def _quoted(value: Any) -> Any:
    if isinstance(value, str):
        return DoubleQuotedScalarString(value)
    if isinstance(value, list):
        return CommentedSeq([_quoted(item) for item in value])
    return value


def _render_field(field: dict, value: Any) -> Any:
    if field["kind"] == "object":
        return _render_mapping(field["children"], value if isinstance(value, dict) else {})
    if field["kind"] == "object_array":
        sequence = CommentedSeq()
        for item in value if isinstance(value, list) else []:
            sequence.append(_render_mapping(field["item"]["children"], item if isinstance(item, dict) else {}))
        return sequence
    if field["kind"] == "scalar_array":
        return _quoted(value if isinstance(value, list) else [])
    return _quoted(value)


def _render_mapping(fields: list[dict], data: dict) -> CommentedMap:
    mapping = CommentedMap()
    for field in fields:
        key = field["key"]
        mapping[key] = _render_field(field, data.get(key))
        if field["comment"]:
            mapping.yaml_add_eol_comment(field["comment"], key=key)
    for key, value in data.items():
        if key not in mapping:
            mapping[key] = deepcopy(value)
    return mapping


class ComponentSpecTemplate:
    def __init__(self, template_path: Path = TEMPLATE_PATH):
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        with template_path.open(encoding="utf-8") as stream:
            template = yaml.load(stream)

        top_fields = _mapping_fields([template], "")
        sections: list[dict] = []
        base_fields = [field for field in top_fields if field["key"] in {"schema_version", "spec_type"}]
        sections.append(
            {
                "key": "spec",
                "label": SECTION_LABELS["schema_version"][0],
                "description": SECTION_LABELS["schema_version"][1],
                "fields": base_fields,
            }
        )
        for field in top_fields:
            if field["key"] in {"schema_version", "spec_type"}:
                continue
            if field["key"] == "derived_parameters":
                parameter_section = next(section for section in sections if section["key"] == "parameters")
                parameter_section["fields"].append(field)
                continue
            label, description = SECTION_LABELS.get(field["key"], (field["label"], field["label"]))
            sections.append(
                {
                    "key": field["key"],
                    "label": label,
                    "description": description,
                    "fields": [field],
                }
            )
        self.schema = {"schema_version": "1.2", "sections": sections}

    def blank_data(self) -> dict:
        return {
            field["key"]: _blank_value(field)
            for section in self.schema["sections"]
            for field in section["fields"]
        }

    def normalize(self, data: dict) -> dict:
        source = data if isinstance(data, dict) else {}
        normalized = {
            field["key"]: _normalize_value(field, source.get(field["key"]))
            for section in self.schema["sections"]
            for field in section["fields"]
        }
        normalized.update({key: deepcopy(value) for key, value in source.items() if key not in normalized})
        return normalized

    def render_yaml(self, data: dict) -> str:
        normalized = self.normalize(data)
        root = CommentedMap()
        for section in self.schema["sections"]:
            for index, field in enumerate(section["fields"]):
                key = field["key"]
                root[key] = _render_field(field, normalized.get(key))
                if field["comment"]:
                    root.yaml_add_eol_comment(field["comment"], key=key)
                if index == 0 and section["key"] != "spec":
                    number = SECTION_NUMBERS.get(section["key"])
                    heading = f"{number}. {section['label']}" if number else section["label"]
                    root.yaml_set_comment_before_after_key(key, before=f"\n── {heading} ──")
        for key, value in normalized.items():
            if key not in root:
                root[key] = deepcopy(value)

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        output = StringIO()
        yaml.dump(root, output)
        return output.getvalue()


component_spec_template = ComponentSpecTemplate()
