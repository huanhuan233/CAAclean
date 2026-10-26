# 圆截面空心直管/弯管的解析几何核验，不依赖原生 Hole 或扫掠节点。
# 长度和半径使用毫米；输出面索引仅指当前 Solid 的 B-Rep Faces（从 1 起），不是 Viewer 面 ID。
# 流程：分裂壁归组 → 内外壁配对 → 有序中心线 → 端口/体积/截面材料侧核验。

"""Finite analytic pipe walls, topology, material and section verification.

All indices refer to the loaded Solid's B-Rep Faces (one based), never a viewer
mesh. Circular cross-section splits are grouped without modifying the source.
"""
from __future__ import annotations

import math

import FreeCAD as App
import Part

from measure_geometry import xyz

MAX_SEGMENTS = 48
# 避开段端的接缝/端口；三个站位分别检查该解析段的前部、中部和后部。
SAMPLE_FRACTIONS = (0.2, 0.5, 0.8)
# 使用单位切向点积的残差，不是毫米距离容差。
TANGENT_RESIDUAL_MAX = 1e-7


# 表示几何不在当前可证明范围内；分类入口将其转换为 unsupported_geometry 及具体原因。
class TubeUnsupported(ValueError):
    pass


# 统一检查几何必要条件，失败时保留可追踪的机器诊断码。
def require(condition, reason):
    if not condition:
        raise TubeUnsupported(reason)


# 以三维欧氏距离判断两个点是否在毫米容差内，不依赖逐坐标四舍五入。
def close(a, b, tol):
    return (a - b).Length <= tol


# 归一化非零向量；调用方须保证方向存在，不能把零向量当有效轴线。
def unit(v):
    return v / v.Length


# 用内核拓扑身份去重共享边，不以坐标接近合并不同实体边。
def unique_edges(faces):
    edges = []
    for face in faces:
        for edge in face.Edges:
            if not any(edge.isSame(other) for other in edges):
                edges.append(edge)
    return edges


# 沿真实共享边扩展连通面组，确认分裂壁不是空间靠近但互不连接的几块面。
def connected_faces(faces):
    reached = {0}
    while True:
        following = {i for i, face in enumerate(faces) if i not in reached and any(
            a.isSame(b) for j in reached for a in face.Edges for b in faces[j].Edges)}
        if not following:
            return len(reached) == len(faces)
        reached.update(following)


# 检查两个面组是否共享至少一条真实拓扑边，作为壁段及端面连接证据。
def shares_edge(first, second):
    return any(a.isSame(b) for f in first for g in second for a in f.Edges for b in g.Edges)


# 将共享边且共面的端面碎片归组，保持所有原始面索引，不修改源实体。
def cap_groups(caps, tol):
    groups = []
    remaining = list(caps)
    while remaining:
        index, face = remaining.pop(0)
        indices, faces = [index], [face]
        while True:
            found = [item for item in remaining if shares_edge(faces, [item[1]]) and
                     abs(unit(face.Surface.Axis).dot(unit(item[1].Surface.Axis))) >= 1 - TANGENT_RESIDUAL_MAX and
                     abs((item[1].CenterOfMass - face.CenterOfMass).dot(unit(face.Surface.Axis))) <= tol]
            if not found:
                break
            for item in found:
                remaining.remove(item)
                indices.append(item[0])
                faces.append(item[1])
        groups.append((indices, faces))
    return groups


# 比较类型、有限端点和中点；允许方向相反，避免同一段因轴向符号不同被拆成两个对象。
def centerline_matches(a, b, tol):
    return (a['kind'] == b['kind'] and close(a['mid'], b['mid'], tol) and
            ((close(a['a'], b['a'], tol) and close(a['b'], b['b'], tol)) or
             (close(a['a'], b['b'], tol) and close(a['b'], b['a'], tol))))


# 从圆柱/圆环面的两个实际圆形端边恢复有限中心线，记录壁半径及原始面。
# 圆环大半径对应中心线弯曲半径，小半径对应管壁所在圆截面半径，两者不能混用。
def wall_fragment(face, index, tol):
    surface = face.Surface
    kind = type(surface).__name__
    require(kind in {'Cylinder', 'Toroid'}, 'non_analytic_or_non_circular_wall')
    require(len(face.Wires) == 1, 'wall_has_extra_trim_loop')
    radius = float(surface.Radius if kind == 'Cylinder' else surface.MinorRadius)
    axis = unit(surface.Axis)
    origin = surface.Center
    require(radius > tol, 'wall_radius_below_tolerance')
    rings = []
    for edge in face.Edges:
        curve = edge.Curve
        if type(curve).__name__ != 'Circle' or abs(curve.Radius - radius) > tol:
            continue
        center = curve.Center
        radial = center - origin
        if kind == 'Cylinder':
            valid = (radial - axis * radial.dot(axis)).Length <= tol and abs(unit(curve.Axis).dot(axis)) > 1 - TANGENT_RESIDUAL_MAX
        else:
            valid = (abs(radial.Length - surface.MajorRadius) <= tol and abs(radial.dot(axis)) <= tol and
                     abs(unit(curve.Axis).dot(unit(axis.cross(radial)))) > 1 - TANGENT_RESIDUAL_MAX)
        if valid and not any(close(center, other, tol) for other in rings):
            rings.append(center)
    require(len(rings) == 2 and not close(*rings, tol), 'two_finite_cross_section_boundaries_required')
    a, b = rings
    if kind == 'Cylinder':
        mid = (a + b) * 0.5
        edge = Part.makeLine(a, b)
    else:
        require(surface.MajorRadius > radius + tol, 'self_overlapping_torus_section')
        u0, u1, _, _ = face.ParameterRange
        require(0 < u1 - u0 < 2 * math.pi - 1e-7, 'closed_or_degenerate_bend')
        # Opposite tube-circle points cancel its minor radius, regardless of
        # whether this face contains only half of that cross-section.
        mid = (face.valueAt((u0 + u1) / 2, 0) + face.valueAt((u0 + u1) / 2, math.pi)) * 0.5
        edge = Part.Arc(a, mid, b).toShape()
        require(abs(edge.Curve.Radius - surface.MajorRadius) <= tol, 'bend_support_inconsistent')
    return dict(kind='line' if kind == 'Cylinder' else 'arc', a=a, b=b, mid=mid,
                edge=edge, radius=radius, faces=[face], indices=[index])


# 遍历单实体并归组同半径同路径的壁片；用面积和端部整周周长核验完整覆盖。
def walls(solid, tol):
    groups, caps = [], []
    for index, face in enumerate(solid.Faces, 1):
        if type(face.Surface).__name__ == 'Plane':
            caps.append((index, face))
            continue
        item = wall_fragment(face, index, tol)
        matches = [g for g in groups if abs(g['radius'] - item['radius']) <= tol and centerline_matches(g, item, tol)]
        require(len(matches) <= 1, 'ambiguous_wall_group')
        if matches:
            matches[0]['faces'].extend(item['faces'])
            matches[0]['indices'].extend(item['indices'])
        else:
            groups.append(item)
    caps = cap_groups(caps, tol)
    require(len(caps) == 2, 'two_annular_terminal_faces_required')
    for group in groups:
        require(connected_faces(group['faces']), 'disconnected_split_wall')
        radius, length = group['radius'], group['edge'].Length
        expected = 2 * math.pi * radius * length
        require(abs(sum(f.Area for f in group['faces']) - expected) <= max(tol * tol, expected * 1e-6),
                'incomplete_or_overlapping_wall_coverage')
        edges = unique_edges(group['faces'])
        for center in (group['a'], group['b']):
            perimeter = sum(e.Length for e in edges if type(e.Curve).__name__ == 'Circle' and
                            abs(e.Curve.Radius - radius) <= tol and close(e.Curve.Center, center, tol))
            require(abs(perimeter - 2 * math.pi * radius) <= max(tol, radius * 1e-6), 'incomplete_section_boundary')
    return groups, caps


# 每段必须有唯一同路径内外壁配对，壁厚大于容差，所有段截面半径在容差内一致。
def pair_walls(groups, tol):
    used, pairs = set(), []
    for i, group in enumerate(groups):
        if i in used:
            continue
        matches = [(j, other) for j, other in enumerate(groups) if j != i and centerline_matches(group, other, tol)]
        require(len(matches) == 1, 'inner_outer_wall_pair_not_unique')
        j, other = matches[0]
        require(j not in used, 'wall_used_by_multiple_segments')
        outer, inner = sorted((group, other), key=lambda item: item['radius'], reverse=True)
        require(outer['radius'] - inner['radius'] > tol, 'wall_thickness_below_tolerance')
        pairs.append(dict(outer=outer, inner=inner))
        used.update((i, j))
    require(1 <= len(pairs) <= MAX_SEGMENTS, 'segment_budget_or_empty_path')
    ro, ri = pairs[0]['outer']['radius'], pairs[0]['inner']['radius']
    require(all(abs(p['outer']['radius'] - ro) <= tol and abs(p['inner']['radius'] - ri) <= tol for p in pairs),
            'varying_section_not_supported')
    return pairs, ro, ri


# 按端点构建不分叉开放路径，从确定性起点排序并核验相切与内外壁共享边。
# 累计站位 s0/s1 是沿中心线的弧长；排序方向是几何约定，不表示机床进料方向。
def ordered_segments(pairs, tol):
    nodes, incidences = [], []
    for i, pair in enumerate(pairs):
        vertices = []
        for point in (pair['outer']['a'], pair['outer']['b']):
            matches = [j for j, existing in enumerate(nodes) if close(point, existing, tol)]
            require(len(matches) <= 1, 'ambiguous_path_junction')
            if not matches:
                matches = [len(nodes)]
                nodes.append(point)
                incidences.append([])
            vertices.append(matches[0])
            incidences[matches[0]].append(i)
        pair['vertices'] = vertices
    ends = [i for i, connected in enumerate(incidences) if len(connected) == 1]
    require(len(ends) == 2 and all(len(c) in {1, 2} for c in incidences), 'closed_or_branched_path')
    current = min(ends, key=lambda i: tuple(xyz(nodes[i])))
    visited, segments, last_pair, last_tangent = set(), [], None, None
    station = 0.0
    while True:
        choices = [i for i in incidences[current] if i not in visited]
        if not choices:
            break
        require(len(choices) == 1, 'branched_path')
        index = choices[0]
        pair = pairs[index]
        following = next(v for v in pair['vertices'] if v != current)
        a, b, mid = nodes[current], nodes[following], pair['outer']['mid']
        kind = pair['outer']['kind']
        edge = Part.makeLine(a, b) if kind == 'line' else Part.Arc(a, mid, b).toShape()
        t0, t1 = edge.tangentAt(edge.FirstParameter), edge.tangentAt(edge.LastParameter)
        if last_pair is not None:
            require(last_tangent.dot(t0) >= 1 - TANGENT_RESIDUAL_MAX, 'non_tangent_segment_junction')
            for side in ('outer', 'inner'):
                require(shares_edge(last_pair[side]['faces'], pair[side]['faces']), 'wall_junction_not_topologically_connected')
        item = dict(kind=kind, start_mm=xyz(a), end_mm=xyz(b), length_mm=edge.Length,
                    tangent_start=xyz(t0), tangent_end=xyz(t1), s0_mm=station, s1_mm=station + edge.Length,
                    order=len(segments) + 1, source_id='brep-segment:' + str(len(segments) + 1),
                    outer_face_indices=pair['outer']['indices'], inner_face_indices=pair['inner']['indices'])
        if kind == 'arc':
            item.update(center_mm=xyz(edge.Curve.Center), plane_normal=xyz(edge.Curve.Axis),
                        radius_mm=edge.Curve.Radius, bend_deg=math.degrees(edge.Length / edge.Curve.Radius))
        segments.append((item, edge, pair))
        station += edge.Length
        visited.add(index)
        current, last_pair, last_tangent = following, pair, t1
    require(len(visited) == len(pairs), 'disconnected_path_components')
    return segments


# 把两个端面组匹配到有序路径 A/B 端，核验内外圆周、环形面积、壁连接及外法向。
def verify_ends(caps, segments, ro, ri, tol, coordinates):
    result = []
    for role, (item, edge, pair), end_name in (('A', segments[0], 'start_mm'), ('B', segments[-1], 'end_mm')):
        center = App.Vector(*item[end_name])
        matches = []
        for indices, faces in caps:
            face = faces[0]
            # 同一端面组内部共享的分割边不能计入内外圆周，否则会把半环分割缝当端口。
            # Internal split seams occur on two cap fragments, not the annulus boundary.
            edges = [e for e in unique_edges(faces) if sum(any(e.isSame(x) for x in f.Edges) for f in faces) == 1]
            if not all(type(e.Curve).__name__ == 'Circle' and close(e.Curve.Center, center, tol) for e in edges):
                continue
            require(all(min(abs(e.Curve.Radius - ro), abs(e.Curve.Radius - ri)) <= tol for e in edges), 'terminal_radius_mismatch')
            for radius in (ro, ri):
                require(abs(sum(e.Length for e in edges if abs(e.Curve.Radius - radius) <= tol) - 2 * math.pi * radius) <= tol,
                        'terminal_not_complete_annulus')
            area = math.pi * (ro * ro - ri * ri)
            require(abs(sum(f.Area for f in faces) - area) <= max(tol * tol, area * 1e-6), 'terminal_not_annular')
            require(all(shares_edge(faces, pair[side]['faces']) for side in ('outer', 'inner')), 'terminal_wall_not_connected')
            u0, u1, v0, v1 = face.ParameterRange
            normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            tangent = App.Vector(*(item['tangent_start'] if role == 'A' else item['tangent_end']))
            require(normal.dot(tangent) * (-1 if role == 'A' else 1) >= 1 - TANGENT_RESIDUAL_MAX, 'terminal_material_orientation_mismatch')
            matches.append(dict(role=role, kind='flat', position_mm=xyz(center), plane_normal=xyz(normal),
                                face_indices=indices, station_s_mm=item['s0_mm'] if role == 'A' else item['s1_mm'],
                                boundary_radii_mm=[ri, ro], evidence='analytic_annular_planar_face', coordinate_system=coordinates))
        require(len(matches) == 1, 'terminal_face_not_unique')
        result.extend(matches)
    require(not set(result[0]['face_indices']).intersection(result[1]['face_indices']), 'terminal_identity_collision')
    return result


# 每段在 20%、50%、80% 站位作法向截面，核验内外圆周及八个径向材料探针。
# 采样用于验证解析支撑及内核截线的一致性，不是实物减薄/椭圆化测量。
def verify_sections(solid, segments, ro, ri, tol, coordinates):
    samples = []
    for item, edge, pair in segments:
        for fraction in SAMPLE_FRACTIONS:
            parameter = edge.FirstParameter + fraction * (edge.LastParameter - edge.FirstParameter)
            center, normal = edge.valueAt(parameter), unit(edge.tangentAt(parameter))
            disk = Part.Face(Part.Wire(Part.makeCircle(ro * 1.05, center, normal)))
            section = solid.section(disk)
            perimeters = [0.0, 0.0]
            residual = 0.0
            curve_kinds = set()
            require(bool(section.Edges), 'empty_local_cross_section')
            for boundary in section.Edges:
                curve = boundary.Curve
                curve_kinds.add(type(curve).__name__)
                if type(curve).__name__ == 'Circle':
                    offset = (curve.Center - center).Length
                    require(offset <= tol and abs(unit(curve.Axis).dot(normal)) >= 1 - TANGENT_RESIDUAL_MAX,
                            'local_section_center_or_normal_mismatch')
                    nearest = min(range(2), key=lambda i: abs(curve.Radius - (ro, ri)[i]))
                    error = max(offset, abs(curve.Radius - (ro, ri)[nearest]))
                else:
                    # OCC may approximate a torus/plane intersection as a spline
                    # after rigid transforms. Analytic wall supports already prove
                    # the circle; verify the returned finite representation too.
                    points = [boundary.valueAt(boundary.FirstParameter + k / 32 *
                              (boundary.LastParameter - boundary.FirstParameter)) for k in range(33)]
                    radii = [(p - center).Length for p in points]
                    nearest = min(range(2), key=lambda i: abs(radii[0] - (ro, ri)[i]))
                    error = max(max(abs(r - (ro, ri)[nearest]) for r in radii),
                                max(abs((p - center).dot(normal)) for p in points))
                require(error <= tol, 'local_section_radius_mismatch')
                residual = max(residual, error)
                perimeters[nearest] += boundary.Length
            require(all(abs(length - 2 * math.pi * radius) <= max(tol, radius * 1e-6)
                        for length, radius in zip(perimeters, (ro, ri))), 'local_section_coverage_incomplete')
            basis = unit(normal.cross(App.Vector(1, 0, 0) if abs(normal.x) < 0.8 else App.Vector(0, 1, 0)))
            second = normal.cross(basis)
            eval_tol = min(tol / 10, (ro - ri) / 100)
            require(not solid.isInside(center, eval_tol, False), 'centerline_contains_material')
            for i in range(8):
                radial = basis * math.cos(i * math.pi / 4) + second * math.sin(i * math.pi / 4)
                require(solid.isInside(center + radial * ((ro + ri) / 2), eval_tol, False) and
                        not solid.isInside(center + radial * (ri / 2), eval_tol, False) and
                        not solid.isInside(center + radial * (ro + max((ro - ri) / 2, 2 * tol)), eval_tol, False),
                        'annular_material_side_not_proved')
            samples.append(dict(status='verified', segment_order=item['order'],
                station_s_mm=item['s0_mm'] + edge.Length * fraction, origin_mm=xyz(center), normal=xyz(normal),
                outer_diameter_mm=2 * pair['outer']['radius'], inner_diameter_mm=2 * pair['inner']['radius'],
                wall_thickness_mm=pair['outer']['radius'] - pair['inner']['radius'], residual_mm=residual,
                kernel_curve_types=sorted(curve_kinds), representation_check_samples_per_non_circle_edge=33,
                method='bounded_normal_section_and_radial_material_probes', coordinate_system=coordinates))
    return samples


# 组合全部几何必要条件，通过后输出尺寸、路径、端口和证据；不支持时不输出确认截面。
def classify_analytic_tube(solid, tolerance, coordinate_system='step_world'):
    try:
        require(solid.ShapeType == 'Solid' and solid.isValid() and solid.isClosed(), 'valid_closed_single_solid_required')
        groups, caps = walls(solid, tolerance)
        pairs, ro, ri = pair_walls(groups, tolerance)
        segments = ordered_segments(pairs, tolerance)
        ends = verify_ends(caps, segments, ro, ri, tolerance, coordinate_system)
        length = sum(edge.Length for _, edge, _ in segments)
        area = math.pi * (ro * ro - ri * ri)
        # 等截面扫掠的理论体积为环形截面积乘中心线长度；与实际体积交叉检查可排除多余材料或缺损。
        residual = abs(solid.Volume - area * length) / (area * length)
        require(residual <= 1e-6, 'analytic_sweep_volume_mismatch')
        samples = verify_sections(solid, segments, ro, ri, tolerance, coordinate_system)
        bent = any(item['kind'] == 'arc' for item, _, _ in segments)
        path = dict(kind='bent' if bent else 'straight', start_mm=segments[0][0]['start_mm'],
                    end_mm=segments[-1][0]['end_mm'], length_mm=length, developed_length_mm=length,
                    segments=[item for item, _, _ in segments], coordinate_system=coordinate_system,
                    method='paired_analytic_walls_and_shared_section_boundaries')
        if not bent:
            path['direction'] = segments[0][0]['tangent_start']
        return dict(status='confirmed_bent_hollow_tube' if bent else 'confirmed_straight_hollow_tube',
            source='derived_geometry', path=path, ends=ends, unmet_conditions=[],
            exterior_face_indices=[i for _, _, pair in segments for i in pair['outer']['indices']] + [i for indices, _ in caps for i in indices],
            face_reference_system='solid_brep_face_index_1_based',
            section=dict(status='analytic_concentric_annulus', outer_diameter_mm=2 * ro, inner_diameter_mm=2 * ri,
                wall_thickness_mm=ro - ri, unit='mm', material_area_mm2=area,
                method='paired_cylindrical_toroidal_walls_and_normal_sections',
                scope='validated_analytic_bent_solid' if bent else 'validated_straight_solid',
                uniformity_status='verified_analytic_constant_section', samples=samples,
                coordinate_system=coordinate_system, tolerance_mm=tolerance,
                wall_thickness_min_mm=min(s['wall_thickness_mm'] for s in samples),
                wall_thickness_max_mm=max(s['wall_thickness_mm'] for s in samples)),
            verification=dict(volume_relative_residual=residual, sample_count=len(samples),
                segment_count=len(segments), wall_face_count=sum(len(g['faces']) for g in groups),
                tangent_residual_limit=TANGENT_RESIDUAL_MAX,
                interpretation='ideal_cad_solid_geometry_not_as_manufactured_wall_thinning'))
    except TubeUnsupported as exc:
        return dict(status='unsupported_geometry', source='derived_geometry', unmet_conditions=[str(exc)])


# 把见证点投影到有限中心线段；圆弧同时考虑端点，近等距但站位不同则返回 ambiguous。
def centerline_station(path, point, tolerance):
    """Project onto finite centerline edges; tied distant stations stay explicit."""
    candidates = []
    for item in path['segments']:
        a, b = App.Vector(*item['start_mm']), App.Vector(*item['end_mm'])
        if item['kind'] == 'line':
            direction = unit(b - a)
            local = max(0.0, min(item['length_mm'], (point - a).dot(direction)))
            foot = a + direction * local
            candidates.append(((point - foot).Length, item['s0_mm'] + local))
        else:
            center, normal = App.Vector(*item['center_mm']), unit(App.Vector(*item['plane_normal']))
            radial = a - center
            projected = point - center - normal * (point - center).dot(normal)
            candidates.extend((((point - a).Length, item['s0_mm']), ((point - b).Length, item['s1_mm'])))
            if projected.Length > tolerance:
                angle = math.atan2(normal.dot(radial.cross(projected)), radial.dot(projected)) % (2 * math.pi)
                if angle <= math.radians(item['bend_deg']):
                    foot = center + unit(projected) * item['radius_mm']
                    candidates.append(((point - foot).Length, item['s0_mm'] + angle * item['radius_mm']))
    minimum = min(d for d, _ in candidates)
    # 几何距离几乎相同不表示路径站位唯一，例如紧邻的回折段；此时不随意取列表第一项。
    stations = sorted(s for d, s in candidates if d <= minimum + tolerance)
    return (stations[0], 'unique') if stations[-1] - stations[0] <= tolerance else (None, 'ambiguous')
