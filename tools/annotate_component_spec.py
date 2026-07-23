#!/usr/bin/env python3
"""Annotate ComponentSpec YAML fields with their authoritative data source.

The transformer is deliberately text based so the original layout and comments
remain readable.  Annotations are appended only inside YAML comments.
"""

from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


DRAWING = "可以从图纸直接获得"
STEP = "可以从STEP直接获得"
ALGORITHM = "可以获得但是需要推理和算法"
UNAVAILABLE = "无法获得"
ALLOWED_CATEGORIES = {DRAWING, STEP, ALGORITHM, UNAVAILABLE}

ANNOTATION_MARKER = "@："
KEY_RE = re.compile(
    r"^(?P<indent>\s*)(?:-\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?P<value>.*)$"
)


PARAMETER_SOURCES: Dict[str, Tuple[str, str]] = {
    "DN": (DRAWING, "公称尺寸是产品语义，应从图纸标题栏或选型表读取，不应从实体尺寸反推"),
    "PN": (DRAWING, "公称压力是产品等级，应从图纸产品信息或标题栏读取"),
    "flange_outer_diameter": (STEP, "法兰外轮廓直径可由B-Rep外圆柱面或径向包络直接测量"),
    "bolt_circle_diameter": (ALGORITHM, "需先识别螺栓孔圆周阵列，再拟合孔中心圆并计算PCD"),
    "bolt_hole_count": (ALGORITHM, "需先识别哪些圆柱孔属于同一螺栓孔阵列后计数"),
    "bolt_hole_diameter": (STEP, "螺栓孔圆柱面的半径是B-Rep显式几何，可直接换算直径"),
    "bolt_hole_start_angle": (ALGORITHM, "必须先建立规范坐标系和零角度方向，再计算第一个孔的方位角"),
    "flange_thickness": (ALGORITHM, "需识别法兰盘两个语义端面，排除突面和颈部后计算轴向距离"),
    "bore_diameter": (ALGORITHM, "需从多个同轴圆柱面中识别中心贯穿内孔，不能只按直径大小选择"),
    "pipe_outer_diameter": (STEP, "焊接端配管外径可由端部圆柱面直接测量"),
    "wall_thickness": (ALGORITHM, "需匹配焊接端内外同轴表面后计算；图纸若仅给下限则不能当作精确值"),
    "hub_large_end_diameter": (ALGORITHM, "需识别锥颈与法兰过渡处的语义截面并求大端直径"),
    "hub_small_end_diameter": (ALGORITHM, "需识别颈部焊接端的外圆柱/锥面边界后测量"),
    "hub_height": (ALGORITHM, "需识别颈部起止截面；图纸近似值与STEP实体值还需语义裁决"),
    "overall_height": (STEP, "零件主轴方向的实体包络长度可由STEP几何直接测量"),
    "facing_type": (DRAWING, "密封面形式是产品语义，应从图纸产品信息或标题栏读取"),
    "raised_face_diameter": (ALGORITHM, "需识别密封端的环形突面，再测量其外径"),
    "raised_face_height": (ALGORITHM, "需识别基准端面与突面，再测量两平面间距"),
    "root_fillet_radius": (ALGORITHM, "需识别颈部与法兰盘的过渡圆角，再从圆环面/圆弧几何取半径"),
    "weld_bevel_angle": (ALGORITHM, "需识别焊接端倒角面后测量；若STEP未建坡口且图纸未标注则无法获得"),
}

GEOMETRIC_PARAMETERS = {
    name for name, (category, _reason) in PARAMETER_SOURCES.items() if category != DRAWING
}


def split_inline_comment(line: str) -> Tuple[str, str]:
    """Split at the first unquoted YAML comment marker."""
    single = False
    double = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and double:
            escaped = True
            continue
        if char == "'" and not double:
            single = not single
            continue
        if char == '"' and not single:
            double = not double
            continue
        if char == "#" and not single and not double:
            return line[:index].rstrip(), line[index:]
    return line.rstrip(), ""


def scalar_text(value: str) -> str:
    value = value.strip()
    if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
        return value[1:-1]
    return value


def param_source(parameter: Optional[str]) -> Tuple[str, str]:
    if parameter in PARAMETER_SOURCES:
        return PARAMETER_SOURCES[parameter]
    return ALGORITHM, "需根据零件语义、图纸符号或STEP特征进行映射"


def structure(reason: str = "属于ComponentSpec结构定义，不是STEP或图纸中的产品数据") -> Tuple[str, str]:
    return UNAVAILABLE, reason


class Context:
    def __init__(self) -> None:
        self.stack: List[Tuple[int, str]] = []
        self.top = ""
        self.parameter: Optional[str] = None
        self.derived_parameter: Optional[str] = None
        self.port: Optional[str] = None
        self.preset: Optional[str] = None
        self.construction: Optional[str] = None
        self.artifact: Optional[str] = None

    def observe(self, indent: int, key: str, value: str) -> List[str]:
        while self.stack and self.stack[-1][0] >= indent:
            self.stack.pop()
        parents = [item[1] for item in self.stack]

        if indent == 0:
            self.top = key
            self.parameter = None
            self.derived_parameter = None
            self.port = None
            self.preset = None
            self.construction = None
            self.artifact = None

        text = scalar_text(value)
        if self.top == "parameters" and indent == 2 and key == "name":
            self.parameter = text
        elif self.top == "derived_parameters" and indent == 2 and key == "name":
            self.derived_parameter = text
        elif self.top == "ports" and indent == 2 and key == "id":
            self.port = text
        elif self.top == "presets" and indent == 2 and key == "name":
            self.preset = text
        elif self.top == "geometry" and indent == 4 and key == "id" and "construction" in parents:
            self.construction = text
        elif self.top == "artifacts" and indent == 2:
            self.artifact = key

        path = parents + [key]
        self.stack.append((indent, key))
        return path


def classify_parameter_metadata(key: str, parameter: Optional[str]) -> Tuple[str, str]:
    category, reason = param_source(parameter)
    if key == "name":
        return category, f"该参数所表达的值来源：{reason}"
    if key == "label":
        return ALGORITHM, "需将图纸符号或原始文本归一化为系统语义名称"
    if key == "type":
        return ALGORITHM, "可根据规范化值、单位和参数语义推断数据类型，但应由schema固化"
    if key == "unit":
        if parameter in {"DN", "PN", "facing_type", "bolt_hole_count"}:
            return DRAWING, "图纸符号和表头可判定该项为等级、枚举或无量纲计数"
        return STEP, "STEP单位声明可提供几何长度单位"
    if key == "default":
        return UNAVAILABLE, "默认值是零件库/产品配置决策，不应由单个STEP或图纸自动决定"
    if key == "enum":
        return ALGORITHM, "需聚合标准表、多份图纸或零件库数据才能建立完整取值集"
    if key in {"min", "max"}:
        return UNAVAILABLE, "参数允许边界是生成器或标准库规则，不能从单个实例反推"
    if key in {"required", "editable", "affects_geometry"}:
        return UNAVAILABLE, "属于参数化模型和产品配置策略，需生成器作者或库管理员定义"
    if key == "standard_symbol":
        return DRAWING, "尺寸符号可从图纸标注和表头直接读取"
    return category, reason


def classify_identity(key: str) -> Tuple[str, str]:
    if key in {"identity", "standard"}:
        return structure()
    if key == "id":
        return UNAVAILABLE, "系统内部零件族ID必须由零件库分配"
    if key == "name":
        return DRAWING, "产品名称通常可从图纸标题栏或产品信息区读取"
    if key == "name_en":
        return ALGORITHM, "可由中文产品名称和领域词表翻译归一化"
    if key in {"type", "subtype", "family"}:
        return ALGORITHM, "需将图纸原始类型和STEP结构特征映射到系统分类体系"
    if key == "number":
        return DRAWING, "标准号通常在图纸产品信息或技术要求中明确给出"
    if key == "edition":
        return ALGORITHM, "可从标准号年份解析或查询标准库获得"
    if key == "title":
        return ALGORITHM, "图纸通常只给标准号，正式标准名需查询标准库归一化"
    if key == "description":
        return ALGORITHM, "可根据零件类型、端口和应用场景生成，但不是源文件权威字段"
    if key in {"license", "version", "author", "maintainer", "created_at", "updated_at", "status"}:
        return UNAVAILABLE, "属于零件库授权、版本或生命周期管理信息，需人工或系统记录"
    if key == "tags":
        return ALGORITHM, "可根据产品名、类型、标准和用途生成检索标签"
    if key in {"default_preset", "default_color"}:
        return UNAVAILABLE, "属于零件库默认选择或展示策略，不应从输入文件猜测"
    return structure()


def classify_coordinate(key: str) -> Tuple[str, str]:
    if key == "coordinate_system":
        return structure()
    if key == "length_unit":
        return STEP, "STEP文件的单位定义可直接读取长度单位"
    if key in {"angle_unit", "handedness"}:
        return UNAVAILABLE, "属于系统规范坐标与单位约定，需全库统一定义"
    if key in {"origin", "x_axis", "y_axis", "z_axis"}:
        return ALGORITHM, "需识别零件主轴、端面和旋转基准，再执行坐标归一化"
    if key in {"origin_definition", "z_axis_definition", "zero_rotation_definition"}:
        return UNAVAILABLE, "属于建模和装配规范约定，源STEP/图纸不会给出全库统一的语义定义"
    return structure()


def classify_port(key: str, path: Sequence[str]) -> Tuple[str, str]:
    if key in {"ports", "frame", "interface", "compatible_with", "rules"}:
        return structure("属于装配端口合同结构，不是源文件的原生字段")
    if key == "id":
        return UNAVAILABLE, "端口ID是系统内部稳定标识，需由零件族模板定义"
    if key in {"name", "type", "role"}:
        return ALGORITHM, "可根据零件类型和候选接口几何进行语义识别，但需零件族规则确认"
    if key in {"origin", "axis", "up"}:
        return ALGORITHM, "需将接口面/中心轴几何锚点转换到规范坐标系后求得端口坐标框"
    if key == "standard":
        return DRAWING, "接口标准应从图纸产品信息或技术要求读取"
    if key in PARAMETER_SOURCES:
        return param_source(key)
    if key == "bevel_angle":
        return param_source("weld_bevel_angle")
    if key in {"port_types", "allowed_mates"} or (key == "<list_scalar>" and "rules" in path):
        return UNAVAILABLE, "允许的端口类型、配合方式和兼容规则属于装配业务合同，必须人工/系统定义"
    return structure("属于装配端口规则，需由零件族模板或装配求解器定义")


def classify_geometry(key: str, path: Sequence[str]) -> Tuple[str, str]:
    if key in {
        "geometry", "generator", "construction", "output", "representation",
        "modeling_kernel", "mode", "preferred_engine", "engine_version",
        "script_file", "entrypoint", "script_required_for_release", "id",
        "operation", "depends_on", "profile_plane", "axis", "angle",
        "profile_definition", "direction", "through_all", "target",
        "enabled_when", "format", "application_protocol", "preserve_names",
        "preserve_colors", "filename_template", "hole_diameter",
        "pitch_circle_diameter", "count", "start_angle", "radius",
    }:
        return UNAVAILABLE, "属于参数化生成器实现、特征顺序或输出策略，必须由建模程序/库规范定义"
    return structure("属于参数化建模配方，不能从成品STEP或图纸唯一还原")


def classify_validation(key: str, path: Sequence[str]) -> Tuple[str, str]:
    if key in {"geometry", "topology", "ports", "review", "step_roundtrip", "bounding_box_expression", "parameter_validation", "validation"}:
        return structure("属于验证规则结构，不是输入文件中的实例数据")
    return UNAVAILABLE, "该值表达期望、容差、发布门禁或输出质量策略，只能由产品/工程规则定义"


def classify_artifact(key: str, artifact: Optional[str]) -> Tuple[str, str]:
    if key in {"artifacts", "reference_step", "generator_source", "preview_model", "thumbnail"}:
        return structure("属于交付物清单结构，由零件库管理")
    if key == "format" and artifact == "reference_step":
        return STEP, "输入文件格式可由文件头和扩展名确定"
    if key == "application_protocol" and artifact == "reference_step":
        return STEP, "STEP应用协议可由FILE_SCHEMA等文件头声明直接读取"
    if key == "length_unit" and artifact == "reference_step":
        return STEP, "STEP单位定义可从文件模型中直接读取"
    if key == "sha256":
        return ALGORITHM, "可对实际交付文件计算SHA-256，但不是STEP/图纸内容字段"
    return UNAVAILABLE, "文件路径、用途、是否必需和生成交付规则由零件库/发布流程定义"


def classify_provenance(key: str) -> Tuple[str, str]:
    if key in {"provenance", "standard_refs"}:
        return structure("属于数据来源与审计结构，由处理流水线记录")
    if key == "source_type":
        return ALGORITHM, "可根据实际输入文件、标准库命中和生成过程综合判定"
    if key in {"number", "table", "page", "series"}:
        return DRAWING, "标准号、表页信息和适用系列应从图纸/标准文档的明确标识读取"
    return UNAVAILABLE, "录入方式、备注、核验人员和变更说明属于流程审计数据，需系统/人工记录"


def classify(top: str, key: str, path: Sequence[str], context: Context) -> Tuple[str, str]:
    if key in {"schema_version", "spec_type"}:
        return UNAVAILABLE, "属于ComponentSpec协议版本和对象类型，由系统固定"
    if top == "identity":
        return classify_identity(key)
    if top == "coordinate_system":
        return classify_coordinate(key)
    if top == "parameters":
        if key == "parameters":
            return structure()
        return classify_parameter_metadata(key, context.parameter)
    if top == "derived_parameters":
        return UNAVAILABLE, "派生参数名称、类型和表达式属于参数化模型逻辑，需生成器作者定义"
    if top == "constraints":
        return UNAVAILABLE, "参数约束、严重级别和提示信息属于参数化模型规则，不能从单个实例反推"
    if top == "ports":
        return classify_port(key, path)
    if top == "geometry":
        return classify_geometry(key, path)
    if top == "presets":
        if key == "presets" or key == "params":
            return structure("属于零件族规格集合结构，不是单个源文件字段")
        if key == "name":
            return ALGORITHM, "可由DN、PN、标准、密封面等已解析规格值按命名规则生成"
        if key == "source_ref":
            return DRAWING, "数据对应的图纸、标准表和页码应从源文档引用信息读取"
        if key == "verification_status":
            return UNAVAILABLE, "验证状态是处理流程结果，需根据实际核验过程记录"
        if key in PARAMETER_SOURCES:
            return param_source(key)
        return structure("属于零件族规格配置，需标准数据和零件库规则确认")
    if top == "validation":
        return classify_validation(key, path)
    if top == "artifacts":
        return classify_artifact(key, context.artifact)
    if top == "provenance":
        return classify_provenance(key)
    return structure()


def annotate_lines(lines: Sequence[str]) -> Tuple[List[str], collections.Counter]:
    output: List[str] = []
    counts: collections.Counter = collections.Counter()
    context = Context()

    for line_number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            output.append(line)
            continue

        code, comment = split_inline_comment(line)
        match = KEY_RE.match(code)
        if match:
            indent = len(match.group("indent"))
            key = match.group("key")
            value = match.group("value").strip()
            path = context.observe(indent, key, value)
        elif code.lstrip().startswith("-"):
            indent = len(code) - len(code.lstrip())
            key = "<list_scalar>"
            value = code.lstrip()[1:].strip()
            path = [item[1] for item in context.stack] + [key]
        else:
            raise ValueError(f"Unrecognized YAML data line {line_number}: {line}")

        category, reason = classify(context.top, key, path, context)
        if category not in ALLOWED_CATEGORIES:
            raise AssertionError(f"Unexpected category at line {line_number}: {category}")
        counts[category] += 1
        annotation = f"{ANNOTATION_MARKER}{category}；{reason}"
        if comment:
            output.append(f"{code} {comment.rstrip()} {annotation}")
        else:
            output.append(f"{code}  # {annotation}")

    return output, counts


def data_line_indexes(lines: Sequence[str]) -> List[int]:
    return [
        index
        for index, line in enumerate(lines)
        if line.strip() and not line.lstrip().startswith("#")
    ]


def verify(source_lines: Sequence[str], output_lines: Sequence[str]) -> None:
    if len(source_lines) != len(output_lines):
        raise AssertionError(
            f"Line count changed: source={len(source_lines)} output={len(output_lines)}"
        )

    source_data_indexes = data_line_indexes(source_lines)
    output_data_indexes = data_line_indexes(output_lines)
    if source_data_indexes != output_data_indexes:
        raise AssertionError("Data-line positions changed")

    for index in source_data_indexes:
        marker_count = output_lines[index].count(ANNOTATION_MARKER)
        if marker_count != 1:
            raise AssertionError(
                f"Line {index + 1} has {marker_count} annotation markers"
            )

    source_text = "\n".join(source_lines) + "\n"
    output_text = "\n".join(output_lines) + "\n"
    source_data = yaml.safe_load(source_text)
    output_data = yaml.safe_load(output_text)
    if source_data != output_data:
        raise AssertionError("Annotated YAML data differs from source YAML data")


def print_report(output_lines: Sequence[str], counts: collections.Counter) -> None:
    print(f"annotated_data_lines={sum(counts.values())}")
    for category in (DRAWING, STEP, ALGORITHM, UNAVAILABLE):
        print(f"{category}={counts[category]}")
        examples = [line.strip() for line in output_lines if f"{ANNOTATION_MARKER}{category}" in line][:2]
        for example in examples:
            print(f"  example: {example}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(r"D:\ragxinchuang\component-spec-v1.2-template.yaml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(r"D:\3D解析\docs\component-spec-v1.2-template.annotated.yaml"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_text = args.source.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    output_lines, counts = annotate_lines(source_lines)
    verify(source_lines, output_lines)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    trailing_newline = "\n" if source_text.endswith(("\n", "\r")) else ""
    args.output.write_text("\n".join(output_lines) + trailing_newline, encoding="utf-8")
    print(f"output={args.output}")
    print_report(output_lines, counts)


if __name__ == "__main__":
    main()
