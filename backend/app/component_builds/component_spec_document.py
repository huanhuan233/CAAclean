# 将规范数据、原始 YAML 和来源文件名封装保存，并验证两种表达的内容一致。
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from numbers import Real
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


DOCUMENT_FORMAT = "component_spec_document_v1"


# 表示规范文档结构或 YAML 与结构化数据的一致性校验失败。
class ComponentSpecDocumentError(ValueError):
    """Raised when a ComponentSpec YAML document cannot be safely persisted."""


# 同时携带结构化内容、原始 YAML、来源文件名和是否采用新封装的标记。
@dataclass(frozen=True)
class ComponentSpecDocument:
    data: dict[str, Any]
    yaml: str | None
    source_filename: str | None
    is_envelope: bool


# 识别版本封装；旧裸字典直接作为数据读取，新封装必须含映射类型 data。
def unpack_component_spec_document(stored: dict[str, Any]) -> ComponentSpecDocument:
    if stored.get("__format__") != DOCUMENT_FORMAT:
        return ComponentSpecDocument(
            data=stored,
            yaml=None,
            source_filename=None,
            is_envelope=False,
        )
    data = stored.get("data")
    if not isinstance(data, dict):
        raise ComponentSpecDocumentError("Stored ComponentSpec document data must be a mapping")
    yaml_text = stored.get("yaml")
    source_filename = stored.get("source_filename")
    return ComponentSpecDocument(
        data=data,
        yaml=yaml_text if isinstance(yaml_text, str) else None,
        source_filename=source_filename if isinstance(source_filename, str) else None,
        is_envelope=True,
    )


# 将数据与原始文本绑定在版本化封装中，便于后续保留导入文件格式。
def pack_component_spec_document(
    data: dict[str, Any],
    yaml_text: str,
    source_filename: str | None = None,
) -> dict[str, Any]:
    return {
        "__format__": DOCUMENT_FORMAT,
        "data": data,
        "yaml": yaml_text,
        "source_filename": source_filename,
    }


# 递归转为 JSON 可存储值，日期转 ISO 文本，保留布尔与数值类型区别。
def _json_compatible(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return str(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    return value


# 递归比较结构与值；允许整数和浮点等值，但禁止布尔值冒充数字。
def _strictly_equivalent(left: Any, right: Any) -> bool:
    # Python 中 True == 1，但规范文档必须区分布尔与数值，避免保存时悄悄改语义。
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, Real) and isinstance(right, Real):
        return float(left) == float(right)
    if isinstance(left, dict) and isinstance(right, dict):
        return (
            left.keys() == right.keys()
            and all(_strictly_equivalent(left[key], right[key]) for key in left)
        )
    if isinstance(left, list) and isinstance(right, list):
        return (
            len(left) == len(right)
            and all(_strictly_equivalent(a, b) for a, b in zip(left, right))
        )
    return type(left) is type(right) and left == right


# 安全解析 YAML、给出错误行列，并拒绝与提交数据不一致的文本。
def validate_component_spec_yaml(yaml_text: str, expected_data: dict[str, Any]) -> dict[str, Any]:
    parser = YAML(typ="safe")
    try:
        parsed = parser.load(yaml_text)
    except YAMLError as exc:
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ComponentSpecDocumentError(f"Invalid YAML{location}: {problem}") from exc

    if not isinstance(parsed, dict):
        raise ComponentSpecDocumentError("ComponentSpec YAML root must be a mapping")
    parsed = _json_compatible(parsed)
    if not _strictly_equivalent(parsed, _json_compatible(expected_data)):
        raise ComponentSpecDocumentError("ComponentSpec YAML does not match submitted data")
    return parsed
