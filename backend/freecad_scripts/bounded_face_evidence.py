"""Finite B-Rep point membership used by parser and interactive queries."""

from __future__ import annotations

import FreeCAD
import Part


def solid_line_material_intervals(solid, start, end):
    """Exact material intervals along one finite line, measured from start."""
    direction = end-start
    length = direction.Length
    if length <= 1e-9:
        return []
    direction.normalize()
    intervals = []
    for edge in solid.common(Part.makeLine(start, end)).Edges:
        scalars = sorted((vertex.Point-start).dot(direction) for vertex in edge.Vertexes)
        if len(scalars) == 2 and scalars[1]-scalars[0] > 1e-7:
            intervals.append(scalars)
    return sorted(intervals)


def trimmed_face_point_status(face, point, tolerance):
    """Classify a point against the trimmed face, including inner wires."""
    vertex = Part.Vertex(point)
    residual = float(face.distToShape(vertex)[0])
    if residual > tolerance:
        status = "outside"
        edge_residual = None
    else:
        edge_residual = min((float(edge.distToShape(vertex)[0]) for edge in face.Edges), default=None)
        status = "boundary" if edge_residual is not None and edge_residual <= tolerance else "inside"
    return {"status": status, "residual_mm": residual,
            "boundary_residual_mm": edge_residual,
            "method": "trimmed_face_and_finite_boundary_distance"}


def cylinder_end_boundaries(wall_id, wall_entity, face_shapes, face_edge_ids,
                            edge_faces, edge_entities, face_entities, tolerance):
    """Return only faces sharing a real circular end edge with this wall."""
    geometry = wall_entity["geometry"]
    evidence = geometry.get("recognition_evidence") or {}
    axial = evidence.get("axial_range_mm")
    if not isinstance(axial, list) or len(axial) != 2:
        return [[], []]
    origin = FreeCAD.Vector(*geometry["center"])
    axis = FreeCAD.Vector(*evidence["axis_unit"])
    results = []
    for scalar in axial:
        point = origin+axis*float(scalar)
        neighbors = []
        for edge_id in face_edge_ids[wall_id]:
            edge = edge_entities[edge_id]
            if edge.get("geometry_type") != "circle":
                continue
            edge_center = FreeCAD.Vector(*edge["center"])
            if abs((edge_center-origin).dot(axis)-scalar) > tolerance:
                continue
            for neighbor_id in edge_faces[edge_id]:
                if neighbor_id == wall_id:
                    continue
                neighbor = face_entities[neighbor_id]
                item = {"face_id": neighbor_id, "shared_edge_id": edge_id,
                        "geometry_type": neighbor.get("geometry_type")}
                if neighbor.get("geometry_type") == "plane":
                    item["axis_point_location"] = trimmed_face_point_status(
                        face_shapes[neighbor_id], point, tolerance)
                elif neighbor.get("geometry_type") == "cone":
                    item["apex_mm"] = (neighbor.get("geometry") or {}).get("apex")
                neighbors.append(item)
        results.append(sorted(neighbors, key=lambda item: (item["face_id"], item["shared_edge_id"])))
    return results


def trimmed_face_interior_points(face, tolerance, max_triangles=64):
    """Bounded representative points; never assume CenterOfMass lies on the face."""
    candidates = [face.CenterOfMass]
    vertices, triangles = face.tessellate(max(0.1, tolerance*20))
    ranked = []
    for triangle in triangles:
        a, b, c = (vertices[index] for index in triangle)
        area = (b-a).cross(c-a).Length
        ranked.append((-area, tuple(sorted(triangle)), (a, b, c)))
    ranked.sort(key=lambda item: (item[0], item[1]))
    for _, _, (a, b, c) in ranked[:max_triangles]:
        candidates.extend(((a+b+c)/3, (a*0.6+b*0.2+c*0.2),
                           (a*0.2+b*0.6+c*0.2), (a*0.2+b*0.2+c*0.6)))
    valid = []
    for point in candidates:
        location = trimmed_face_point_status(face, point, tolerance)
        if location["status"] != "inside":
            continue
        margin = location["boundary_residual_mm"] or 0.0
        if margin <= tolerance*2:
            continue
        valid.append((-margin, point.x, point.y, point.z, point))
    valid.sort(key=lambda item: item[:4])
    return [item[4] for item in valid[:max_triangles]]
