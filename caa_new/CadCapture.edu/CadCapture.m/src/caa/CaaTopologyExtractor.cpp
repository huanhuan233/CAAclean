#include "caa/CaaTopologyExtractor.h"
#include "caa/CaaGuards.h"

#include <CATBaseUnknown.h>
#include <CATBody.h>
#include <CATCell.h>
#include <CATEdge.h>
#include <CATFace.h>
#include <CATICGMBodyTessellator.h>
#include <CATCGMTessFanIter.h>
#include <CATCGMTessPointIter.h>
#include <CATCGMTessPolyIter.h>
#include <CATCGMTessStripeIter.h>
#include <CATCGMTessTrianIter.h>
#include <CATDocument.h>
#include <CATIGeometricalElement.h>
#include <CATIPrtContainer.h>
#include <CATIPrtPart.h>
#include <CATISpecObject.h>
#include <CATIShapeFeatureBody.h>
#include <CATLISTV_CATISpecObject.h>
#include <CATInit.h>
#include <CATMathPoint.h>
#include <CATUnicodeString.h>
#include <ListPOfCATCell.h>
#include <cstring>
#include <vector>

namespace cadcapture {

class CgmTessellatorGuard
{
public:
  explicit CgmTessellatorGuard(CATICGMBodyTessellator* tessellator)
    : _tessellator(tessellator) {}
  ~CgmTessellatorGuard() { if (_tessellator) _tessellator->Release(); }
  CATICGMBodyTessellator* Get() const { return _tessellator; }

private:
  CgmTessellatorGuard(const CgmTessellatorGuard&);
  CgmTessellatorGuard& operator=(const CgmTessellatorGuard&);

  CATICGMBodyTessellator* _tessellator;
};

class SpecListGuard
{
public:
  explicit SpecListGuard(CATListValCATISpecObject_var* list) : _list(list) {}
  ~SpecListGuard() { delete _list; }

private:
  SpecListGuard(const SpecListGuard&);
  SpecListGuard& operator=(const SpecListGuard&);
  CATListValCATISpecObject_var* _list;
};

static std::string UnicodeToUtf8Local(const CATUnicodeString& value)
{
  const size_t capacity = static_cast<size_t>(value.GetLengthInChar() + 1) * 4 + 1;
  std::vector<char> buffer(capacity, 0);
  size_t byte_count = 0;
  value.ConvertToUTF8(&buffer[0], &byte_count);
  if (byte_count >= buffer.size())
    byte_count = buffer.size() - 1;
  buffer[byte_count] = 0;
  return std::string(&buffer[0], byte_count);
}

static std::string SafeSpecString(CATISpecObject* spec, const char* field)
{
  if (!spec)
    return "";
  try
  {
    if (std::strcmp(field, "display") == 0)
      return UnicodeToUtf8Local(spec->GetDisplayName());
    if (std::strcmp(field, "internal") == 0)
      return UnicodeToUtf8Local(spec->GetName());
    if (std::strcmp(field, "startup") == 0)
      return UnicodeToUtf8Local(spec->GetType());
  }
  catch (...)
  {
  }
  return "";
}

static std::string ObjectKey(const std::string& display_name,
                             const std::string& internal_name,
                             const std::string& startup_type)
{
  return display_name + "\n" + internal_name + "\n" + startup_type;
}

static std::string SpecKey(CATISpecObject* spec)
{
  return ObjectKey(SafeSpecString(spec, "display"),
                   SafeSpecString(spec, "internal"),
                   SafeSpecString(spec, "startup"));
}

class FeatureSubjectMatcher
{
public:
  explicit FeatureSubjectMatcher(const ReconstructionPackage& package)
    : _package(package), _used(package.objects.size(), false)
  {
  }

  std::string Match(CATISpecObject* spec)
  {
    const std::string key = SpecKey(spec);
    size_t i;
    for (i = 0; i < _package.objects.size(); ++i)
    {
      if (_used[i])
        continue;
      const ObjectEntity& object = _package.objects[i];
      if (object.object_kind != "catia_spec_object")
        continue;
      if (ObjectKey(object.display_name, object.internal_name, object.startup_type) == key)
      {
        _used[i] = true;
        return object.object_id;
      }
    }
    return "";
  }

private:
  const ReconstructionPackage& _package;
  std::vector<bool> _used;
};

static const char* TopologyCellKind(short dimension)
{
  if (dimension == 0) return "vertex";
  if (dimension == 1) return "edge";
  if (dimension == 2) return "face";
  if (dimension == 3) return "volume";
  return "unknown";
}

static std::string FindRootCatPartSubject(const ReconstructionPackage& package)
{
  size_t i;
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    if (object.startup_type == "Part" || object.internal_name == "Part")
      return object.object_id;
  }
  if (!package.document_graph.documents.empty())
    return package.document_graph.documents[0].document_id;
  return "";
}

static bool IsRootCatPart(const ReconstructionPackage& package)
{
  return !package.document_graph.documents.empty() &&
         package.document_graph.documents[0].document_kind == "catpart";
}

static CATISpecObject* GetRootPartSpec(CaaDocumentHandle& document_handle,
                                       ReconstructionPackage& package)
{
  CATDocument* document = static_cast<CATDocument*>(document_handle.NativeDocumentForCaaOnly());
  if (!document)
    return 0;

  CATInit* init = 0;
  try
  {
    if (FAILED(document->QueryInterface(IID_CATInit, reinterpret_cast<void**>(&init))) || !init)
      return 0;
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_catinit_query_failed",
                                                 FindRootCatPartSubject(package),
                                                 "CATInit QueryInterface raised an exception",
                                                 "topology_extractor"));
    return 0;
  }
  CaaInterfaceGuard<CATInit> init_guard(init);

  CATBaseUnknown* root = 0;
  try
  {
    root = init->GetRootContainer("CATIPrtContainer");
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_root_container_failed",
                                                 FindRootCatPartSubject(package),
                                                 "CATInit::GetRootContainer raised an exception",
                                                 "topology_extractor"));
    return 0;
  }
  if (!root)
    return 0;
  CaaInterfaceGuard<CATBaseUnknown> root_guard(root);

  CATIPrtContainer* part_container = 0;
  try
  {
    if (FAILED(root->QueryInterface(IID_CATIPrtContainer, reinterpret_cast<void**>(&part_container))) ||
        !part_container)
      return 0;
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_prt_container_query_failed",
                                                 FindRootCatPartSubject(package),
                                                 "CATIPrtContainer QueryInterface raised an exception",
                                                 "topology_extractor"));
    return 0;
  }
  CaaInterfaceGuard<CATIPrtContainer> container_guard(part_container);

  CATISpecObject_var part = NULL_var;
  try
  {
    part = part_container->GetPart();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_get_part_failed",
                                                 FindRootCatPartSubject(package),
                                                 "CATIPrtContainer::GetPart raised an exception",
                                                 "topology_extractor"));
    return 0;
  }
  if (part == NULL_var)
    return 0;

  CATISpecObject* retained = part;
  if (retained)
    retained->AddRef();
  return retained;
}

static void LoadCellsByDimension(CATBody* body,
                                 short dimension,
                                 std::vector<CATCell*>& output)
{
  if (!body)
    return;
  CATLISTP(CATCell) cells;
  body->GetAllCells(cells, dimension);
  int index = 1;
  for (; index <= cells.Size(); ++index)
    output.push_back(cells[index]);
}

static long EstimateTrianglesFromPointGroups(CATLONG32 group_count, CATLONG32 point_count)
{
  if (group_count <= 0 || point_count <= 0)
    return 0;
  return point_count > 2 * group_count ?
    static_cast<long>(point_count - 2 * group_count) : 0;
}

static void AppendCellEntity(CaptureIdRegistry& ids,
                             ReconstructionPackage& package,
                             CATCell* cell,
                             const std::string& body_id,
                             const std::string& subject_id,
                             long topology_index)
{
  TopologyEntity entity;
  entity.topology_id = ids.NextTopologyId();
  entity.subject_id = subject_id;
  entity.parent_topology_id = body_id;
  entity.topology_index = topology_index;
  entity.source_kind = "cat_body_cell";
  entity.value_source = "typed_caa_public_cat_topology";
  entity.stable_id_method = "cat_topology_dimension_order_revision_local";
  entity.stability_scope = "same_input_same_r21_parser_revision";
  entity.read_status = "success";

  if (!cell)
  {
    entity.topology_kind = "unknown";
    entity.read_status = "partial";
    package.topology.push_back(entity);
    return;
  }

  try
  {
    const short dimension = cell->GetDimension();
    entity.dimension = static_cast<long>(dimension);
    entity.topology_kind = TopologyCellKind(dimension);
  }
  catch (...)
  {
    entity.topology_kind = "unknown";
    entity.read_status = "partial";
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_cell_dimension_failed",
                                                 entity.topology_id,
                                                 "CATCell::GetDimension raised an exception",
                                                 "topology_extractor"));
  }
  try { entity.domain_count = static_cast<long>(cell->GetNbDomains()); }
  catch (...)
  {
    entity.read_status = "partial";
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_cell_domain_count_failed",
                                                 entity.topology_id,
                                                 "CATCell::GetNbDomains raised an exception",
                                                 "topology_extractor"));
  }
  try { entity.internal_domain_count = static_cast<long>(cell->GetNbInternalDomains()); }
  catch (...)
  {
    entity.read_status = "partial";
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_cell_internal_domain_count_failed",
                                                 entity.topology_id,
                                                 "CATCell::GetNbInternalDomains raised an exception",
                                                 "topology_extractor"));
  }
  try
  {
    CATMathPoint center;
    cell->EstimateCenter(center);
    center.GetCoord(entity.center_mm);
    entity.has_center = true;
    entity.geometry_status = "center_available";
  }
  catch (...)
  {
    entity.geometry_status = "center_unavailable";
  }
  try
  {
    if (entity.dimension == 2)
    {
      CATFace* face = static_cast<CATFace*>(cell);
      entity.area_mm2 = face->CalcArea();
      entity.area_mm2_available = true;
      entity.measure_status = "success";
    }
    else if (entity.dimension == 1)
    {
      CATEdge* edge = static_cast<CATEdge*>(cell);
      entity.length_mm = edge->CalcLength();
      entity.length_mm_available = true;
      entity.measure_status = "success";
    }
    else
      entity.measure_status = "not_applicable";
  }
  catch (...)
  {
    entity.measure_status = "failed";
    entity.read_status = "partial";
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_cell_measure_failed",
                                                 entity.topology_id,
                                                 "CATFace::CalcArea or CATEdge::CalcLength raised an exception",
                                                 "topology_extractor"));
  }

  package.topology.push_back(entity);
}

static void AppendFaceTessellation(CaptureIdRegistry& ids,
                                   ReconstructionPackage& package,
                                   CATICGMBodyTessellator* tessellator,
                                   CATFace* face,
                                   const std::string& body_topology_id,
                                   const std::string& face_topology_id,
                                   const std::string& subject_id,
                                   long primitive_index,
                                   long& next_triangle)
{
  GeometryEntity geometry;
  geometry.geometry_id = ids.NextGeometryId();
  geometry.subject_id = subject_id;
  geometry.body_topology_id = body_topology_id;
  geometry.topology_id = face_topology_id;
  geometry.geometry_kind = "face_tessellation_range";
  geometry.kind = GeometryTessellation;
  geometry.value_source = "typed_caa_public_body_tessellator";
  geometry.primitive_index = primitive_index;
  geometry.triangle_start = next_triangle;

  if (!tessellator || !face)
  {
    geometry.representation_status = "unavailable";
    package.geometry.push_back(geometry);
    return;
  }

  try
  {
    CATBoolean planar = FALSE;
    CATCGMTessPointIter* points = 0;
    CATCGMTessStripeIter* strips = 0;
    CATCGMTessFanIter* fans = 0;
    CATCGMTessPolyIter* polygons = 0;
    CATCGMTessTrianIter* triangles = 0;
    short side = 0;
    tessellator->GetFace(face, planar, &points, &strips, &fans, &polygons, &triangles, &side);
    geometry.planar = planar ? true : false;
    geometry.face_orientation_side = side;
    if (points)
      geometry.point_count = static_cast<long>(points->GetNbPoint());
    if (triangles)
      geometry.isolated_triangle_count = static_cast<long>(triangles->GetNbTrian());
    CATLONG32 strip_points = 0;
    if (strips)
    {
      geometry.strip_count = static_cast<long>(strips->GetNbStri(strip_points));
      geometry.estimated_triangle_count += EstimateTrianglesFromPointGroups(geometry.strip_count, strip_points);
    }
    CATLONG32 fan_points = 0;
    if (fans)
    {
      geometry.fan_count = static_cast<long>(fans->GetNbFan(fan_points));
      geometry.estimated_triangle_count += EstimateTrianglesFromPointGroups(geometry.fan_count, fan_points);
    }
    CATLONG32 polygon_points = 0;
    if (polygons)
    {
      geometry.polygon_count = static_cast<long>(polygons->GetNbPoly(polygon_points));
      geometry.estimated_triangle_count += EstimateTrianglesFromPointGroups(geometry.polygon_count, polygon_points);
    }
    geometry.estimated_triangle_count += geometry.isolated_triangle_count;
    geometry.triangle_count = geometry.estimated_triangle_count;
    next_triangle += geometry.triangle_count;
    geometry.representation_status = "success";
  }
  catch (...)
  {
    geometry.representation_status = "failed";
    package.diagnostics.push_back(MakeDiagnostic("warning", "face_tessellation_failed",
                                                 face_topology_id,
                                                 "CATICGMBodyTessellator::GetFace raised an exception",
                                                 "topology_extractor"));
  }
  package.geometry.push_back(geometry);
}

static void AppendResultOutBody(CaptureIdRegistry& ids,
                                ReconstructionPackage& package,
                                CATBody* body,
                                const std::string& feature_subject_id)
{
  if (!body || feature_subject_id.empty())
    return;

  TopologyEntity entity;
  entity.topology_id = ids.NextTopologyId();
  entity.subject_id = feature_subject_id;
  entity.topology_kind = "feature_result_body";
  entity.source_kind = "catishapefeaturebody_resultout";
  entity.value_source = "CATIShapeFeatureBody.GetResultOUT;CATIGeometricalElement.GetBodyResult";
  entity.stable_id_method = "capture_id_registry";
  entity.stability_scope = "same_input_same_r21_parser_revision";
  entity.read_status = "success";
  try
  {
    int vertices = 0;
    int edges = 0;
    int faces = 0;
    int volumes = 0;
    body->GetCellNumbers(&vertices, &edges, &faces, &volumes);
    entity.vertex_count = static_cast<long>(vertices);
    entity.edge_count = static_cast<long>(edges);
    entity.face_count = static_cast<long>(faces);
    entity.volume_count = static_cast<long>(volumes);
  }
  catch (...)
  {
    entity.read_status = "partial";
    package.diagnostics.push_back(MakeDiagnostic("warning", "feature_result_cell_count_failed",
                                                 feature_subject_id,
                                                 "CATBody::GetCellNumbers failed for feature ResultOUT",
                                                 "topology_extractor"));
  }
  package.topology.push_back(entity);

  FeatureDependency dependency;
  dependency.from_feature_id = feature_subject_id;
  dependency.to_feature_id = entity.topology_id;
  dependency.dependency_kind = "has_resultout_body";
  dependency.read_status = entity.read_status;
  package.feature_dependencies.push_back(dependency);
}

static void CaptureResultOutForSpec(CATISpecObject* spec,
                                    CaptureIdRegistry& ids,
                                    ReconstructionPackage& package,
                                    FeatureSubjectMatcher& matcher)
{
  if (!spec)
    return;
  CATIShapeFeatureBody* shape_body = 0;
  try
  {
    if (FAILED(spec->QueryInterface(IID_CATIShapeFeatureBody,
                                    reinterpret_cast<void**>(&shape_body))) ||
        !shape_body)
      return;
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "shape_feature_body_query_exception",
                                                 FindRootCatPartSubject(package),
                                                 "CATIShapeFeatureBody QueryInterface raised an exception",
                                                 "topology_extractor"));
    return;
  }
  CaaInterfaceGuard<CATIShapeFeatureBody> shape_guard(shape_body);

  const std::string subject_id = matcher.Match(spec);
  CATISpecObject_var result_out = NULL_var;
  try
  {
    result_out = shape_body->GetResultOUT();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "feature_resultout_read_failed",
                                                 subject_id,
                                                 "CATIShapeFeatureBody::GetResultOUT raised an exception",
                                                 "topology_extractor"));
    return;
  }
  if (result_out == NULL_var)
    return;

  CATISpecObject* result_spec = result_out;
  CATIGeometricalElement* geometry = 0;
  try
  {
    if (FAILED(result_spec->QueryInterface(IID_CATIGeometricalElement,
                                           reinterpret_cast<void**>(&geometry))) ||
        !geometry)
      return;
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "feature_result_geometry_query_exception",
                                                 subject_id,
                                                 "CATIGeometricalElement QueryInterface raised an exception for ResultOUT",
                                                 "topology_extractor"));
    return;
  }
  CaaInterfaceGuard<CATIGeometricalElement> geometry_guard(geometry);

  CATBody_var result_body = NULL_var;
  try
  {
    result_body = geometry->GetBodyResult();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "feature_result_body_read_failed",
                                                 subject_id,
                                                 "CATIGeometricalElement::GetBodyResult raised an exception for ResultOUT",
                                                 "topology_extractor"));
    return;
  }
  if (result_body == NULL_var)
    return;
  CATBody* body = result_body;
  AppendResultOutBody(ids, package, body, subject_id);
}

static void TraverseResultOutSpecs(CATISpecObject* spec,
                                   CaptureIdRegistry& ids,
                                   ReconstructionPackage& package,
                                   FeatureSubjectMatcher& matcher)
{
  if (!spec)
    return;
  CaptureResultOutForSpec(spec, ids, package, matcher);
  CATListValCATISpecObject_var* children = 0;
  try
  {
    children = spec->ListComponents();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "feature_result_children_failed",
                                                 FindRootCatPartSubject(package),
                                                 "CATISpecObject::ListComponents failed during ResultOUT scan",
                                                 "topology_extractor"));
    return;
  }
  if (!children)
    return;
  SpecListGuard guard(children);
  int index = 1;
  for (; index <= children->Size(); ++index)
  {
    CATISpecObject_var child = (*children)[index];
    if (child != NULL_var)
    {
      CATISpecObject* child_pointer = child;
      TraverseResultOutSpecs(child_pointer, ids, package, matcher);
    }
  }
}

bool CaaTopologyExtractor::Extract(CaaDocumentHandle& document_handle,
                                   CaptureIdRegistry& ids,
                                   ReconstructionPackage& package)
{
  if (!IsRootCatPart(package))
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "topology_root_not_catpart",
                                                 "topology",
                                                 "Root final-body topology is only captured for CATPart root documents in this stage",
                                                 "topology_extractor"));
    return true;
  }

  const std::string subject_id = FindRootCatPartSubject(package);
  CATISpecObject* part_spec = GetRootPartSpec(document_handle, package);
  if (!part_spec)
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "topology_part_root_unavailable",
                                                 subject_id,
                                                 "Part root was unavailable for final-body topology extraction",
                                                 "topology_extractor"));
    return true;
  }
  CaaInterfaceGuard<CATISpecObject> part_guard(part_spec);

  CATIPrtPart* part_interface = 0;
  try
  {
    if (FAILED(part_spec->QueryInterface(IID_CATIPrtPart, reinterpret_cast<void**>(&part_interface))) ||
        !part_interface)
    {
      package.diagnostics.push_back(MakeDiagnostic("info", "catiprtpart_unavailable",
                                                   subject_id,
                                                   "Part object does not expose CATIPrtPart",
                                                   "topology_extractor"));
      return true;
    }
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "catiprtpart_query_exception",
                                                 subject_id,
                                                 "CATIPrtPart QueryInterface raised an exception",
                                                 "topology_extractor"));
    return true;
  }
  CaaInterfaceGuard<CATIPrtPart> part_interface_guard(part_interface);

  CATBody_var body_var = NULL_var;
  try
  {
    body_var = part_interface->GetSolid();
  }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "part_main_solid_read_failed",
                                                 subject_id,
                                                 "CATIPrtPart::GetSolid raised an exception",
                                                 "topology_extractor"));
    return true;
  }
  if (body_var == NULL_var)
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "part_main_solid_unavailable",
                                                 subject_id,
                                                 "CATIPrtPart::GetSolid returned null",
                                                 "topology_extractor"));
    return true;
  }

  CATBody* body = body_var;
  if (!body)
    return true;

  TopologyEntity body_entity;
  body_entity.topology_id = ids.NextTopologyId();
  body_entity.subject_id = subject_id;
  body_entity.topology_kind = "body";
  body_entity.source_kind = "catiprtpart_main_solid";
  body_entity.value_source = "typed_caa_public_cat_body";
  body_entity.stable_id_method = "capture_id_registry";
  body_entity.stability_scope = "same_input_same_r21_parser_revision";
  body_entity.read_status = "success";
  try
  {
    int vertices = 0;
    int edges = 0;
    int faces = 0;
    int volumes = 0;
    body->GetCellNumbers(&vertices, &edges, &faces, &volumes);
    body_entity.vertex_count = static_cast<long>(vertices);
    body_entity.edge_count = static_cast<long>(edges);
    body_entity.face_count = static_cast<long>(faces);
    body_entity.volume_count = static_cast<long>(volumes);
  }
  catch (...)
  {
    body_entity.read_status = "partial";
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_cell_count_failed",
                                                 subject_id,
                                                 "CATBody::GetCellNumbers raised an exception",
                                                 "topology_extractor"));
  }
  package.topology.push_back(body_entity);
  const std::string body_id = body_entity.topology_id;

  std::vector<CATCell*> faces;
  std::vector<CATCell*> edges;
  std::vector<CATCell*> vertices;
  std::vector<CATCell*> volumes;
  try { LoadCellsByDimension(body, 2, faces); }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_face_enumeration_failed",
                                                 body_id,
                                                 "CATBody::GetAllCells failed for faces",
                                                 "topology_extractor"));
  }
  try { LoadCellsByDimension(body, 1, edges); }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_edge_enumeration_failed",
                                                 body_id,
                                                 "CATBody::GetAllCells failed for edges",
                                                 "topology_extractor"));
  }
  try { LoadCellsByDimension(body, 0, vertices); }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_vertex_enumeration_failed",
                                                 body_id,
                                                 "CATBody::GetAllCells failed for vertices",
                                                 "topology_extractor"));
  }
  try { LoadCellsByDimension(body, 3, volumes); }
  catch (...)
  {
    package.diagnostics.push_back(MakeDiagnostic("warning", "topology_volume_enumeration_failed",
                                                 body_id,
                                                 "CATBody::GetAllCells failed for volumes",
                                                 "topology_extractor"));
  }

  CATICGMBodyTessellator* tessellator = 0;
  try
  {
    tessellator = CATCGMCreateBodyTessellator(body, 0.1);
    if (tessellator)
      tessellator->Run();
  }
  catch (...)
  {
    if (tessellator)
    {
      tessellator->Release();
      tessellator = 0;
    }
    package.diagnostics.push_back(MakeDiagnostic("warning", "body_tessellation_failed",
                                                 body_id,
                                                 "CATCGMCreateBodyTessellator or Run raised an exception",
                                                 "topology_extractor"));
  }
  CgmTessellatorGuard tessellator_guard(tessellator);

  size_t i;
  long primitive_index = 1;
  long next_triangle = 0;
  for (i = 0; i < faces.size(); ++i, ++primitive_index)
  {
    const size_t before = package.topology.size();
    AppendCellEntity(ids, package, faces[i], body_id, subject_id, primitive_index);
    const std::string face_id = package.topology.size() > before ? package.topology[before].topology_id : "";
    CATFace* face = static_cast<CATFace*>(faces[i]);
    AppendFaceTessellation(ids, package, tessellator_guard.Get(), face,
                           body_id, face_id, subject_id, primitive_index, next_triangle);
  }
  for (i = 0; i < edges.size(); ++i)
    AppendCellEntity(ids, package, edges[i], body_id, subject_id, static_cast<long>(i + 1));
  for (i = 0; i < vertices.size(); ++i)
    AppendCellEntity(ids, package, vertices[i], body_id, subject_id, static_cast<long>(i + 1));
  for (i = 0; i < volumes.size(); ++i)
    AppendCellEntity(ids, package, volumes[i], body_id, subject_id, static_cast<long>(i + 1));

  FeatureSubjectMatcher matcher(package);
  TraverseResultOutSpecs(part_spec, ids, package, matcher);

  package.diagnostics.push_back(MakeDiagnostic("info", "catpart_final_body_topology_captured",
                                               body_id,
                                               "CATPart final CATBody topology and face tessellation ranges captured from R21 Public CAA",
                                               "topology_extractor"));
  return true;
}

}
