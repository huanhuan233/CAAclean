from __future__ import annotations

import json
import math
import sys
import uuid
from pathlib import Path

try:
    import FreeCAD
    import Import
    import MeshPart
    import Part
except ImportError as exc:
    raise SystemExit(f"FreeCAD modules are not available: {exc}")

# 用途：让 FreeCAD 标准执行和测试加载器都能从脚本同目录导入共享几何工具。
SCRIPT_FILE = globals().get("__file__") or sys.argv[0]
SCRIPT_DIRECTORY = str(Path(SCRIPT_FILE).resolve().parent)
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from bounds import union_bbox


SCHEMA_VERSION = "cad_parse_v2"
NAMESPACE = uuid.UUID("8c5fe5cc-91cb-4f13-8d1c-2a6e3ef93349")
CURVE_TYPE_IDS = {
    "Part::GeomLine": "line",
    "Part::GeomCircle": "circle",
    "Part::GeomEllipse": "ellipse",
    "Part::GeomHyperbola": "hyperbola",
    "Part::GeomParabola": "parabola",
    "Part::GeomBezierCurve": "bezier_curve",
    "Part::GeomBSplineCurve": "bspline_curve",
    "Part::GeomOffsetCurve": "offset_curve",
}
CURVE_2D_TYPE_IDS = {
    "Part::Geom2dLine": "line_2d",
    "Part::Geom2dCircle": "circle_2d",
    "Part::Geom2dEllipse": "ellipse_2d",
    "Part::Geom2dHyperbola": "hyperbola_2d",
    "Part::Geom2dParabola": "parabola_2d",
    "Part::Geom2dBezierCurve": "bezier_curve_2d",
    "Part::Geom2dBSplineCurve": "bspline_curve_2d",
    "Part::Geom2dOffsetCurve": "offset_curve_2d",
}
CURVE_2D_CLASS_TYPE_IDS = {
    "Line2d": "Part::Geom2dLine",
    "Circle2d": "Part::Geom2dCircle",
    "Ellipse2d": "Part::Geom2dEllipse",
    "Hyperbola2d": "Part::Geom2dHyperbola",
    "Parabola2d": "Part::Geom2dParabola",
    "BezierCurve2d": "Part::Geom2dBezierCurve",
    "BSplineCurve2d": "Part::Geom2dBSplineCurve",
    "OffsetCurve2d": "Part::Geom2dOffsetCurve",
}
DEGENERATE_LENGTH_TOLERANCE = 1e-12


def stable_uuid(revision_id: str, *parts: object) -> str:
    key = ":".join(str(part) for part in (revision_id, *parts))
    return str(uuid.uuid5(NAMESPACE, key))


def vec(value) -> list[float]:
    return [float(value.x), float(value.y), float(value.z)]


def coordinates(value) -> list[float]:
    result = [float(value.x), float(value.y)]
    try:
        result.append(float(value.z))
    except (AttributeError, TypeError, ValueError):
        pass
    return result


def safe_attr(value, *names):
    for name in names:
        try:
            candidate = getattr(value, name)
        except Exception:
            continue
        if candidate is not None:
            return candidate
    return None


def safe_call(value, name, *args, **kwargs):
    candidate = safe_attr(value, name)
    if not callable(candidate):
        return None
    try:
        return candidate(*args, **kwargs)
    except Exception:
        return None


def compact(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}


def bbox(shape) -> dict:
    box = shape.BoundBox
    return {
        "min": [float(box.XMin), float(box.YMin), float(box.ZMin)],
        "max": [float(box.XMax), float(box.YMax), float(box.ZMax)],
    }


def center(shape):
    try:
        return vec(shape.CenterOfMass)
    except Exception:
        return None


def attr_vec(value, *names):
    candidate = safe_attr(value, *names)
    if candidate is not None:
        try:
            return vec(candidate)
        except Exception:
            return None
    return None


def attr_float(value, *names):
    candidate = safe_attr(value, *names)
    if candidate is not None:
        try:
            return float(candidate)
        except Exception:
            return None
    return None


def attr_bool(value, *names):
    candidate = safe_attr(value, *names)
    if candidate is None:
        return None
    try:
        return bool(candidate() if callable(candidate) else candidate)
    except Exception:
        return None


def attr_int(value, *names):
    candidate = safe_attr(value, *names)
    if candidate is None:
        return None
    try:
        return int(candidate)
    except Exception:
        return None


def method_values(value, name, converter=None):
    values = safe_call(value, name)
    if values is None:
        return None
    try:
        return [converter(item) if converter else item for item in values]
    except Exception:
        return None


def parameter_range(value) -> list[float] | None:
    first = attr_float(value, "FirstParameter")
    last = attr_float(value, "LastParameter")
    if first is None or last is None:
        candidate = safe_attr(value, "ParameterRange")
        try:
            first, last = float(candidate[0]), float(candidate[1])
        except Exception:
            return None
    return [first, last]


def ranges_match(left: list[float] | None, right: list[float] | None) -> bool | None:
    if left is None or right is None:
        return None
    return all(
        math.isclose(left[index], right[index], rel_tol=1e-9, abs_tol=1e-12)
        for index in range(2)
    )


def point_at(edge, parameter):
    if parameter is None:
        return None
    point = safe_call(edge, "valueAt", parameter)
    if point is None:
        return None
    try:
        return coordinates(point)
    except Exception:
        return None


def normalized_direction(start, end):
    if start is None or end is None:
        return None
    try:
        delta = [float(end[index]) - float(start[index]) for index in range(len(start))]
        length = math.sqrt(sum(component * component for component in delta))
        if length <= DEGENERATE_LENGTH_TOLERANCE:
            return None
        return [component / length for component in delta]
    except Exception:
        return None


def curve_geometry(curve, geometry_type: str, depth: int = 0) -> dict:
    curve_type_id = safe_attr(curve, "TypeId")
    geometry: dict = {"curve_type_id": curve_type_id}

    if geometry_type == "line":
        geometry.update(
            compact(
                {
                    "location": attr_vec(curve, "Location", "Position"),
                    "direction": attr_vec(curve, "Direction", "Axis"),
                }
            )
        )
    elif geometry_type == "circle":
        geometry.update(
            compact(
                {
                    "center": attr_vec(curve, "Center", "Location", "Position"),
                    "axis": attr_vec(curve, "Axis"),
                    "radius": attr_float(curve, "Radius"),
                }
            )
        )
    elif geometry_type in {"ellipse", "hyperbola"}:
        center_point = attr_vec(curve, "Center", "Location", "Position")
        focus1 = attr_vec(curve, "Focus1")
        geometry.update(
            compact(
                {
                    "center": center_point,
                    "axis": attr_vec(curve, "Axis"),
                    "major_radius": attr_float(curve, "MajorRadius"),
                    "minor_radius": attr_float(curve, "MinorRadius"),
                    "focal": attr_float(curve, "Focal"),
                    "focus1": focus1,
                    "focus2": attr_vec(curve, "Focus2"),
                    "major_axis_direction": normalized_direction(center_point, focus1),
                }
            )
        )
    elif geometry_type == "parabola":
        geometry.update(
            compact(
                {
                    "location": attr_vec(curve, "Location", "Position", "Center"),
                    "axis": attr_vec(curve, "Axis"),
                    "focal": attr_float(curve, "Focal"),
                    "focus": attr_vec(curve, "Focus"),
                    "parameter": attr_float(curve, "Parameter"),
                }
            )
        )
    elif geometry_type in {"bezier_curve", "bspline_curve"}:
        geometry.update(
            compact(
                {
                    "degree": attr_int(curve, "Degree"),
                    "poles": method_values(curve, "getPoles", coordinates),
                    "weights": method_values(curve, "getWeights", float),
                    "rational": attr_bool(curve, "isRational"),
                }
            )
        )
        if geometry_type == "bspline_curve":
            geometry.update(
                compact(
                    {
                        "knots": method_values(curve, "getKnots", float),
                        "multiplicities": method_values(curve, "getMultiplicities", int),
                        "continuity": safe_attr(curve, "Continuity"),
                    }
                )
            )
    elif geometry_type == "offset_curve":
        geometry.update(
            compact(
                {
                    "offset_value": attr_float(curve, "OffsetValue"),
                    "offset_direction": attr_vec(curve, "OffsetDirection"),
                }
            )
        )
        basis_curve = safe_attr(curve, "BasisCurve")
        if basis_curve is not None and depth < 8:
            basis_type_id = safe_attr(basis_curve, "TypeId")
            basis_geometry_type = CURVE_TYPE_IDS.get(basis_type_id, "other_curve")
            geometry["basis_curve"] = {
                "geometry_type": basis_geometry_type,
                **curve_geometry(basis_curve, basis_geometry_type, depth + 1),
            }

    return compact(geometry)


def common_edge_geometry(edge, curve) -> dict:
    edge_range = parameter_range(edge)
    curve_range = parameter_range(curve)
    geometry = curve_geometry(curve, CURVE_TYPE_IDS.get(safe_attr(curve, "TypeId"), "other_curve"))
    geometry.update(
        compact(
            {
                "parameter_range": edge_range,
                "start_point": point_at(edge, edge_range[0]) if edge_range else None,
                "end_point": point_at(edge, edge_range[1]) if edge_range else None,
                "closed": attr_bool(curve, "isClosed"),
                "periodic": attr_bool(curve, "isPeriodic"),
                "trimmed": None if ranges_match(edge_range, curve_range) is None else not ranges_match(edge_range, curve_range),
            }
        )
    )
    return geometry


def sample_edge(edge, number: int = 9) -> list[list[float]] | None:
    points = safe_call(edge, "discretize", Number=number)
    if not points:
        return None
    try:
        return [coordinates(point) for point in points]
    except Exception:
        return None


def curve_2d_geometry(curve, geometry_type: str, depth: int = 0) -> dict:
    curve_type_id = curve_2d_type_id(curve)
    geometry: dict = {"curve_type_id": curve_type_id}
    if geometry_type == "line_2d":
        location = safe_attr(curve, "Location")
        direction = safe_attr(curve, "Direction")
        geometry.update(
            compact(
                {
                    "location": coordinates(location) if location is not None else None,
                    "direction": coordinates(direction) if direction is not None else None,
                }
            )
        )
    elif geometry_type == "circle_2d":
        center_value = safe_call(curve, "getCircleCenter") or safe_attr(curve, "Center", "Location")
        geometry.update(
            compact(
                {
                    "center": coordinates(center_value) if center_value is not None else None,
                    "radius": attr_float(curve, "Radius"),
                }
            )
        )
    elif geometry_type in {"ellipse_2d", "hyperbola_2d"}:
        center_value = safe_attr(curve, "Center", "Location")
        focus1_value = safe_attr(curve, "Focus1")
        center_point = coordinates(center_value) if center_value is not None else None
        focus1 = coordinates(focus1_value) if focus1_value is not None else None
        geometry.update(
            compact(
                {
                    "center": center_point,
                    "major_radius": attr_float(curve, "MajorRadius"),
                    "minor_radius": attr_float(curve, "MinorRadius"),
                    "focal": attr_float(curve, "Focal"),
                    "focus1": focus1,
                    "major_axis_direction": normalized_direction(center_point, focus1),
                }
            )
        )
    elif geometry_type == "parabola_2d":
        location = safe_attr(curve, "Location")
        focus = safe_attr(curve, "Focus")
        geometry.update(
            compact(
                {
                    "location": coordinates(location) if location is not None else None,
                    "focal": attr_float(curve, "Focal"),
                    "focus": coordinates(focus) if focus is not None else None,
                    "parameter": attr_float(curve, "Parameter"),
                }
            )
        )
    elif geometry_type in {"bezier_curve_2d", "bspline_curve_2d"}:
        geometry.update(
            compact(
                {
                    "degree": attr_int(curve, "Degree"),
                    "poles": method_values(curve, "getPoles", coordinates),
                    "weights": method_values(curve, "getWeights", float),
                    "rational": attr_bool(curve, "isRational"),
                    "periodic": attr_bool(curve, "isPeriodic"),
                }
            )
        )
        if geometry_type == "bspline_curve_2d":
            geometry.update(
                compact(
                    {
                        "knots": method_values(curve, "getKnots", float),
                        "multiplicities": method_values(curve, "getMultiplicities", int),
                    }
                )
            )
    elif geometry_type == "offset_curve_2d":
        geometry["offset_value"] = attr_float(curve, "OffsetValue")
        basis_curve = safe_attr(curve, "BasisCurve")
        if basis_curve is not None and depth < 8:
            basis_type_id = curve_2d_type_id(basis_curve)
            basis_geometry_type = CURVE_2D_TYPE_IDS.get(basis_type_id, "other_curve_2d")
            geometry["basis_curve"] = {
                "geometry_type": basis_geometry_type,
                **curve_2d_geometry(basis_curve, basis_geometry_type, depth + 1),
            }
    return compact(geometry)


def curve_2d_type_id(curve):
    curve_type_id = safe_attr(curve, "TypeId")
    if curve_type_id is not None:
        return curve_type_id
    geom_2d = safe_attr(Part, "Geom2d")
    if geom_2d is None:
        return None
    for class_name, canonical_type_id in CURVE_2D_CLASS_TYPE_IDS.items():
        curve_class = safe_attr(geom_2d, class_name)
        if curve_class is not None and curve.__class__ is curve_class:
            return canonical_type_id
    return None


def placement_geometry(placement) -> dict | None:
    if placement is None:
        return None
    base = safe_attr(placement, "Base")
    rotation = safe_attr(placement, "Rotation")
    quaternion = safe_attr(rotation, "Q") if rotation is not None else None
    result = compact(
        {
            "base": coordinates(base) if base is not None else None,
            "quaternion": [float(value) for value in quaternion] if quaternion is not None else None,
        }
    )
    return result or None


def edge_pcurves(edge) -> list[dict]:
    result = []
    method = safe_attr(edge, "curveOnSurface")
    if not callable(method):
        return result
    for index in range(64):
        try:
            item = method(index)
        except Exception as exc:
            result.append({"geometry_type": "invalid_curve_2d", "index": index, "error": str(exc)})
            break
        if item is None:
            break
        try:
            curve, surface, placement, first, last = item
            curve_type_id = curve_2d_type_id(curve)
            geometry_type = CURVE_2D_TYPE_IDS.get(curve_type_id, "other_curve_2d")
            result.append(
                {
                    "index": index,
                    "geometry_type": geometry_type,
                    "surface_type_id": safe_attr(surface, "TypeId"),
                    "parameter_range": [float(first), float(last)],
                    "placement": placement_geometry(placement),
                    **curve_2d_geometry(curve, geometry_type),
                }
            )
        except Exception as exc:
            result.append({"geometry_type": "invalid_curve_2d", "index": index, "error": str(exc)})
    return result


def face_geometry(face) -> tuple[str, dict]:
    surface = face.Surface
    name = surface.__class__.__name__.lower()
    if "plane" in name:
        return "plane", {"normal": vec(surface.Axis), "position": vec(surface.Position)}
    if "cylinder" in name:
        return "cylinder", {"radius": float(surface.Radius), "axis": vec(surface.Axis), "center": vec(surface.Center)}
    if "cone" in name:
        geometry = {
            "axis": attr_vec(surface, "Axis"),
            "apex": attr_vec(surface, "Apex"),
            "center": attr_vec(surface, "Center"),
            "semi_angle": attr_float(surface, "SemiAngle"),
        }
        radius1 = attr_float(surface, "Radius1")
        radius2 = attr_float(surface, "Radius2")
        if radius1 is not None:
            geometry["radius1"] = radius1
        if radius2 is not None:
            geometry["radius2"] = radius2
        return "cone", {key: value for key, value in geometry.items() if value is not None}
    if "sphere" in name:
        return "sphere", {"radius": float(surface.Radius), "center": vec(surface.Center)}
    if "torus" in name:
        return "torus", {
            "center": vec(surface.Center),
            "axis": vec(surface.Axis),
            "major_radius": float(surface.MajorRadius),
            "minor_radius": float(surface.MinorRadius),
        }
    if "bspline" in name or "b-spline" in name:
        return "bspline_surface", {"surface_class": surface.__class__.__name__}
    return "other", {"surface_class": surface.__class__.__name__}


# 用途：采样面方向、参数域、法向和主曲率；单项不可用时只省略该项，不中止整面解析。
def face_analysis_geometry(face) -> dict:
    result = {}
    orientation = safe_attr(face, "Orientation")
    if orientation is not None:
        result["orientation"] = str(orientation)
    parameter_bounds = safe_attr(face, "ParameterRange")
    try:
        uv_bounds = [float(value) for value in parameter_bounds]
    except (TypeError, ValueError):
        uv_bounds = None
    if uv_bounds and len(uv_bounds) == 4:
        result["uv_bounds"] = uv_bounds
        u_mid = (uv_bounds[0] + uv_bounds[1]) * 0.5
        v_mid = (uv_bounds[2] + uv_bounds[3]) * 0.5
        normal = safe_call(face, "normalAt", u_mid, v_mid)
        if normal is not None:
            try:
                result["normal_samples"] = [vec(normal)]
            except Exception:
                pass
        curvature = safe_call(face, "curvatureAt", u_mid, v_mid)
        if curvature is not None:
            try:
                result["curvature_samples"] = [[float(value) for value in curvature]]
            except (TypeError, ValueError):
                pass
    result["surface_type_raw"] = face.Surface.__class__.__name__
    return result


def edge_geometry(edge) -> tuple[str, dict]:
    try:
        curve = edge.Curve
    except Exception as exc:
        length = attr_float(edge, "Length")
        tolerance = attr_float(edge, "Tolerance") or DEGENERATE_LENGTH_TOLERANCE
        vertices = safe_attr(edge, "Vertexes") or []
        if length is not None and length <= max(DEGENERATE_LENGTH_TOLERANCE, tolerance) and len(vertices) <= 1:
            edge_range = parameter_range(edge)
            point = None
            if vertices:
                point_value = safe_attr(vertices[0], "Point")
                if point_value is not None:
                    point = coordinates(point_value)
            if point is None and edge_range:
                point = point_at(edge, edge_range[0])
            return "degenerate_edge", compact(
                {
                    "point": point,
                    "parameter_range": edge_range,
                    "pcurves": edge_pcurves(edge),
                    "curve_error": str(exc),
                }
            )
        return "invalid_curve", compact(
            {
                "error": str(exc),
                "parameter_range": parameter_range(edge),
                "sample_points": sample_edge(edge),
            }
        )

    curve_type_id = safe_attr(curve, "TypeId")
    geometry_type = CURVE_TYPE_IDS.get(curve_type_id, "other_curve")
    geometry = common_edge_geometry(edge, curve)
    if geometry_type == "other_curve":
        geometry["sample_points"] = sample_edge(edge)
    return geometry_type, compact(geometry)


def parser_version() -> str:
    version = getattr(FreeCAD, "Version", lambda: ["unknown"])()
    if isinstance(version, (list, tuple)):
        return ".".join(str(part) for part in version[:3])
    return str(version)


# 用途：从实际 Part 模块读取 OpenCascade 版本；不可用时如实返回 unknown。
def kernel_version() -> str:
    value = safe_attr(Part, "OCC_VERSION")
    return str(value) if value is not None else "unknown"


class TopologyIndex:
    def __init__(self, shapes):
        self.items = list(shapes)
        self.buckets: dict[int, list[tuple[int, object]]] = {}
        for index, shape in enumerate(self.items):
            self.buckets.setdefault(self._hash(shape), []).append((index, shape))

    def _hash(self, shape) -> int:
        try:
            return int(shape.hashCode())
        except Exception:
            return id(shape)

    def find(self, candidate):
        for index, shape in self.buckets.get(self._hash(candidate), []):
            try:
                if candidate.isSame(shape):
                    return index, shape
            except Exception:
                if candidate is shape:
                    return index, shape
        for index, shape in enumerate(self.items):
            try:
                if candidate.isSame(shape):
                    return index, shape
            except Exception:
                if candidate is shape:
                    return index, shape
        self.items.append(candidate)
        index = len(self.items) - 1
        self.buckets.setdefault(self._hash(candidate), []).append((index, candidate))
        return index, candidate


def tessellate_face(face, deflection: float) -> tuple[list[list[float]], list[list[int]]]:
    try:
        mesh = MeshPart.meshFromShape(Shape=face, LinearDeflection=deflection, AngularDeflection=0.5, Relative=False)
        points = [vec(point) for point in mesh.Points]
        triangles = []
        for facet in mesh.Facets:
            triangles.append([int(index) for index in facet.PointIndices])
        return points, triangles
    except Exception:
        try:
            points, triangles = face.tessellate(deflection)
            return [vec(point) for point in points], [[int(i) for i in tri] for tri in triangles]
        except Exception:
            return [], []


def add_entity(entities: list[dict], **kwargs) -> dict:
    entity = {
        "source_ref": None,
        "source_index": None,
        "name": None,
        "label": None,
        "sort_order": 0,
        "geometry_type": None,
        "area": None,
        "volume": None,
        "length": None,
        "center": None,
        "bounding_box": None,
        "placement": None,
        "geometry": {},
        "metadata": {},
        "fingerprint": None,
    }
    entity.update(kwargs)
    entities.append(entity)
    return entity


def relation(relations: list[dict], revision_id: str, source_id: str, target_id: str, relation_type: str, metadata=None) -> None:
    relations.append(
        {
            "id": stable_uuid(revision_id, "relation", source_id, target_id, relation_type),
            "revision_id": revision_id,
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "relation_type": relation_type,
            "metadata": metadata or {},
        }
    )


def parse(job: dict) -> dict:
    revision_id = job["revision_id"]
    source_path = Path(job["source_file_path"])
    deflection = float(job.get("mesh_deflection", 0.1))

    doc = FreeCAD.newDocument(f"cad_{revision_id.replace('-', '_')}")
    try:
        Import.insert(str(source_path), doc.Name)
        doc.recompute()

        entities: list[dict] = []
        relations: list[dict] = []
        meshes: list[dict] = []
        root_id = stable_uuid(revision_id, "root", "/root")
        add_entity(
            entities,
            id=root_id,
            revision_id=revision_id,
            parent_entity_id=None,
            entity_type="root",
            name=source_path.stem,
            label=source_path.name,
            tree_path="/root",
            metadata={"assembly_hierarchy_preserved": False},
        )

        face_entities: list[tuple[str, object]] = []
        edge_entities: list[tuple[str, object]] = []
        vertex_entities: list[tuple[str, object]] = []
        wire_entities: list[tuple[str, object]] = []
        shell_entities: list[tuple[str, object]] = []
        solid_count = 0
        object_boxes = []

        for object_index, obj in enumerate(doc.Objects):
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull():
                continue
            object_boxes.append(bbox(shape))
            object_id = stable_uuid(revision_id, "imported_object", object_index, obj.Name)
            object_path = f"/root/{object_index}"
            add_entity(
                entities,
                id=object_id,
                revision_id=revision_id,
                parent_entity_id=root_id,
                entity_type="imported_object",
                source_ref=obj.Name,
                source_index=object_index,
                name=obj.Name,
                label=getattr(obj, "Label", obj.Name),
                tree_path=object_path,
                sort_order=object_index,
                volume=float(getattr(shape, "Volume", 0.0) or 0.0),
                center=center(shape),
                bounding_box=bbox(shape),
                metadata={"assembly_hierarchy_preserved": False},
            )
            relation(relations, revision_id, root_id, object_id, "contains")

            solids = list(shape.Solids) or ([shape] if getattr(shape, "ShapeType", "") == "Solid" else [])
            for solid_index, solid in enumerate(solids):
                solid_count += 1
                solid_id = stable_uuid(revision_id, "solid", object_path, solid_index)
                solid_path = f"{object_path}/solid-{solid_index}"
                add_entity(
                    entities,
                    id=solid_id,
                    revision_id=revision_id,
                    parent_entity_id=object_id,
                    entity_type="solid",
                    source_ref=f"Solid{solid_index + 1}",
                    source_index=solid_index,
                    tree_path=solid_path,
                    sort_order=solid_index,
                    volume=float(getattr(solid, "Volume", 0.0) or 0.0),
                    center=center(solid),
                    bounding_box=bbox(solid),
                )
                relation(relations, revision_id, object_id, solid_id, "has_solid")

                solid_edge_index = TopologyIndex(solid.Edges)
                solid_vertex_index = TopologyIndex(solid.Vertexes)
                edge_ids: dict[int, str] = {}
                vertex_ids: dict[int, str] = {}

                for edge_index, edge in enumerate(solid_edge_index.items):
                    edge_ref = f"Edge{edge_index + 1}"
                    curve_type, edge_geom = edge_geometry(edge)
                    edge_id = stable_uuid(revision_id, "edge", solid_path, edge_ref)
                    edge_ids[edge_index] = edge_id
                    add_entity(
                        entities,
                        id=edge_id,
                        revision_id=revision_id,
                        parent_entity_id=solid_id,
                        entity_type="edge",
                        source_ref=edge_ref,
                        source_index=edge_index,
                        tree_path=f"{solid_path}/edge-{edge_index}",
                        sort_order=edge_index,
                        geometry_type=curve_type,
                        length=float(getattr(edge, "Length", 0.0) or 0.0),
                        center=center(edge),
                        bounding_box=bbox(edge),
                        geometry=edge_geom,
                    )
                    edge_entities.append((edge_id, edge))

                for vertex_index, vertex in enumerate(solid_vertex_index.items):
                    vertex_ref = f"Vertex{vertex_index + 1}"
                    vertex_id = stable_uuid(revision_id, "vertex", solid_path, vertex_ref)
                    vertex_ids[vertex_index] = vertex_id
                    add_entity(
                        entities,
                        id=vertex_id,
                        revision_id=revision_id,
                        parent_entity_id=solid_id,
                        entity_type="vertex",
                        source_ref=vertex_ref,
                        source_index=vertex_index,
                        tree_path=f"{solid_path}/vertex-{vertex_index}",
                        sort_order=vertex_index,
                        center=vec(vertex.Point),
                        geometry={"point": vec(vertex.Point)},
                    )
                    vertex_entities.append((vertex_id, vertex))

                for edge_index, edge in enumerate(solid_edge_index.items):
                    edge_id = edge_ids[edge_index]
                    for vertex in edge.Vertexes:
                        vertex_index, _ = solid_vertex_index.find(vertex)
                        if vertex_index not in vertex_ids:
                            vertex_ref = f"Vertex{vertex_index + 1}"
                            vertex_id = stable_uuid(revision_id, "vertex", solid_path, vertex_ref)
                            vertex_ids[vertex_index] = vertex_id
                            add_entity(
                                entities,
                                id=vertex_id,
                                revision_id=revision_id,
                                parent_entity_id=solid_id,
                                entity_type="vertex",
                                source_ref=vertex_ref,
                                source_index=vertex_index,
                                tree_path=f"{solid_path}/vertex-{vertex_index}",
                                sort_order=vertex_index,
                                center=vec(vertex.Point),
                                geometry={"point": vec(vertex.Point)},
                            )
                            vertex_entities.append((vertex_id, vertex))
                        relation(relations, revision_id, edge_id, vertex_ids[vertex_index], "has_vertex")
                        
                for face_index, face in enumerate(solid.Faces):
                    face_ref = f"Face{face_index + 1}"
                    geometry_type, geometry = face_geometry(face)
                    geometry.update(face_analysis_geometry(face))
                    face_id = stable_uuid(revision_id, "face", solid_path, face_ref, face_index)
                    face_path = f"{solid_path}/face-{face_index}"
                    add_entity(
                        entities,
                        id=face_id,
                        revision_id=revision_id,
                        parent_entity_id=solid_id,
                        entity_type="face",
                        source_ref=face_ref,
                        source_index=face_index,
                        tree_path=face_path,
                        sort_order=face_index,
                        geometry_type=geometry_type,
                        area=float(getattr(face, "Area", 0.0) or 0.0),
                        center=center(face),
                        bounding_box=bbox(face),
                        geometry=geometry,
                    )
                    face_entities.append((face_id, face))
                    relation(relations, revision_id, solid_id, face_id, "has_face")

                    positions, indices = tessellate_face(face, deflection)
                    meshes.append(
                        {
                            "id": stable_uuid(revision_id, "mesh", face_id),
                            "revision_id": revision_id,
                            "entity_id": face_id,
                            "mesh_type": "face",
                            "positions": positions,
                            "indices": indices,
                            "normals": None,
                            "color": None,
                            "linear_deflection": deflection,
                            "angular_deflection": 0.5,
                            "vertex_count": len(positions),
                            "triangle_count": len(indices),
                        }
                    )

                    for edge in face.Edges:
                        edge_index, _ = solid_edge_index.find(edge)
                        if edge_index not in edge_ids:
                            edge_ref = f"Edge{edge_index + 1}"
                            curve_type, edge_geom = edge_geometry(edge)
                            edge_id = stable_uuid(revision_id, "edge", solid_path, edge_ref)
                            edge_ids[edge_index] = edge_id
                            add_entity(
                                entities,
                                id=edge_id,
                                revision_id=revision_id,
                                parent_entity_id=solid_id,
                                entity_type="edge",
                                source_ref=edge_ref,
                                source_index=edge_index,
                                tree_path=f"{solid_path}/edge-{edge_index}",
                                sort_order=edge_index,
                                geometry_type=curve_type,
                                length=float(getattr(edge, "Length", 0.0) or 0.0),
                                center=center(edge),
                                bounding_box=bbox(edge),
                                geometry=edge_geom,
                            )
                            edge_entities.append((edge_id, edge))
                        relation(relations, revision_id, face_id, edge_ids[edge_index], "bounded_by_edge")

                    # 每个 Wire 作为独立拓扑节点保留，后续开口环和岛屿分析不再依赖边列表猜测。
                    for wire_index, wire in enumerate(safe_attr(face, "Wires") or []):
                        wire_id = stable_uuid(revision_id, "wire", face_id, wire_index)
                        closed = safe_call(wire, "isClosed")
                        if closed is None:
                            closed = attr_bool(wire, "Closed")
                        add_entity(
                            entities,
                            id=wire_id,
                            revision_id=revision_id,
                            parent_entity_id=face_id,
                            entity_type="wire",
                            source_ref=f"Wire{wire_index + 1}",
                            source_index=wire_index,
                            tree_path=f"{face_path}/wire-{wire_index}",
                            sort_order=wire_index,
                            geometry_type="closed_wire" if closed else "open_wire",
                            length=float(getattr(wire, "Length", 0.0) or 0.0),
                            center=center(wire),
                            bounding_box=bbox(wire),
                            geometry={"closed": bool(closed)},
                        )
                        wire_entities.append((wire_id, wire))
                        relation(relations, revision_id, face_id, wire_id, "has_wire")
                        for wire_edge in wire.Edges:
                            wire_edge_index, _ = solid_edge_index.find(wire_edge)
                            if wire_edge_index in edge_ids:
                                relation(relations, revision_id, wire_id,
                                         edge_ids[wire_edge_index], "contains_edge")

                # Shell 在 Face 之后建立，便于通过同一实体对象反查已分配的面编号。
                solid_face_index = TopologyIndex(solid.Faces)
                face_ids_by_index = {
                    face_index: stable_uuid(revision_id, "face", solid_path,
                                            f"Face{face_index + 1}", face_index)
                    for face_index in range(len(solid.Faces))
                }
                for shell_index, shell in enumerate(safe_attr(solid, "Shells") or []):
                    shell_id = stable_uuid(revision_id, "shell", solid_id, shell_index)
                    add_entity(
                        entities,
                        id=shell_id,
                        revision_id=revision_id,
                        parent_entity_id=solid_id,
                        entity_type="shell",
                        source_ref=f"Shell{shell_index + 1}",
                        source_index=shell_index,
                        tree_path=f"{solid_path}/shell-{shell_index}",
                        sort_order=shell_index,
                        geometry_type="closed_shell" if safe_call(shell, "isClosed") else "open_shell",
                        area=float(getattr(shell, "Area", 0.0) or 0.0),
                        center=center(shell),
                        bounding_box=bbox(shell),
                    )
                    shell_entities.append((shell_id, shell))
                    relation(relations, revision_id, solid_id, shell_id, "has_shell")
                    for shell_face in shell.Faces:
                        shell_face_index, _ = solid_face_index.find(shell_face)
                        if shell_face_index in face_ids_by_index:
                            relation(relations, revision_id, shell_id,
                                     face_ids_by_index[shell_face_index], "contains_face")

        # 用途：只有共享真实几何边的面才建立邻接，避免仅凭空间接近产生伪邻接。
        for left_index, (left_id, left_face) in enumerate(face_entities):
            left_hashes = {edge.hashCode() for edge in left_face.Edges}
            for right_id, right_face in face_entities[left_index + 1 :]:
                if left_hashes.intersection(edge.hashCode() for edge in right_face.Edges):
                    relation(relations, revision_id, left_id, right_id, "adjacent_to")
                    relation(relations, revision_id, right_id, left_id, "adjacent_to")

        return {
            "revision_id": revision_id,
            "parser_name": "FreeCAD",
            "parser_version": parser_version(),
            "kernel_name": "OpenCascade",
            "kernel_version": kernel_version(),
            "schema_version": SCHEMA_VERSION,
            "unit": "mm",
            "bounding_box": union_bbox(object_boxes),
            "summary": {
                "object_count": len(doc.Objects),
                "solid_count": solid_count,
                "face_count": len(face_entities),
                "edge_count": len(edge_entities),
                "vertex_count": len(vertex_entities),
                "wire_count": len(wire_entities),
                "shell_count": len(shell_entities),
            },
            "entities": entities,
            "relations": relations,
            "meshes": meshes,
            "parse_manifest": {
                "source_file_name": source_path.name,
                "mesh_deflection": deflection,
                "assembly_hierarchy_preserved": False,
            },
        }
    finally:
        FreeCAD.closeDocument(doc.Name)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: parse_step.py <job.json>", file=sys.stderr)
        return 2
    job_path = Path(sys.argv[1])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    result = parse(job)
    Path(job["result_json_path"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
