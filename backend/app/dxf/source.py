"""Read DXF source semantics into JSON-safe, revision-bound records."""

from __future__ import annotations

import hashlib
from pathlib import Path

import ezdxf

from app.dxf.geometry import measure_entity

PARSER_VERSION = "dxf-source-v1"
SUPPORTED = {"POINT", "LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE"}
MAX_ENTITIES = 200_000
MAX_VERTICES = 2_000_000


def _point(value) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


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


def _attributes(entity) -> dict:
    return {key: str(value) for key, value in entity.dxf.all_existing_dxf_attribs().items()
            if key not in {"handle", "owner"}}


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
                else:
                    record["status"] = "unsupported"
                    diagnostics.append({"code": "unsupported_entity", "object_id": record["object_id"],
                                        "type": kind, "layout": layout.name, "handle": handle})
            except (TypeError, ValueError, AttributeError, ezdxf.DXFError) as exc:
                record["status"] = "failed"
                diagnostics.append({"code": "entity_parse_failed", "object_id": record["object_id"],
                                    "type": kind, "message": str(exc)})
            entities.append(record)
    units_code = int(drawing.header.get("$INSUNITS", 0))
    entities = [measure_entity(record, units_code) for record in entities]
    source_layers = _source_layer_names(source)
    return {
        "schema_version": "dxf_document_v1", "parser_version": PARSER_VERSION,
        "revision_id": revision_id, "source_sha256": hashlib.sha256(source).hexdigest(),
        "dxf_version": drawing.dxfversion, "encoding": drawing.encoding,
        "units": {"code": units_code, "source": "$INSUNITS" if units_code else "drawing_unit"},
        "layouts": [{"name": layout.name, "is_model": layout.name == "Model"} for layout in drawing.layouts],
        "layers": [{"name": layer.dxf.name, "source_defined": source_layers is None or layer.dxf.name in source_layers,
                    "color": int(layer.dxf.color),
                    "linetype": layer.dxf.linetype, "visible": not layer.is_off() and not layer.is_frozen()}
                   for layer in drawing.layers],
        "entities": entities, "diagnostics": diagnostics,
        "counts": {"source_entities": len(entities),
                   "parsed": sum(record.get("status") is None for record in entities),
                   "unsupported": sum(record.get("status") == "unsupported" for record in entities),
                   "failed": sum(record.get("status") == "failed" for record in entities),
                   "vertices": vertices_seen},
    }
