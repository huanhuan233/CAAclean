"""Structural-role proposals over exact same-Solid thin-wall measurements."""

from __future__ import annotations

from typing import Any

from .contracts import CanonicalFeature
from .eaag import EaagGraph


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def _edge_lengths(graph: EaagGraph, face_id: str) -> list[float]:
    return sorted((float(graph.entities[edge_id].get("length") or 0)
                   for edge_id in graph.face_edge_ids(face_id)
                   if graph.entities[edge_id].get("geometry_type") == "line"), reverse=True)


def structural_proposals(graph: EaagGraph, solid_id: str, face_ids: list[str],
                         thin_pairs: list[dict[str, Any]],
                         existing: list[CanonicalFeature], tolerance: float) -> list[dict[str, Any]]:
    """Separate confirmed thin geometry from tentative engineering function."""
    faces = set(face_ids)
    rectangular_bosses = [feature for feature in existing
                          if feature.family == "boss" and feature.subtype == "rectangular_straight_wall"
                          and feature.geometry_refs.solid_ids == [solid_id]]
    proposals = []
    flange_pairs: set[tuple[str, str]] = set()
    valid_pairs = [pair for pair in thin_pairs if pair.get("solid_id") == solid_id and
                   {pair.get("face_a_id"), pair.get("face_b_id")}.issubset(faces)]
    for index, first in enumerate(valid_pairs):
        a_faces = {first["face_a_id"], first["face_b_id"]}
        for second in valid_pairs[index+1:]:
            b_faces = {second["face_a_id"], second["face_b_id"]}
            shared = a_faces.intersection(b_faces)
            if len(shared) != 1 or abs(float(first["thickness_mm"])-float(second["thickness_mm"])) > tolerance:
                continue
            if abs(_dot(first["direction"], second["direction"])) < 1-1e-3:
                continue
            cap_id = next(iter(shared))
            under_ids = sorted((a_faces | b_faces)-shared)
            cap = graph.entities[cap_id]
            if float(cap.get("area") or 0) <= sum(float(graph.entities[face_id].get("area") or 0) for face_id in under_ids):
                continue
            web_pair = next((pair for pair in valid_pairs
                             if pair is not first and pair is not second and
                             abs(_dot(pair["direction"], first["direction"])) < 1e-3 and
                             all(any(web_face in graph.face_neighbors(under_id)
                                     for web_face in (pair["face_a_id"], pair["face_b_id"]))
                                 for under_id in under_ids)), None)
            if web_pair is None:
                continue
            lengths = _edge_lengths(graph, cap_id)
            if len(lengths) != 4 or lengths[-1] <= float(first["thickness_mm"]):
                continue
            thickness = float(first["thickness_mm"])
            flange_pairs.update((tuple(sorted(a_faces)), tuple(sorted(b_faces))))
            proposals.append({
                "family": "flange", "subtype": "straight_free_edge_band_candidate",
                "roles": {"flange_web": [cap_id] + under_ids,
                          "web_support_reference": [web_pair["face_a_id"], web_pair["face_b_id"]]},
                "payload": {"length_mm": lengths[0], "width_mm": lengths[-1],
                            "local_thickness_mm": thickness, "free_edge_face_ids": under_ids,
                            "connected_web_face_ids": sorted([web_pair["face_a_id"], web_pair["face_b_id"]]),
                            "thickness_method": first["method"],
                            "geometry_form_status": "confirmed", "structural_role_status": "candidate",
                            "render_range_status": "candidate_full_band_faces"},
                "frame": {"origin_mm": first["start_point_mm"], "normal": first["direction"],
                          "axis_selection": "finite_band_edges_and_opposed_planes"},
                "measures": [("length", lengths[0], "mm", "finite_band_edge_length"),
                             ("width", lengths[-1], "mm", "finite_band_edge_length"),
                             ("local_thickness", thickness, "mm", first["method"])],
                "relations": [], "diagnostics": ["FLANGE_FUNCTIONAL_ROLE_NOT_UNIQUELY_PROVEN"],
            })
            break
    seen = set()
    for pair in valid_pairs:
        pair_faces = {pair.get("face_a_id"), pair.get("face_b_id")}
        if pair.get("solid_id") != solid_id or not pair_faces.issubset(faces) or len(pair_faces) != 2:
            continue
        key = tuple(sorted(pair_faces))
        if key in seen or key in flange_pairs:
            continue
        seen.add(key)
        thickness = float(pair["thickness_mm"])
        if thickness <= tolerance or pair.get("method") != "trimmed_plane_projection_and_exact_solid_segment_intersection_v2":
            continue
        parent = next((feature for feature in rectangular_bosses
                       if pair_faces.issubset(set(feature.typed_payload["geometry_recognition"]["wall_face_ids"]))), None)
        if parent is not None:
            boss = parent.typed_payload["geometry_recognition"]
            if abs(thickness-float(boss["width_mm"])) > tolerance or float(boss["length_mm"]) < 4*thickness:
                continue
            family, subtype = "rib", "straight_prismatic_candidate"
            roles = {"rib_web": sorted(pair_faces),
                     "top_reference": [boss["cap_face_id"]],
                     "root_reference": [boss["support_face_id"]]}
            payload = {
                "length_mm": boss["length_mm"], "local_thickness_mm": thickness,
                "height_mm": boss["height_mm"], "thickness_start_mm": pair["start_point_mm"],
                "thickness_end_mm": pair["end_point_mm"], "thickness_direction": pair["direction"],
                "material_interval_mm": pair["material_interval_mm"],
                "thickness_method": pair["method"],
                "thin_wall_pair_id": pair.get("pair_id"),
                "thickness_scope": pair.get("coverage_status"),
                "length_definition": "finite_top_edge_projection_in_parent_boss_frame",
                "height_definition": "parent_cap_to_root_support_plane",
                "root_support_face_id": boss["support_face_id"],
                "parent_geometry_feature_id": parent.feature_center_id,
                "geometry_form_status": "confirmed", "structural_role_status": "candidate",
                "render_range_status": "candidate_full_side_faces",
            }
            measures = [("length", float(boss["length_mm"]), "mm", "finite_top_edge_projection"),
                        ("local_thickness", thickness, "mm", pair["method"]),
                        ("height", float(boss["height_mm"]), "mm", "cap_root_plane_distance")]
            frame = parent.coordinate_frame
            relations = [{"kind": "STRUCTURAL_ROLE_OF", "target_id": parent.feature_center_id}]
            diagnostics = ["RIB_FUNCTIONAL_ROLE_NOT_UNIQUELY_PROVEN"]
        else:
            lengths = _edge_lengths(graph, pair["face_a_id"])
            if len(lengths) < 4 or lengths[0] < 4*thickness or lengths[-1] < 1.5*thickness-tolerance:
                continue
            family, subtype = "web", "thin_plate_candidate"
            roles = {"web_side": sorted(pair_faces)}
            payload = {
                "local_thickness_mm": thickness,
                "thickness_start_mm": pair["start_point_mm"],
                "thickness_end_mm": pair["end_point_mm"], "thickness_direction": pair["direction"],
                "material_interval_mm": pair["material_interval_mm"],
                "thickness_method": pair["method"],
                "thin_wall_pair_id": pair.get("pair_id"),
                "thickness_scope": pair.get("coverage_status"),
                "bounded_face_edge_lengths_mm": lengths,
                "geometry_form_status": "confirmed", "structural_role_status": "candidate",
                "render_range_status": "candidate_full_opposed_faces",
            }
            measures = [("local_thickness", thickness, "mm", pair["method"])]
            frame = {"origin_mm": pair["start_point_mm"], "normal": pair["direction"],
                     "axis_selection": "opposed_trimmed_plane_normals"}
            relations = []
            diagnostics = ["WEB_LOAD_BEARING_ROLE_NOT_UNIQUELY_PROVEN"]
        proposals.append({"family": family, "subtype": subtype, "roles": roles,
                          "payload": payload, "frame": frame, "measures": measures,
                          "relations": relations, "diagnostics": diagnostics})
    return proposals
