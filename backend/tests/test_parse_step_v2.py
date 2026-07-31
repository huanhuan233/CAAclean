import importlib.util
import sys
import types
from pathlib import Path
from uuid import uuid4

import pytest


class Vec:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class Box:
    def __init__(self, mn, mx):
        self.XMin, self.YMin, self.ZMin = mn
        self.XMax, self.YMax, self.ZMax = mx


class Shape:
    ShapeType = "Solid"
    Volume = 1.0
    CenterOfMass = Vec(0, 0, 0)

    def __init__(self, faces, edges, vertexes, box):
        self.Faces = faces
        self.Edges = edges
        self.Vertexes = vertexes
        self.BoundBox = box
        self.Solids = []

    def isNull(self):
        return False


class Topo:
    def __init__(self, name, box=None):
        self.name = name
        self.BoundBox = box or Box((0, 0, 0), (1, 1, 1))
        self.CenterOfMass = Vec(0, 0, 0)

    def hashCode(self):
        return 42

    def isSame(self, other):
        return self is other


class Vertex(Topo):
    def __init__(self, name, point):
        super().__init__(name)
        self.Point = Vec(*point)


class Edge(Topo):
    Length = 1.0

    def __init__(self, name, curve, vertexes):
        super().__init__(name)
        self.Curve = curve
        self.Vertexes = vertexes
        self.FirstParameter = 0.25
        self.LastParameter = 0.75
        self.ParameterRange = (self.FirstParameter, self.LastParameter)

    def valueAt(self, parameter):
        return Vec(parameter, 0, 0)

    def discretize(self, Number=9):
        return [Vec(index / (Number - 1), 0, 0) for index in range(Number)]


class UndefinedCurveEdge(Topo):
    Length = 1e-16
    FirstParameter = 0.0
    LastParameter = 6.283185307179586
    ParameterRange = (FirstParameter, LastParameter)

    def __init__(self, name, vertexes, pcurve=None):
        super().__init__(name)
        self.Vertexes = vertexes
        self._pcurve = pcurve

    @property
    def Curve(self):
        raise TypeError("undefined curve type")

    def valueAt(self, parameter):
        return self.Vertexes[0].Point

    def curveOnSurface(self, index):
        if index == 0:
            return self._pcurve
        return None


class InvalidCurveEdge(UndefinedCurveEdge):
    Length = 2.0


class AnalyticCurve:
    FirstParameter = 0.0
    LastParameter = 1.0

    def isClosed(self):
        return False

    def isPeriodic(self):
        return False


class LineCurve(AnalyticCurve):
    TypeId = "Part::GeomLine"
    Location = Vec(1, 2, 3)
    Direction = Vec(0, 1, 0)


class CircleCurve(AnalyticCurve):
    TypeId = "Part::GeomCircle"
    Center = Vec(1, 2, 3)
    Axis = Vec(0, 0, 1)
    Radius = 4.0

    def isClosed(self):
        return True

    def isPeriodic(self):
        return True


class EllipseCurve(AnalyticCurve):
    TypeId = "Part::GeomEllipse"
    Center = Vec(0, 0, 0)
    Axis = Vec(0, 0, 1)
    MajorRadius = 5.0
    MinorRadius = 2.0
    Focus1 = Vec(4.582575695, 0, 0)
    Focus2 = Vec(-4.582575695, 0, 0)


class HyperbolaCurve(AnalyticCurve):
    TypeId = "Part::GeomHyperbola"
    Center = Vec(0, 0, 0)
    Axis = Vec(0, 0, 1)
    MajorRadius = 5.0
    MinorRadius = 3.0
    Focal = 5.8309518948
    Focus1 = Vec(5.8309518948, 0, 0)
    Focus2 = Vec(-5.8309518948, 0, 0)


class ParabolaCurve(AnalyticCurve):
    TypeId = "Part::GeomParabola"
    Location = Vec(0, 0, 0)
    Axis = Vec(0, 0, 1)
    Focal = 2.5
    Focus = Vec(2.5, 0, 0)


class BezierCurve(AnalyticCurve):
    TypeId = "Part::GeomBezierCurve"
    Degree = 2

    def isRational(self):
        return True

    def getPoles(self):
        return [Vec(0, 0, 0), Vec(1, 2, 0), Vec(2, 0, 0)]

    def getWeights(self):
        return [1.0, 0.5, 1.0]


class BSplineCurve(BezierCurve):
    TypeId = "Part::GeomBSplineCurve"
    Degree = 3
    Continuity = "C2"

    def getKnots(self):
        return [0.0, 0.5, 1.0]

    def getMultiplicities(self):
        return [4, 1, 4]


class OffsetCurve(AnalyticCurve):
    TypeId = "Part::GeomOffsetCurve"
    OffsetValue = 3.5
    OffsetDirection = Vec(0, 0, 1)
    BasisCurve = LineCurve()


class OtherCurve(AnalyticCurve):
    TypeId = "Part::GeomExperimentalCurve"


class Line2d:
    Location = types.SimpleNamespace(x=0.0, y=0.0)
    Direction = types.SimpleNamespace(x=1.0, y=0.0)


class SphereSurface:
    TypeId = "Part::GeomSphere"


class Face(Topo):
    Area = 1.0

    def __init__(self, name, surface, edges):
        super().__init__(name)
        self.Surface = surface
        self.Edges = edges

    def tessellate(self, deflection):
        return [Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)], [(0, 1, 2)]


class Circle:
    TypeId = "Part::GeomCircle"
    FirstParameter = 0.0
    LastParameter = 6.283185307179586
    Radius = 4.0
    Center = Vec(1, 2, 3)
    Axis = Vec(0, 0, 1)

    def isClosed(self):
        return True

    def isPeriodic(self):
        return True


class Cone:
    Axis = Vec(0, 1, 0)
    Apex = Vec(0, 0, 2)
    Center = Vec(0, 0, 1)
    SemiAngle = 0.25
    Radius1 = 2.0
    Radius2 = 5.0


class Torus:
    Center = Vec(2, 2, 2)
    Axis = Vec(1, 0, 0)
    MajorRadius = 8.0
    MinorRadius = 1.5


class Plane:
    Axis = Vec(0, 0, 1)
    Position = Vec(0, 0, 0)


def load_parse_step(monkeypatch, objects):
    fake_freecad = types.SimpleNamespace(
        Version=lambda: ["1", "1", "0"],
        newDocument=lambda name: types.SimpleNamespace(Name=name, Objects=objects, recompute=lambda: None),
        closeDocument=lambda name: None,
    )
    fake_import = types.SimpleNamespace(insert=lambda path, doc_name: None)
    fake_mesh_part = types.SimpleNamespace(meshFromShape=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("fallback")))
    monkeypatch.setitem(sys.modules, "FreeCAD", fake_freecad)
    monkeypatch.setitem(sys.modules, "Import", fake_import)
    monkeypatch.setitem(sys.modules, "MeshPart", fake_mesh_part)
    fake_geom2d = types.SimpleNamespace(Line2d=Line2d)
    monkeypatch.setitem(sys.modules, "Part", types.SimpleNamespace(Geom2d=fake_geom2d))
    module_path = Path(__file__).resolve().parents[1] / "freecad_scripts" / "parse_step.py"
    spec = importlib.util.spec_from_file_location("parse_step_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_step_v2_uses_solid_unique_edges_vertices_and_enriched_geometry(tmp_path, monkeypatch):
    v1 = Vertex("v1", (0, 0, 0))
    v2 = Vertex("v2", (1, 0, 0))
    shared_edge = Edge("shared", Circle(), [v1, v2])
    cone_face = Face("cone_face", Cone(), [shared_edge])
    torus_face = Face("torus_face", Torus(), [shared_edge])
    solid = Shape([cone_face, torus_face], [shared_edge], [v1, v2], Box((0, 0, 0), (1, 1, 1)))
    solid.Solids = [solid]
    obj = types.SimpleNamespace(Name="Obj1", Label="Obj1", Shape=solid)
    module = load_parse_step(monkeypatch, [obj])
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    result = module.parse({"revision_id": str(uuid4()), "source_file_path": str(source), "mesh_deflection": 0.1})

    edges = [entity for entity in result["entities"] if entity["entity_type"] == "edge"]
    vertices = [entity for entity in result["entities"] if entity["entity_type"] == "vertex"]
    faces = [entity for entity in result["entities"] if entity["entity_type"] == "face"]
    assert result["schema_version"] == "cad_parse_v2"
    assert result["parser_version"] == "1.1.0"
    assert len(edges) == 1
    assert len(vertices) == 2
    assert edges[0]["source_ref"] == "Edge1"
    assert vertices[0]["source_ref"] == "Vertex1"
    assert edges[0]["parent_entity_id"] == faces[0]["parent_entity_id"]
    assert edges[0]["geometry"]["radius"] == 4.0
    assert edges[0]["geometry"]["center"] == [1.0, 2.0, 3.0]
    assert edges[0]["geometry"]["axis"] == [0.0, 0.0, 1.0]
    assert edges[0]["geometry"]["curve_type_id"] == "Part::GeomCircle"
    assert {face["geometry_type"] for face in faces} == {"cone", "torus"}
    assert next(face for face in faces if face["geometry_type"] == "cone")["geometry"]["semi_angle"] == 0.25
    assert next(face for face in faces if face["geometry_type"] == "torus")["geometry"]["major_radius"] == 8.0
    assert len([rel for rel in result["relations"] if rel["relation_type"] == "bounded_by_edge"]) == 2
    assert len([rel for rel in result["relations"] if rel["relation_type"] == "has_vertex"]) == 2
    entity_ids = {entity["id"] for entity in result["entities"]}
    for rel in result["relations"]:
        assert rel["source_entity_id"] in entity_ids
        assert rel["target_entity_id"] in entity_ids


def test_parse_step_v2_rerun_for_same_revision_has_stable_entity_ids(tmp_path, monkeypatch):
    v1 = Vertex("v1", (0, 0, 0))
    v2 = Vertex("v2", (1, 0, 0))
    shared_edge = Edge("shared", Circle(), [v1, v2])
    face = Face("face", Cone(), [shared_edge])
    solid = Shape([face], [shared_edge], [v1, v2], Box((0, 0, 0), (1, 1, 1)))
    solid.Solids = [solid]
    obj = types.SimpleNamespace(Name="Obj1", Label="Obj1", Shape=solid)
    module = load_parse_step(monkeypatch, [obj])
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")
    revision_id = str(uuid4())
    job = {"revision_id": revision_id, "source_file_path": str(source), "mesh_deflection": 0.1}

    first = module.parse(job)
    second = module.parse(job)

    assert [entity["id"] for entity in first["entities"]] == [entity["id"] for entity in second["entities"]]
    assert [rel["id"] for rel in first["relations"]] == [rel["id"] for rel in second["relations"]]


def test_parse_step_v2_merges_bounding_boxes_for_all_imported_objects(tmp_path, monkeypatch):
    obj1_shape = Shape([Face("face1", Plane(), [])], [], [], Box((0, 0, 0), (1, 1, 1)))
    obj1_shape.Solids = [obj1_shape]
    obj2_shape = Shape([Face("face2", Plane(), [])], [], [], Box((-5, -4, -3), (2, 3, 4)))
    obj2_shape.Solids = [obj2_shape]
    objects = [
        types.SimpleNamespace(Name="Obj1", Label="Obj1", Shape=obj1_shape),
        types.SimpleNamespace(Name="Obj2", Label="Obj2", Shape=obj2_shape),
    ]
    module = load_parse_step(monkeypatch, objects)
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    result = module.parse({"revision_id": str(uuid4()), "source_file_path": str(source), "mesh_deflection": 0.1})

    assert result["bounding_box"] == {"min": [-5.0, -4.0, -3.0], "max": [2.0, 3.0, 4.0]}


@pytest.mark.parametrize(
    ("curve", "expected_type", "field", "expected"),
    [
        (LineCurve(), "line", "direction", [0.0, 1.0, 0.0]),
        (CircleCurve(), "circle", "radius", 4.0),
        (EllipseCurve(), "ellipse", "major_radius", 5.0),
        (HyperbolaCurve(), "hyperbola", "focal", 5.8309518948),
        (ParabolaCurve(), "parabola", "focal", 2.5),
        (BezierCurve(), "bezier_curve", "weights", [1.0, 0.5, 1.0]),
        (BSplineCurve(), "bspline_curve", "multiplicities", [4, 1, 4]),
        (OffsetCurve(), "offset_curve", "offset_value", 3.5),
    ],
)
def test_edge_geometry_dispatches_every_freecad_curve_type_exactly(
    monkeypatch, curve, expected_type, field, expected
):
    module = load_parse_step(monkeypatch, [])
    edge = Edge("edge", curve, [])

    geometry_type, geometry = module.edge_geometry(edge)

    assert geometry_type == expected_type
    assert geometry["curve_type_id"] == curve.TypeId
    assert geometry["parameter_range"] == [0.25, 0.75]
    assert geometry["start_point"] == [0.25, 0.0, 0.0]
    assert geometry["end_point"] == [0.75, 0.0, 0.0]
    assert geometry["trimmed"] is True
    assert geometry[field] == expected


def test_edge_geometry_serializes_offset_basis_curve(monkeypatch):
    module = load_parse_step(monkeypatch, [])

    geometry_type, geometry = module.edge_geometry(Edge("offset", OffsetCurve(), []))

    assert geometry_type == "offset_curve"
    assert geometry["basis_curve"]["geometry_type"] == "line"
    assert geometry["basis_curve"]["curve_type_id"] == "Part::GeomLine"
    assert geometry["basis_curve"]["direction"] == [0.0, 1.0, 0.0]


def test_edge_geometry_preserves_unlisted_valid_curve_with_samples(monkeypatch):
    module = load_parse_step(monkeypatch, [])

    geometry_type, geometry = module.edge_geometry(Edge("other", OtherCurve(), []))

    assert geometry_type == "other_curve"
    assert geometry["curve_type_id"] == "Part::GeomExperimentalCurve"
    assert len(geometry["sample_points"]) == 9


def test_parse_step_v2_classifies_degenerate_edge_and_keeps_2d_pcurve(tmp_path, monkeypatch):
    v1 = Vertex("v1", (0, 0, 0))
    pcurve = (Line2d(), SphereSurface(), types.SimpleNamespace(), 0.0, 6.283185307179586)
    bad_edge = UndefinedCurveEdge("bad", [v1], pcurve=pcurve)
    face = Face("face", Plane(), [bad_edge])
    solid = Shape([face], [bad_edge], [v1], Box((0, 0, 0), (1, 1, 1)))
    solid.Solids = [solid]
    obj = types.SimpleNamespace(Name="Obj1", Label="Obj1", Shape=solid)
    module = load_parse_step(monkeypatch, [obj])
    source = tmp_path / "part.stp"
    source.write_text("ISO-10303-21;", encoding="utf-8")

    result = module.parse({"revision_id": str(uuid4()), "source_file_path": str(source), "mesh_deflection": 0.1})

    edges = [entity for entity in result["entities"] if entity["entity_type"] == "edge"]
    assert len(edges) == 1
    assert edges[0]["geometry_type"] == "degenerate_edge"
    assert edges[0]["geometry"]["point"] == [0.0, 0.0, 0.0]
    assert edges[0]["geometry"]["parameter_range"] == [0.0, 6.283185307179586]
    assert edges[0]["geometry"]["pcurves"][0]["geometry_type"] == "line_2d"
    assert edges[0]["geometry"]["pcurves"][0]["surface_type_id"] == "Part::GeomSphere"


def test_edge_geometry_marks_non_degenerate_curve_failure_as_invalid(monkeypatch):
    module = load_parse_step(monkeypatch, [])
    v1 = Vertex("v1", (0, 0, 0))
    v2 = Vertex("v2", (1, 0, 0))

    geometry_type, geometry = module.edge_geometry(InvalidCurveEdge("bad", [v1, v2]))

    assert geometry_type == "invalid_curve"
    assert geometry["error"] == "undefined curve type"
