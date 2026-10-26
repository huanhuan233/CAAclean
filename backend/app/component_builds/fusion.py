# 把构建身份、图纸事实和模型测量融合为规范草稿，并逐字段报告来源、保留决定和待复核项。
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


# 表示没有可供融合的图纸、测量、特征或模型版本数据。
class FusionSourceUnavailable(ValueError):
    pass


# 保存同一构建关联的图纸事实、测量、识别特征和版本元数据。
@dataclass(frozen=True)
class FusionSources:
    drawing_facts: list[dict]
    measurements: list[dict]
    features: list[dict]
    revision: dict | None = None

    # 任一来源非空即可启动融合；不要求每条来源通道均成功。
    @property
    def available(self) -> bool:
        return bool(self.drawing_facts or self.measurements or self.features or self.revision)


# 返回融合后的草稿、字段决策统计、来源明细及无法确定的业务警告。
@dataclass(frozen=True)
class FusionResult:
    data: dict
    summary: dict[str, int]
    fields: list[dict]
    warnings: list[str]


FLANGE_SYMBOL_MAP = {
    "D": ("flange_outer_diameter", "法兰外径", "float", False),
    "K": ("bolt_circle_diameter", "螺栓孔中心圆直径", "float", False),
    "n": ("bolt_hole_count", "螺栓孔数量", "integer", False),
    "L": ("bolt_hole_diameter", "螺栓孔直径", "float", False),
    "C": ("flange_thickness", "法兰厚度", "float", False),
    "A1": ("pipe_outer_diameter", "配管外径", "float", False),
    "S": ("wall_thickness", "配管壁厚", "float", True),
    "N": ("hub_small_end_diameter", "颈部小端直径", "float", True),
    "H1": ("hub_height", "颈部高度", "float", True),
    "H": ("overall_height", "法兰总高度", "float", False),
    "d": ("raised_face_diameter", "突面直径", "float", False),
    "f1": ("raised_face_height", "突面高度", "float", False),
    "R": ("root_fillet_radius", "颈部根圆角半径", "float", False),
}


# 深拷贝现有草稿并补身份与来源；法兰按目标 DN 行回填，默认保留已填写值。
def fuse_component_spec(
    *,
    build: dict,
    current: dict,
    sources: FusionSources,
    overwrite: bool = False,
) -> FusionResult:
    data = deepcopy(current)
    fields: list[dict] = []
    warnings: list[str] = []

    # 对点分路径执行补空或覆盖，并记录来源、置信度和待复核标记。
    def assign(
        path: str,
        value: Any,
        *,
        source: str,
        confidence: float = 1.0,
        needs_review: bool = False,
    ) -> None:
        if value is None:
            return
        existing = _get_path(data, path)
        # 默认补空策略保留用户已有值；字段报告仍记录本次候选的来源与保留决定。
        if not overwrite and not _is_empty(existing):
            _record(fields, path, existing, source, confidence, "preserved", needs_review)
            return
        _set_path(data, path, value)
        _record(fields, path, value, source, confidence, "filled", needs_review)

    product = {
        fact.get("fact_key"): fact
        for fact in sources.drawing_facts
        if fact.get("fact_type") != "dimension" and fact.get("fact_key")
    }
    standard_number = build.get("standard_number") or _fact_value(product.get("product.standard_number"))
    subtype_raw = _fact_value(product.get("product.component_type_raw"))

    assign("identity.id", build.get("component_id"), source="build")
    assign("identity.name", build.get("component_name"), source="build")
    assign("identity.type", build.get("component_type"), source="build")
    assign("identity.family", build.get("family"), source="build")
    assign("identity.version", build.get("version") or "1.0.0", source="build")
    assign("identity.status", "draft", source="derived")
    assign("identity.standard.number", standard_number, source="build" if build.get("standard_number") else "drawing")
    assign("identity.standard.edition", _standard_edition(standard_number), source="derived")
    _fuse_revision_metadata(assign, sources.revision)
    if sources.drawing_facts and sources.revision:
        assign("provenance.source_type", "drawing_and_step", source="derived", needs_review=True)
    elif sources.drawing_facts:
        assign("provenance.source_type", "drawing", source="derived", needs_review=True)
    elif sources.revision:
        assign("provenance.source_type", "step", source="derived", needs_review=True)
    assign("provenance.data_entry_method", "automatic_fusion", source="derived")
    if build.get("component_type") == "flange" and subtype_raw and "带颈对焊" in str(subtype_raw):
        assign("identity.subtype", "weld_neck", source="drawing", confidence=0.9)
        assign("identity.name_en", "Weld Neck Flange", source="derived", confidence=0.8, needs_review=True)

    target_dn = _resolve_target_dn(data, build)
    if target_dn is None:
        if any(fact.get("fact_type") == "dimension" for fact in sources.drawing_facts):
            warnings.append("target_dn_unresolved")
    elif build.get("component_type") == "flange":
        _fuse_flange(
            data=data,
            fields=fields,
            warnings=warnings,
            build=build,
            product=product,
            sources=sources,
            target_dn=target_dn,
            overwrite=overwrite,
        )
        if _get_parameter(data, "bolt_hole_count") is not None:
            assign(
                "validation.geometry.expected_through_hole_count_expression",
                "bolt_hole_count",
                source="derived",
            )

    summary = {
        "filled": sum(item["decision"] == "filled" for item in fields),
        "preserved": sum(item["decision"] == "preserved" for item in fields),
        "conflicts": sum(item["decision"] == "conflict" for item in fields),
        "needs_review": sum(bool(item["needs_review"]) for item in fields),
    }
    return FusionResult(data=data, summary=summary, fields=fields, warnings=warnings)


# 从模型版本回填实体数量与参考 STEP 信息，记录文件摘要及长度单位。
def _fuse_revision_metadata(assign, revision: dict | None) -> None:
    if not revision:
        return

    solid_count = revision.get("solid_count")
    if isinstance(solid_count, int) and solid_count > 0:
        assign(
            "validation.topology.expected_body_count",
            solid_count,
            source="step",
        )
        assign(
            "validation.topology.solid_required",
            True,
            source="step",
        )

    assign(
        "artifacts.reference_step.file",
        revision.get("source_file_name"),
        source="step",
    )
    assign(
        "artifacts.reference_step.role",
        "默认预设的几何回归基准",
        source="derived",
    )
    assign("artifacts.reference_step.format", "STEP", source="derived")
    assign(
        "artifacts.reference_step.application_protocol",
        "AP242",
        source="system",
    )
    assign(
        "artifacts.reference_step.length_unit",
        revision.get("unit") or "mm",
        source="step",
    )
    assign(
        "artifacts.reference_step.sha256",
        revision.get("source_sha256"),
        source="step",
    )


# 按目标 DN 选择图纸尺寸行，生成法兰参数与预设；推导内孔须有模型测量佐证。
def _fuse_flange(
    *,
    data: dict,
    fields: list[dict],
    warnings: list[str],
    build: dict,
    product: dict[str, dict],
    sources: FusionSources,
    target_dn: int,
    overwrite: bool,
) -> None:
    row = {
        str(fact.get("symbol")): fact
        for fact in sources.drawing_facts
        if fact.get("fact_type") == "dimension" and _row_dn(fact) == target_dn and fact.get("symbol")
    }
    if not row:
        warnings.append("target_dn_row_missing")
        return

    pn = _parse_number(_fact_value(product.get("product.pressure_class")))
    _upsert_parameter(data, fields, "DN", target_dn, label="公称尺寸", value_type="integer", unit=None, source="derived", overwrite=overwrite)
    if pn is not None:
        _upsert_parameter(data, fields, "PN", int(pn), label="公称压力等级", value_type="integer", unit=None, source="drawing", confidence=0.9, overwrite=overwrite)

    for symbol, (name, label, value_type, mapping_review) in FLANGE_SYMBOL_MAP.items():
        fact = row.get(symbol)
        if not fact:
            continue
        value = _fact_value(fact)
        if value_type == "integer" and isinstance(value, (int, float)):
            value = int(value)
        needs_review = mapping_review or fact.get("operator") not in {None, "eq", "categorical"}
        _upsert_parameter(
            data,
            fields,
            name,
            value,
            label=label,
            value_type=value_type,
            unit=None if value_type == "integer" else fact.get("unit"),
            source="drawing",
            confidence=float(fact.get("confidence") or 0),
            needs_review=needs_review,
            standard_symbol=symbol,
            overwrite=overwrite,
        )

    facing = _normalize_facing(_fact_value(product.get("product.facing_type")))
    if facing:
        _upsert_parameter(
            data,
            fields,
            "facing_type",
            facing,
            label="密封面形式",
            value_type="string",
            unit=None,
            source="drawing",
            confidence=0.9,
            overwrite=overwrite,
        )

    pipe_od = _numeric_fact(row.get("A1"))
    wall = _numeric_fact(row.get("S"))
    if pipe_od is not None and wall is not None:
        bore = round(pipe_od - 2 * wall, 6)
        # 外径减两倍壁厚仅是推导候选，必须在模型直径测量中得到佐证才回填。
        if _measurement_confirms(sources.measurements, bore):
            _upsert_parameter(
                data,
                fields,
                "bore_diameter",
                bore,
                label="内孔直径",
                value_type="float",
                unit="mm",
                source="derived",
                confidence=0.85,
                overwrite=overwrite,
            )
        else:
            warnings.append("bore_diameter_unconfirmed")

    preset_name = f"DN{target_dn}-PN{int(pn)}" if pn is not None else f"DN{target_dn}"
    _assign_simple(data, fields, "identity.default_preset", preset_name, "derived", 1.0, False, overwrite)
    _upsert_preset(data, fields, preset_name, build.get("standard_number"), overwrite=overwrite)
    preset = next(
        item
        for item in data["presets"]
        if isinstance(item, dict) and item.get("name") == preset_name
    )
    for parameter in data.get("parameters", []):
        if not isinstance(parameter, dict):
            continue
        name = parameter.get("name")
        if name and not _is_empty(parameter.get("default")):
            _assign_simple(
                preset,
                fields,
                f"params.{name}",
                parameter["default"],
                "derived",
                1.0,
                False,
                overwrite,
                report_path=f"presets.{preset_name}.params.{name}",
            )


# 按参数名创建或更新规格定义，再依据覆盖开关写默认值和字段报告。
def _upsert_parameter(
    data: dict,
    fields: list[dict],
    name: str,
    value: Any,
    *,
    label: str,
    value_type: str,
    unit: str | None,
    source: str,
    confidence: float = 1.0,
    needs_review: bool = False,
    standard_symbol: str | None = None,
    overwrite: bool,
) -> None:
    parameters = data.setdefault("parameters", [])
    parameter = next(
        (
            item
            for item in parameters
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )
    if parameter is None:
        parameter = {
            "name": name,
            "label": label,
            "type": value_type,
            "unit": unit,
            "default": None,
            "enum": [],
            "required": True,
            "editable": name in {"DN", "PN", "wall_thickness", "facing_type"},
            "affects_geometry": True,
            "standard_symbol": standard_symbol,
            "min": None,
            "max": None,
        }
        parameters.append(parameter)
    elif overwrite:
        parameter.update(
            {
                "label": label,
                "type": value_type,
                "unit": unit,
                "required": True,
                "editable": name in {"DN", "PN", "wall_thickness", "facing_type"},
                "affects_geometry": True,
                "standard_symbol": standard_symbol,
            }
        )
    _assign_simple(
        parameter,
        fields,
        "default",
        value,
        source,
        confidence,
        needs_review,
        overwrite,
        report_path=f"parameters.{name}.default",
    )


# 按预设名补建待复核规格组合，并记录其标准来源。
def _upsert_preset(data: dict, fields: list[dict], name: str, source_ref: str | None, *, overwrite: bool) -> None:
    presets = data.setdefault("presets", [])
    preset = next(
        (
            item
            for item in presets
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )
    if preset is None:
        preset = {"name": name, "source_ref": None, "verification_status": "needs_review", "params": {}}
        presets.append(preset)
    _assign_simple(
        preset,
        fields,
        "source_ref",
        source_ref,
        "build",
        1.0,
        False,
        overwrite,
        report_path=f"presets.{name}.source_ref",
    )


# 按参数业务名称检索字典条目，忽略不合法的列表成员。
def _get_parameter(data: dict, name: str) -> dict | None:
    return next(
        (
            item
            for item in data.get("parameters", [])
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )


# 统一处理单字段补空、覆盖和保留决策，并允许指定独立报告路径。
def _assign_simple(
    root: dict,
    fields: list[dict],
    path: str,
    value: Any,
    source: str,
    confidence: float,
    needs_review: bool,
    overwrite: bool,
    *,
    report_path: str | None = None,
) -> None:
    if value is None:
        return
    current = _get_path(root, path)
    decision = "filled"
    if not overwrite and not _is_empty(current):
        value = current
        decision = "preserved"
    else:
        _set_path(root, path, value)
    _record(fields, report_path or path, value, source, confidence, decision, needs_review)


# 优先取草稿 DN 默认值，其次解析构件名称，最后使用构建默认 DN。
def _resolve_target_dn(data: dict, build: dict) -> int | None:
    existing = next(
        (
            item.get("default")
            for item in data.get("parameters", [])
            if isinstance(item, dict) and item.get("name") == "DN"
        ),
        None,
    )
    if isinstance(existing, (int, float)):
        return int(existing)
    match = re.search(r"(?:^|[-_\s])DN\s*(\d+)(?:$|[-_\s])", str(build.get("component_name") or ""), re.IGNORECASE)
    if match:
        return int(match.group(1))
    default_dn = build.get("default_dn")
    return int(default_dn) if isinstance(default_dn, (int, float)) else None


# 读取图纸事实元数据中的行公称尺寸，只接受数值类型。
def _row_dn(fact: dict) -> int | None:
    value = (fact.get("metadata") or {}).get("row_dn")
    return int(value) if isinstance(value, (int, float)) else None


# 仅用圆或圆柱直径测量验证推导值，允许 0.1 的绝对偏差。
def _measurement_confirms(measurements: list[dict], expected: float) -> bool:
    for measurement in measurements:
        if measurement.get("measurement_type") not in {"circle_diameter", "cylinder_diameter"}:
            continue
        value = measurement.get("normalized_value")
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, (int, float)) and abs(float(value) - expected) <= 0.1:
            return True
    return False


# 提取支持的密封面代号并转大写，不认识的文本返回空值。
def _normalize_facing(value: Any) -> str | None:
    if not value:
        return None
    match = re.search(r"\b(FF|RF|MF|TG|RJ)\b", str(value), re.IGNORECASE)
    return match.group(1).upper() if match else None


# 从标准编号中提取独立的四位年份，作为版次候选。
def _standard_edition(value: Any) -> str | None:
    match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", str(value or ""))
    return match.group(0) if match else None


# 提取文本中首个非负整数或小数，供压力等级解析。
def _parse_number(value: Any) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


# 读取已归一化事实中的数值，非数值事实返回空值。
def _numeric_fact(fact: dict | None) -> float | None:
    value = _fact_value(fact)
    return float(value) if isinstance(value, (int, float)) else None


# 取事实归一化值；未找到事实时返回空值以跳过回填。
def _fact_value(fact: dict | None) -> Any:
    return fact.get("normalized_value") if fact else None


# 保存字段值、来源、四位置信度、决策与复核状态，供融合报告展示。
def _record(fields, path, value, source, confidence, decision, needs_review):
    fields.append(
        {
            "path": path,
            "value": value,
            "source": source,
            "confidence": round(float(confidence), 4),
            "decision": decision,
            "needs_review": bool(needs_review),
        }
    )


# 仅把空值、空文本及空容器视为可补空，保留零和 False。
def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


# 沿点分键路径读取嵌套字典，中途不是字典时返回空值。
def _get_path(root: dict, path: str) -> Any:
    current: Any = root
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


# 沿点分路径补建字典并写入末级值，用于规范字段回填。
def _set_path(root: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    current = root
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value
