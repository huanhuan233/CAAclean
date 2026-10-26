# 读取 DXF 源语义，绑定修订与源文件摘要，并将原始实体、块实例和解析诊断分别保留。
"""Read DXF source semantics into JSON-safe, revision-bound records."""

from __future__ import annotations

import hashlib
from itertools import islice
from pathlib import Path

import ezdxf
from ezdxf import path as dxf_path

from app.dxf.geometry import measure_entity

PARSER_VERSION = "dxf-source-v1"
SUPPORTED = {"POINT", "LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE"}
MAX_ENTITIES = 200_000
MAX_VERTICES = 2_000_000
MAX_OCCURRENCES = 50_000
MAX_BLOCK_DEPTH = 8


# 把三维坐标序列转换为可 JSON 序列化的浮点列表。
def _point(value) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


# 在 ezdxf 补默认资源前扫描 ASCII 图层声明；二进制 DXF 无此来源判断。
def _source_layer_names(source: bytes) -> set[str] | None:
    """Inspect ASCII TABLES tags before ezdxf adds required default resources."""
    if source.startswith(b"AutoCAD Binary DXF"):
        return None
    lines = source.decode("latin-1").splitlines()
    names: set[str] = set()
    in_tables = False
    in_layer = False
    for index in range(0, len(lines) - 1, 2):
        code, value = lines[index].strip(), lines[index + 1].strip()
        if code == "0" and value == "SECTION":
            in_tables = False
        elif code == "2" and value == "TABLES":
            in_tables = True
        elif code == "0" and value == "ENDSEC":
            in_tables = False
        if not in_tables:
            continue
        if code == "0":
            in_layer = value == "LAYER"
        elif in_layer and code == "2":
            names.add(value)
            in_layer = False
    return names


# 保留已存在的 DXF 属性文本，但排除另行记录的句柄和所有者。
def _attributes(entity) -> dict:
    return {key: str(value) for key, value in entity.dxf.all_existing_dxf_attribs().items()
            if key not in {"handle", "owner"}}


# 为已变换的块子实体创建派生记录，以实例路径区分身份并保留定义句柄线索。
def _virtual_record(entity, revision_id: str, layout: str, layer: str, occurrence_path: list[str],
                    definition_handle: str | None) -> dict:
    kind = entity.dxftype()
    record = {"object_id": f"{revision_id}:{layout}:{'/'.join(occurrence_path)}",
              "source_handle": None, "derived": True, "definition_handle": definition_handle,
              "occurrence_path": occurrence_path, "layout": layout,
              "layer": entity.dxf.get("layer", layer), "type": kind,
              "source_attributes": _attributes(entity)}
    if kind == "LINE":
        record.update(start=_point(entity.dxf.start), end=_point(entity.dxf.end))
    elif kind in {"CIRCLE", "ARC"}:
        record.update(center=_point(entity.ocs().to_wcs(entity.dxf.center)), radius=float(entity.dxf.radius))
        if kind == "ARC":
            record.update(start_angle=float(entity.dxf.start_angle), end_angle=float(entity.dxf.end_angle))
    elif kind == "LWPOLYLINE":
        record["vertices"] = [[float(x), float(y), float(sw), float(ew), float(b)]
                              for x, y, sw, ew, b in entity.get_points("xyseb")]
        record["closed"] = bool(entity.closed)
        record["elevation"] = float(entity.dxf.get("elevation", 0))
        record["extrusion"] = _point(entity.dxf.get("extrusion", (0, 0, 1)))
        record["world_vertices"] = [_point(entity.ocs().to_wcs((v[0], v[1], record["elevation"])))
                                    for v in record["vertices"]]
    elif kind == "TEXT":
        record.update(raw_text=entity.dxf.text, display_text=entity.dxf.text,
                      insert=_point(entity.dxf.insert), text_height=float(entity.dxf.height))
    else:
        record["status"] = "unsupported"
    return record


# 递归展开块和阵列实例，限制递归深度及实例数量，并记录缺块、循环或变换失败。
def _expand_insert(entity, drawing, revision_id: str, layout: str, path: list[str],
                   active_blocks: set[str], out: list[dict], diagnostics: list[dict]) -> None:
    name = entity.dxf.name
    # 当前递归栈防止块循环，路径长度和全局实例计数限制展开规模。
    if name in active_blocks or len(path) > MAX_BLOCK_DEPTH:
        diagnostics.append({"code": "block_cycle_or_depth", "occurrence_path": path, "block": name})
        return
    if name not in drawing.blocks:
        diagnostics.append({"code": "block_missing", "occurrence_path": path, "block": name})
        return
    if len(out) >= MAX_OCCURRENCES:
        diagnostics.append({"code": "occurrence_budget", "occurrence_path": path})
        return
    definition = list(drawing.blocks[name])
    try:
        instances = list(islice(entity.multi_insert(), MAX_OCCURRENCES - len(out) + 1)) if entity.mcount > 1 else [entity]
    except (AttributeError, ValueError):
        instances = [entity]
    for instance_index, instance in enumerate(instances):
        if len(out) >= MAX_OCCURRENCES:
            diagnostics.append({"code": "occurrence_budget", "occurrence_path": path})
            return
        instance_path = [*path, str(instance_index)] if len(instances) > 1 else path
        try:
            virtuals = list(instance.virtual_entities())
        except (ezdxf.DXFError, ValueError) as exc:
            diagnostics.append({"code": "block_transform_failed", "occurrence_path": instance_path,
                                "message": str(exc)})
            continue
        for child_index, virtual in enumerate(virtuals):
            if len(out) >= MAX_OCCURRENCES:
                diagnostics.append({"code": "occurrence_budget", "occurrence_path": instance_path})
                return
            child_path = [*instance_path, str(child_index)]
            if virtual.dxftype() == "INSERT":
                _expand_insert(virtual, drawing, revision_id, layout, child_path,
                               active_blocks | {name}, out, diagnostics)
                continue
            # 定义句柄按子实体序号关联；派生实体的唯一身份仍由 occurrence_path 给出。
            definition_handle = definition[child_index].dxf.get("handle") if child_index < len(definition) else None
            try:
                out.append(_virtual_record(virtual, revision_id, layout,
                                           instance.dxf.get("layer", "0"), child_path, definition_handle))
            except (ezdxf.DXFError, ValueError, AttributeError) as exc:
                diagnostics.append({"code": "block_entity_failed", "occurrence_path": child_path,
                                    "message": str(exc)})


# 校验文件头并逐实体解析源语义，保留局部失败诊断，最终附加单位与测量结果。
def parse_source(path: Path, revision_id: str) -> dict:
    """Reject malformed input and preserve unsupported entities as explicit diagnostics."""
    source = path.read_bytes()
    if not source or (not source.startswith(b"AutoCAD Binary DXF\r\n\x1a\x00")
                      and b"SECTION" not in source[:4096]):
        raise ValueError("DXF_HEADER_INVALID: source is neither ASCII nor binary DXF")
    try:
        drawing = ezdxf.readfile(path)
    except (ezdxf.DXFError, UnicodeError, OSError) as exc:
        raise ValueError(f"DXF_PARSE_INVALID: {exc}") from exc
    entities = []
    occurrences = []
    diagnostics = []
    vertices_seen = 0
    for layout in drawing.layouts:
        for entity in layout:
            if len(entities) + len(diagnostics) >= MAX_ENTITIES:
                diagnostics.append({"code": "entity_budget", "layout": layout.name,
                                    "message": "entity expansion budget reached"})
                break
            kind = entity.dxftype()
            handle = entity.dxf.get("handle")
            record = {
                "object_id": f"{revision_id}:{layout.name}:{handle}",
                "source_handle": handle, "derived": False,
                "owner": entity.dxf.get("owner"), "layout": layout.name,
                "layer": entity.dxf.get("layer", "0"), "type": kind,
                "source_attributes": _attributes(entity),
            }
            try:
                if kind == "POINT":
                    record["point"] = _point(entity.dxf.location)
                elif kind == "LINE":
                    record["start"] = _point(entity.dxf.start)
                    record["end"] = _point(entity.dxf.end)
                elif kind in {"CIRCLE", "ARC"}:
                    record["center"] = _point(entity.ocs().to_wcs(entity.dxf.center))
                    record["radius"] = float(entity.dxf.radius)
                    record["extrusion"] = _point(entity.dxf.get("extrusion", (0, 0, 1)))
                    if kind == "ARC":
                        record["start_angle"] = float(entity.dxf.start_angle)
                        record["end_angle"] = float(entity.dxf.end_angle)
                elif kind == "LWPOLYLINE":
                    points = list(entity.get_points("xyseb"))
                    vertices_seen += len(points)
                    if vertices_seen > MAX_VERTICES:
                        raise ValueError("vertex budget reached")
                    record["vertices"] = [[float(x), float(y), float(start), float(end), float(bulge)]
                                          for x, y, start, end, bulge in points]
                    record["closed"] = bool(entity.closed)
                    record["elevation"] = float(entity.dxf.get("elevation", 0))
                    record["extrusion"] = _point(entity.dxf.get("extrusion", (0, 0, 1)))
                    record["world_vertices"] = [_point(entity.ocs().to_wcs((v[0], v[1], record["elevation"])))
                                                for v in record["vertices"]]
                elif kind == "POLYLINE" and entity.is_2d_polyline:
                    points = list(entity.vertices)
                    vertices_seen += len(points)
                    if vertices_seen > MAX_VERTICES:
                        raise ValueError("vertex budget reached")
                    record["vertices"] = [[float(v.dxf.location.x), float(v.dxf.location.y),
                                           float(v.dxf.get("start_width", 0)),
                                           float(v.dxf.get("end_width", 0)),
                                           float(v.dxf.get("bulge", 0))] for v in points]
                    record["closed"] = bool(entity.is_closed)
                    record["elevation"] = float(entity.dxf.elevation.z)
                    record["extrusion"] = _point(entity.dxf.get("extrusion", (0, 0, 1)))
                    record["world_vertices"] = [_point(entity.ocs().to_wcs((v[0], v[1], record["elevation"])))
                                                for v in record["vertices"]]
                elif kind == "INSERT":
                    record.update(block_name=entity.dxf.name, insert=_point(entity.dxf.insert),
                                  rotation=float(entity.dxf.get("rotation", 0)),
                                  scale=[float(entity.dxf.get("xscale", 1)), float(entity.dxf.get("yscale", 1)),
                                         float(entity.dxf.get("zscale", 1))],
                                  attribs=[{"tag": item.dxf.tag, "text": item.dxf.text}
                                           for item in entity.attribs])
                    _expand_insert(entity, drawing, revision_id, layout.name, [str(handle)],
                                   set(), occurrences, diagnostics)
                elif kind == "TEXT":
                    style = entity.dxf.get("style", "Standard")
                    font = drawing.styles.get(style)
                    record.update(raw_text=entity.dxf.text, display_text=entity.dxf.text,
                                  insert=_point(entity.dxf.insert), text_height=float(entity.dxf.height),
                                  style=style, font_ref=font.dxf.get("font") if font else None,
                                  rotation=float(entity.dxf.get("rotation", 0)))
                elif kind == "MTEXT":
                    style = entity.dxf.get("style", "Standard")
                    font = drawing.styles.get(style)
                    record.update(raw_text=entity.text, display_text=entity.plain_text(),
                                  insert=_point(entity.dxf.insert), text_height=float(entity.dxf.char_height),
                                  style=style, font_ref=font.dxf.get("font") if font else None)
                # 标注覆盖文本、显示文本和几何测量分别保存，避免把显示覆盖值当作实测值。
                elif kind == "DIMENSION":
                    raw_text = entity.dxf.get("text", "")
                    measured = entity.get_measurement()
                    measured = float(measured) if measured is not None else None
                    record.update(dimension_type=int(entity.dimtype),
                                  raw_text=raw_text,
                                  display_text="" if raw_text == " " else
                                  str(measured) if raw_text in {"", "<>"} and measured is not None else raw_text,
                                  measurement=measured,
                                  dimstyle=entity.dxf.get("dimstyle", "Standard"),
                                  geometry_block=entity.dxf.get("geometry"),
                                  style_overrides=dict(entity.get_acad_dstyle(
                                      drawing.dimstyles.get(entity.dxf.get("dimstyle", "Standard")))))
                elif kind == "HATCH":
                    boundaries = []
                    for boundary in entity.paths.paths:
                        if hasattr(boundary, "vertices"):
                            boundaries.append({"type": "polyline", "closed": bool(boundary.is_closed),
                                               "vertices": [[float(x), float(y), 0.0, 0.0, float(b)]
                                                            for x, y, b in boundary.vertices]})
                        else:
                            boundaries.append({"type": "edge", "edge_count": len(boundary.edges)})
                    record.update(solid_fill=bool(entity.dxf.solid_fill),
                                  pattern_name=entity.dxf.get("pattern_name"),
                                  boundary_path_count=len(boundaries), boundary_paths=boundaries,
                                  hatch_style=int(entity.dxf.get("hatch_style", 0)),
                                  pattern_scale=float(entity.dxf.get("pattern_scale", 1)),
                                  pattern_angle=float(entity.dxf.get("pattern_angle", 0)))
                # 曲线离散点仅用于显示；0.05 容差使用图纸单位，此路径不计算精确弧长或面积。
                elif kind in {"ELLIPSE", "SPLINE"}:
                    curve = dxf_path.make_path(entity)
                    record["display_points"] = [_point(point) for point in curve.flattening(distance=0.05, segments=8)]
                    record["display_tolerance"] = 0.05
                    if kind == "SPLINE":
                        record.update(degree=int(entity.dxf.degree),
                                      knots=[float(v) for v in entity.knots],
                                      weights=[float(v) for v in entity.weights],
                                      control_points=[_point(v) for v in entity.control_points])
                else:
                    record["status"] = "unsupported"
                    diagnostics.append({"code": "unsupported_entity", "object_id": record["object_id"],
                                        "type": kind, "layout": layout.name, "handle": handle})
            # 单个实体解析失败仍保留对象身份及诊断，不使整个文档的其他实体丢失。
            except (TypeError, ValueError, AttributeError, ezdxf.DXFError) as exc:
                record["status"] = "failed"
                diagnostics.append({"code": "entity_parse_failed", "object_id": record["object_id"],
                                    "type": kind, "message": str(exc)})
            entities.append(record)
    # 毫米归一化只依赖 DXF 的 INSUNITS，不从图名、标注文字或几何尺寸猜单位。
    units_code = int(drawing.header.get("$INSUNITS", 0))
    entities = [measure_entity(record, units_code) for record in entities]
    occurrences = [measure_entity(record, units_code) for record in occurrences]
    source_layers = _source_layer_names(source)
    return {
        "schema_version": "dxf_document_v1", "parser_version": PARSER_VERSION,
        "revision_id": revision_id, "source_sha256": hashlib.sha256(source).hexdigest(),
        "dxf_version": drawing.dxfversion, "encoding": drawing.encoding,
        "units": {"code": units_code, "source": "$INSUNITS" if units_code else "drawing_unit"},
        "layouts": [{"name": layout.name, "is_model": layout.name == "Model"} for layout in drawing.layouts],
        "blocks": [{"name": block.name, "base_point": _point(block.base_point),
                    "entity_handles": [entity.dxf.get("handle") for entity in block]}
                   for block in drawing.blocks if not block.name.startswith("*")],
        "layers": [{"name": layer.dxf.name, "source_defined": None if source_layers is None else layer.dxf.name in source_layers,
                    "color": int(layer.dxf.color),
                    "linetype": layer.dxf.linetype, "visible": not layer.is_off() and not layer.is_frozen()}
                   for layer in drawing.layers],
        "entities": entities, "occurrences": occurrences, "diagnostics": diagnostics,
        "counts": {"source_entities": len(entities),
                   "parsed": sum(record.get("status") is None for record in entities),
                   "unsupported": sum(record.get("status") == "unsupported" for record in entities),
                   "failed": sum(record.get("status") == "failed" for record in entities),
                   "vertices": vertices_seen,
                   "occurrences": len(occurrences),
                   "displayable": sum(item.get("status") is None and item["type"] in
                                      {"POINT", "LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "TEXT", "MTEXT", "ELLIPSE", "SPLINE"}
                                      for item in [*entities, *occurrences]),
                   "measurable": sum(item.get("length") is not None for item in [*entities, *occurrences]),
                   "unprocessed": sum(item.get("code") in {"occurrence_budget", "block_cycle_or_depth"}
                                      for item in diagnostics)},
    }
