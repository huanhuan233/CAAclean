#include "caa/CaaTopologyExtractor.h"
#include "caa/CaaGuards.h"

#include <CATBaseUnknown.h>
#include <CATBoundaryIterator.h>
#include <CATBody.h>
#include <CATCell.h>
#include <CATDomain.h>
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
#include <cmath>
#include <cstring>
#include <map>
#include <sstream>
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

struct TessPointData
{
  TessPointData()
  {
    xyz[0] = xyz[1] = xyz[2] = 0.0;
  }

  double xyz[3];
};

class BoundaryIteratorGuard
{
public:
  explicit BoundaryIteratorGuard(CATBoundaryIterator* iterator) : _iterator(iterator) {}
  ~BoundaryIteratorGuard() { delete _iterator; }
  CATBoundaryIterator* Get() const { return _iterator; }

private:
  BoundaryIteratorGuard(const BoundaryIteratorGuard&);
  BoundaryIteratorGuard& operator=(const BoundaryIteratorGuard&);
  CATBoundaryIterator* _iterator;
};

static void BuildTessPointMap(CATCGMTessPointIter* points, std::map<int, TessPointData>& out_points)
{
  if (!points)
    return;
  try
  {
    points->Reset();
    while (!points->IsExhausted())
    {
      TessPointData data;
      const double* xyz = points->GetPointXyz();
      if (xyz)
      {
        data.xyz[0] = xyz[0];
        data.xyz[1] = xyz[1];
        data.xyz[2] = xyz[2];
      }
      out_points[static_cast<int>(points->GetPointNu())] = data;
      points->GoToNext();
    }
  }
  catch (...)
  {
  }
}

static bool LookupTessPoint(const std::map<int, TessPointData>& points, int rank, double* out_xyz)
{
  std::map<int, TessPointData>::const_iterator found = points.find(rank);
  if (found == points.end())
    return false;
  out_xyz[0] = found->second.xyz[0];
  out_xyz[1] = found->second.xyz[1];
  out_xyz[2] = found->second.xyz[2];
  return true;
}

static void ComputeTriangleNormal(MeshTriangleEntity& triangle)
{
  const double* vertices = triangle.vertices_mm;
  const double ux = vertices[3] - vertices[0];
  const double uy = vertices[4] - vertices[1];
  const double uz = vertices[5] - vertices[2];
  const double vx = vertices[6] - vertices[0];
  const double vy = vertices[7] - vertices[1];
  const double vz = vertices[8] - vertices[2];
  double nx = uy * vz - uz * vy;
  double ny = uz * vx - ux * vz;
  double nz = ux * vy - uy * vx;
  const double norm = std::sqrt(nx * nx + ny * ny + nz * nz);
  if (norm <= 1.0e-12)
    return;
  triangle.normal[0] = nx / norm;
  triangle.normal[1] = ny / norm;
  triangle.normal[2] = nz / norm;
  triangle.normal_available = true;
}

static std::string MakeIndexedId(const std::string& prefix, long index)
{
  std::ostringstream out;
  out << prefix << "_" << index;
  return out.str();
}

static bool AppendMeshTriangle(ReconstructionPackage& package,
                               const GeometryEntity& geometry,
                               const std::map<int, TessPointData>& points,
                               int a,
                               int b,
                               int c,
                               const char* source_primitive,
                               long& next_triangle,
                               long& triangle_in_face)
{
  double p0[3] = { 0.0, 0.0, 0.0 };
  double p1[3] = { 0.0, 0.0, 0.0 };
  double p2[3] = { 0.0, 0.0, 0.0 };
  if (!LookupTessPoint(points, a, p0) ||
      !LookupTessPoint(points, b, p1) ||
      !LookupTessPoint(points, c, p2))
    return false;

  ++next_triangle;
  ++triangle_in_face;
  MeshTriangleEntity triangle;
  triangle.triangle_id = MakeIndexedId("mesh_triangle", next_triangle);
  triangle.mesh_map_id = geometry.geometry_id;
  triangle.body_id = geometry.body_topology_id;
  triangle.face_cell_id = geometry.topology_id;
  triangle.triangle_index = next_triangle;
  triangle.triangle_index_in_face = triangle_in_face;
  triangle.vertex_ranks[0] = a;
  triangle.vertex_ranks[1] = b;
  triangle.vertex_ranks[2] = c;
  int i;
  for (i = 0; i < 3; ++i)
  {
    triangle.vertices_mm[i] = p0[i];
    triangle.vertices_mm[3 + i] = p1[i];
    triangle.vertices_mm[6 + i] = p2[i];
  }
  ComputeTriangleNormal(triangle);
  triangle.source_primitive = source_primitive ? source_primitive : "unknown";
  triangle.value_source = "typed_caa_public_body_tessellator_triangle_payload";
  package.mesh_triangles.push_back(triangle);
  return true;
}

static double Distance3(const double a[3], const double b[3])
{
  const double dx = a[0] - b[0];
  const double dy = a[1] - b[1];
  const double dz = a[2] - b[2];
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

static void AppendFeatureTopologyLink(ReconstructionPackage& package,
                                      const NativeFeatureResultCellEntity& result_cell)
{
  if (result_cell.dimension != 2)
    return;

  NativeFeatureTopologyLinkEntity link;
  link.link_id = MakeIndexedId("feature_topology_link", static_cast<long>(package.native_feature_topology_links.size() + 1));
  link.source_feature_id = result_cell.source_feature_id;
  link.result_id = result_cell.result_id;
  link.result_cell_id = result_cell.result_cell_id;
  link.mapping_direction = "result_cell_to_final_face";
  link.mapping_method = "caa_resultout_to_final_face_geometry_fingerprint_candidate";
  link.mapping_status = "unmatched";

  if (!result_cell.has_center || !result_cell.area_mm2_available)
  {
    link.mapping_status = "insufficient_result_fingerprint";
    package.native_feature_topology_links.push_back(link);
    return;
  }

  double best_center = 0.0;
  double best_area = 0.0;
  size_t i;
  for (i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& cell = package.topology[i];
    if (cell.dimension != 2 || !cell.has_center || !cell.area_mm2_available)
      continue;
    if (cell.source_kind != "cat_body_cell")
      continue;
    const double center_residual = Distance3(result_cell.center_mm, cell.center_mm);
    const double area_residual = std::fabs(result_cell.area_mm2 - cell.area_mm2);
    const double area_tolerance = std::fabs(result_cell.area_mm2) * 0.000001 > 0.001 ?
      std::fabs(result_cell.area_mm2) * 0.000001 : 0.001;
    if (center_residual <= 0.001 && area_residual <= area_tolerance)
    {
      if (link.candidate_count == 0 || center_residual < best_center ||
          (center_residual == best_center && area_residual < best_area))
      {
        best_center = center_residual;
        best_area = area_residual;
        link.final_cell_id = cell.topology_id;
        link.final_body_id = cell.parent_topology_id;
        link.center_residual_mm = center_residual;
        link.measure_residual = area_residual;
      }
      ++link.candidate_count;
    }
  }

  if (link.candidate_count == 1)
  {
    link.mapping_status = "candidate";
    link.authority = "geometry_fingerprint";
    link.relation_kind = "candidate_survives_to_final";
    link.confidence = 0.75;
  }
  else if (link.candidate_count > 1)
  {
    link.mapping_status = "ambiguous";
    link.authority = "ambiguous";
    link.relation_kind = "candidate_survives_to_final";
    link.confidence = 0.35;
  }
  package.native_feature_topology_links.push_back(link);
}

static std::string LookupCellId(CATCell* cell, const std::map<CATCell*, std::string>& cell_ids)
{
  std::map<CATCell*, std::string>::const_iterator found = cell_ids.find(cell);
  if (found == cell_ids.end())
    return "";
  return found->second;
}

static void AppendFaceWires(ReconstructionPackage& package,
                            CATFace* face,
                            const std::string& body_id,
                            const std::string& face_id,
                            long face_index,
                            const std::map<CATCell*, std::string>& cell_ids,
                            long& next_wire_index,
                            long& next_coedge_index)
{
  if (!face)
    return;
  CATBoundaryIterator* raw_iterator = 0;
  try { raw_iterator = face->CreateBoundaryIterator(); }
  catch (...) { raw_iterator = 0; }
  BoundaryIteratorGuard iterator_guard(raw_iterator);
  CATBoundaryIterator* iterator = iterator_guard.Get();
  if (!iterator)
    return;

  NativeTopologyWireEntity current;
  bool has_current = false;
  long coedge_index_in_wire = 0;
  long current_wire_first_coedge = 0;
  long loop_index_in_face = 0;
  try
  {
    CATSide side = CATSideUnknown;
    CATDomain* domain = 0;
    short new_domain = 0;
    CATCell* boundary = 0;
    while ((boundary = iterator->Next(&side, &domain, &new_domain)) != 0)
    {
      if (!has_current || new_domain)
      {
        if (has_current)
        {
          current.edge_count = coedge_index_in_wire;
          package.topology_wires.push_back(current);
        }
        current = NativeTopologyWireEntity();
        ++next_wire_index;
        ++loop_index_in_face;
        current.wire_id = MakeIndexedId(body_id + "_wire", next_wire_index);
        current.body_id = body_id;
        current.wire_index = next_wire_index;
        current.wire_kind = loop_index_in_face == 1 ? "outer_loop" : "inner_loop";
        current.owning_face_id = face_id;
        current.owning_face_topology_index = face_index;
        current.value_source = "typed_caa_public_boundary_iterator";
        has_current = true;
        coedge_index_in_wire = 0;
        current_wire_first_coedge = next_coedge_index + 1;
      }
      const std::string edge_id = LookupCellId(boundary, cell_ids);
      if (!edge_id.empty())
      {
        NativeTopologyCoedgeEntity coedge;
        ++next_coedge_index;
        ++coedge_index_in_wire;
        coedge.coedge_id = MakeIndexedId(body_id + "_coedge", next_coedge_index);
        coedge.body_id = body_id;
        coedge.wire_id = current.wire_id;
        coedge.owning_face_id = face_id;
        coedge.edge_cell_id = edge_id;
        coedge.coedge_index = next_coedge_index;
        coedge.coedge_index_in_wire = coedge_index_in_wire;
        coedge.edge_orientation_side = static_cast<short>(side);
        coedge.orientation_status = side == CATSideUnknown ? "unknown" : "from_cat_boundary_iterator_side";
        coedge.value_source = "typed_caa_public_boundary_iterator";
        if (coedge_index_in_wire > 1 && !package.topology_coedges.empty())
        {
          coedge.previous_coedge_id = package.topology_coedges.back().coedge_id;
          package.topology_coedges.back().next_coedge_id = coedge.coedge_id;
        }
        package.topology_coedges.push_back(coedge);
      }
    }
    if (has_current)
    {
      current.edge_count = coedge_index_in_wire;
      current.closed_status = coedge_index_in_wire > 0 ? "closed_by_boundary_iterator_loop" : "empty";
      if (coedge_index_in_wire > 1)
      {
        const std::string first_id = MakeIndexedId(body_id + "_coedge", current_wire_first_coedge);
        const std::string last_id = MakeIndexedId(body_id + "_coedge", next_coedge_index);
        if (!package.topology_coedges.empty())
          package.topology_coedges.back().next_coedge_id = first_id;
        size_t i;
        for (i = 0; i < package.topology_coedges.size(); ++i)
        {
          if (package.topology_coedges[i].coedge_id == first_id)
          {
            package.topology_coedges[i].previous_coedge_id = last_id;
            break;
          }
        }
      }
      package.topology_wires.push_back(current);
    }
  }
  catch (...)
  {
  }
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
    std::map<int, TessPointData> point_map;
    BuildTessPointMap(points, point_map);
    long triangle_in_face = 0;
    long failed_triangle_count = 0;
    if (triangles)
    {
      triangles->Reset();
      while (!triangles->IsExhausted())
      {
        int ranks[3] = { 0, 0, 0 };
        triangles->GetTrianNuPts(ranks);
        if (!AppendMeshTriangle(package, geometry, point_map, ranks[0], ranks[1], ranks[2],
                                "triangle", next_triangle, triangle_in_face))
          ++failed_triangle_count;
        triangles->GoToNext();
      }
    }
    if (strips)
    {
      strips->Reset();
      while (!strips->IsExhausted())
      {
        const CATLONG32 count = strips->GetStriNbPts();
        if (count >= 3)
        {
          std::vector<int> ranks(static_cast<size_t>(count), 0);
          strips->GetStriNuPts(&ranks[0]);
          CATLONG32 strip_index = 0;
          for (strip_index = 0; strip_index < count - 2; ++strip_index)
          {
            const int a = (strip_index % 2 == 0) ? ranks[static_cast<size_t>(strip_index)] : ranks[static_cast<size_t>(strip_index + 1)];
            const int b = (strip_index % 2 == 0) ? ranks[static_cast<size_t>(strip_index + 1)] : ranks[static_cast<size_t>(strip_index)];
            const int c = ranks[static_cast<size_t>(strip_index + 2)];
            if (!AppendMeshTriangle(package, geometry, point_map, a, b, c,
                                    "strip", next_triangle, triangle_in_face))
              ++failed_triangle_count;
          }
        }
        strips->GoToNext();
      }
    }
    if (fans)
    {
      fans->Reset();
      while (!fans->IsExhausted())
      {
        const CATLONG32 count = fans->GetFanNbPts();
        if (count >= 3)
        {
          std::vector<int> ranks(static_cast<size_t>(count), 0);
          fans->GetFanNuPts(&ranks[0]);
          CATLONG32 fan_index = 1;
          for (; fan_index < count - 1; ++fan_index)
          {
            if (!AppendMeshTriangle(package, geometry, point_map, ranks[0],
                                    ranks[static_cast<size_t>(fan_index)],
                                    ranks[static_cast<size_t>(fan_index + 1)],
                                    "fan", next_triangle, triangle_in_face))
              ++failed_triangle_count;
          }
        }
        fans->GoToNext();
      }
    }
    if (polygons)
    {
      polygons->Reset();
      while (!polygons->IsExhausted())
      {
        const CATLONG32 count = polygons->GetPolyNbPts();
        if (count >= 3)
        {
          std::vector<int> ranks(static_cast<size_t>(count), 0);
          polygons->GetPolyNuPts(&ranks[0]);
          CATLONG32 polygon_index = 1;
          for (; polygon_index < count - 1; ++polygon_index)
          {
            if (!AppendMeshTriangle(package, geometry, point_map, ranks[0],
                                    ranks[static_cast<size_t>(polygon_index)],
                                    ranks[static_cast<size_t>(polygon_index + 1)],
                                    "polygon", next_triangle, triangle_in_face))
              ++failed_triangle_count;
          }
        }
        polygons->GoToNext();
      }
    }
    geometry.triangle_count = triangle_in_face;
    geometry.representation_status = "success";
    if (failed_triangle_count > 0)
      geometry.representation_status = "partial";
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
  const std::string result_id = entity.topology_id;

  FeatureDependency dependency;
  dependency.from_feature_id = feature_subject_id;
  dependency.to_feature_id = result_id;
  dependency.dependency_kind = "has_resultout_body";
  dependency.read_status = entity.read_status;
  package.feature_dependencies.push_back(dependency);

  std::vector<CATCell*> result_faces;
  std::vector<CATCell*> result_edges;
  std::vector<CATCell*> result_vertices;
  std::vector<CATCell*> result_volumes;
  try { LoadCellsByDimension(body, 2, result_faces); } catch (...) {}
  try { LoadCellsByDimension(body, 1, result_edges); } catch (...) {}
  try { LoadCellsByDimension(body, 0, result_vertices); } catch (...) {}
  try { LoadCellsByDimension(body, 3, result_volumes); } catch (...) {}

  std::vector<CATCell*> all_cells;
  size_t i;
  for (i = 0; i < result_faces.size(); ++i) all_cells.push_back(result_faces[i]);
  for (i = 0; i < result_edges.size(); ++i) all_cells.push_back(result_edges[i]);
  for (i = 0; i < result_vertices.size(); ++i) all_cells.push_back(result_vertices[i]);
  for (i = 0; i < result_volumes.size(); ++i) all_cells.push_back(result_volumes[i]);

  for (i = 0; i < all_cells.size(); ++i)
  {
    CATCell* cell = all_cells[i];
    NativeFeatureResultCellEntity result_cell;
    result_cell.result_cell_id = MakeIndexedId(result_id + "_cell", static_cast<long>(i + 1));
    result_cell.result_id = result_id;
    result_cell.source_feature_id = feature_subject_id;
    result_cell.result_cell_index = static_cast<long>(i + 1);
    result_cell.read_status = "success";
    result_cell.stable_id_method = "cat_feature_result_dimension_order_revision_local";
    result_cell.value_source = "typed_caa_public_shape_feature_body_resultout";
    try
    {
      const short dimension = cell ? cell->GetDimension() : -1;
      result_cell.dimension = static_cast<long>(dimension);
      result_cell.cell_kind = TopologyCellKind(dimension);
    }
    catch (...)
    {
      result_cell.read_status = "partial";
      result_cell.cell_kind = "unknown";
    }
    try
    {
      if (cell)
      {
        CATMathPoint center;
        cell->EstimateCenter(center);
        center.GetCoord(result_cell.center_mm);
        result_cell.has_center = true;
      }
    }
    catch (...)
    {
    }
    try
    {
      if (result_cell.dimension == 2)
      {
        CATFace* face = static_cast<CATFace*>(cell);
        result_cell.area_mm2 = face->CalcArea();
        result_cell.area_mm2_available = true;
      }
      else if (result_cell.dimension == 1)
      {
        CATEdge* edge = static_cast<CATEdge*>(cell);
        result_cell.length_mm = edge->CalcLength();
        result_cell.length_mm_available = true;
      }
    }
    catch (...)
    {
      result_cell.read_status = "partial";
    }
    package.native_feature_result_cells.push_back(result_cell);
    AppendFeatureTopologyLink(package, result_cell);
  }
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
  std::map<CATCell*, std::string> cell_ids;
  std::vector<std::string> face_ids;
  for (i = 0; i < faces.size(); ++i, ++primitive_index)
  {
    const size_t before = package.topology.size();
    AppendCellEntity(ids, package, faces[i], body_id, subject_id, primitive_index);
    const std::string face_id = package.topology.size() > before ? package.topology[before].topology_id : "";
    if (!face_id.empty())
    {
      cell_ids[faces[i]] = face_id;
      face_ids.push_back(face_id);
    }
    CATFace* face = static_cast<CATFace*>(faces[i]);
    AppendFaceTessellation(ids, package, tessellator_guard.Get(), face,
                           body_id, face_id, subject_id, primitive_index, next_triangle);
  }
  for (i = 0; i < edges.size(); ++i)
  {
    const size_t before = package.topology.size();
    AppendCellEntity(ids, package, edges[i], body_id, subject_id, static_cast<long>(i + 1));
    if (package.topology.size() > before)
      cell_ids[edges[i]] = package.topology[before].topology_id;
  }
  for (i = 0; i < vertices.size(); ++i)
  {
    const size_t before = package.topology.size();
    AppendCellEntity(ids, package, vertices[i], body_id, subject_id, static_cast<long>(i + 1));
    if (package.topology.size() > before)
      cell_ids[vertices[i]] = package.topology[before].topology_id;
  }
  for (i = 0; i < volumes.size(); ++i)
  {
    const size_t before = package.topology.size();
    AppendCellEntity(ids, package, volumes[i], body_id, subject_id, static_cast<long>(i + 1));
    if (package.topology.size() > before)
      cell_ids[volumes[i]] = package.topology[before].topology_id;
  }

  long next_wire_index = 0;
  long next_coedge_index = 0;
  for (i = 0; i < faces.size() && i < face_ids.size(); ++i)
  {
    CATFace* face = static_cast<CATFace*>(faces[i]);
    AppendFaceWires(package, face, body_id, face_ids[i], static_cast<long>(i + 1),
                    cell_ids, next_wire_index, next_coedge_index);
  }

  FeatureSubjectMatcher matcher(package);
  TraverseResultOutSpecs(part_spec, ids, package, matcher);

  package.diagnostics.push_back(MakeDiagnostic("info", "catpart_final_body_topology_captured",
                                               body_id,
                                               "CATPart final CATBody topology and face tessellation ranges captured from R21 Public CAA",
                                               "topology_extractor"));
  return true;
}

}
