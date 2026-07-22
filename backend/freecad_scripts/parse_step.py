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


SCHEMA_VERSION = "cad_parse_v2"
NAMESPACE = uuid.UUID("8c5fe5cc-91cb-4f13-8d1c-2a6e3ef93349")


def stable_uuid(revision_id: str, *parts: object) -> str:
    key = ":".join(str(part) for part in (revision_id, *parts))
    return str(uuid.uuid5(NAMESPACE, key))


def vec(value) -> list[float]:
    return [float(value.x), float(value.y), float(value.z)]


def bbox(shape) -> dict:
    box = shape.BoundBox
    return {
        "min": [float(box.XMin), float(box.YMin), float(box.ZMin)],
        "max": [float(box.XMax), float(box.YMax), float(box.ZMax)],
    }


def union_bbox(boxes: list[dict]) -> dict | None:
    if not boxes:
        return None
    return {
        "min": [min(box["min"][axis] for box in boxes) for axis in range(3)],
        "max": [max(box["max"][axis] for box in boxes) for axis in range(3)],
    }


def center(shape):
    try:
        return vec(shape.CenterOfMass)
    except Exception:
        return None


def attr_vec(value, *names):
    for name in names:
        candidate = getattr(value, name, None)
        if candidate is not None:
            return vec(candidate)
    return None


def attr_float(value, *names):
    for name in names:
        candidate = getattr(value, name, None)
        if candidate is not None:
            try:
                return float(candidate)
            except Exception:
                return None
    return None


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


def edge_geometry(edge) -> tuple[str, dict]:
    curve = edge.Curve
    name = curve.__class__.__name__.lower()
    if "line" in name:
        return "line", {}
    if "circle" in name:
        geometry = {"radius": float(curve.Radius), "center": vec(curve.Center), "axis": attr_vec(curve, "Axis")}
        return "circle", {key: value for key, value in geometry.items() if value is not None}
    if "ellipse" in name:
        return "ellipse", {}
    if "bspline" in name:
        return "bspline_curve", {}
    return "other", {"curve_class": curve.__class__.__name__}


def parser_version() -> str:
    version = getattr(FreeCAD, "Version", lambda: ["unknown"])()
    if isinstance(version, (list, tuple)):
        return ".".join(str(part) for part in version[:3])
    return str(version)


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

        # Conservative adjacency: faces sharing at least one geometric edge object.
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
            "schema_version": SCHEMA_VERSION,
            "unit": "mm",
            "bounding_box": union_bbox(object_boxes),
            "summary": {
                "object_count": len(doc.Objects),
                "solid_count": solid_count,
                "face_count": len(face_entities),
                "edge_count": len(edge_entities),
                "vertex_count": len(vertex_entities),
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
