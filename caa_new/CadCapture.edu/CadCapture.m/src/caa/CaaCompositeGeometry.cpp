#include "caa/CaaCompositeGeometry.h"
#include "caa/CaaPropertyEvidence.h"
#include "caa/CaaGuards.h"
#include <CATICciPly.h>
#include <CATICciCompositesGeometry.h>
#include <CATIGeometricalElement.h>
#include <CATIInertia.h>
#include <CATBody.h>
#include <CATEdge.h>
#include <CATFace.h>
#include <CATBoundaryIterator.h>
#include <CATDomain.h>
#include <CATCrvParam.h>
#include <CATGeometry.h>
#include <CATCurve.h>
#include <CATCrvLimits.h>
#include <CATCircle.h>
#include <CATConic.h>
#include <CATLine.h>
#include <CATMathPlane.h>
#include <CATMathVector.h>
#include <CATVertex.h>
#include <CATPoint.h>
#include <algorithm>
#include <cmath>
#include <ListPOfCATCell.h>
#include <map>
#include <set>

namespace cadcapture {
namespace {
void Add(std::vector<PropertyFact>& facts, const char* key, PropertyFact fact)
{
  fact.key = key;
  facts.push_back(fact);
}
PropertyFact Numeric(double value, const char* unit, const char* api)
{
  PropertyFact fact = evidence::Text(evidence::Number(value), api);
  fact.value_type = "number";
  fact.raw_unit = fact.display_unit = unit;
  return fact;
}

bool WriteVerifiedStraightEdge(std::ostringstream& json, CATEdge* edge, CATCurve* curve)
{
  if (!edge || !curve) return false;
  CATVertex* first = 0;
  CATVertex* last = 0;
  edge->GetVertices(&first, &last);
  CATPoint* first_point = first ? first->GetPoint() : 0;
  CATPoint* last_point = last ? last->GetPoint() : 0;
  if (!first_point || !last_point) return false;
  double a[3], b[3];
  first_point->GetCoord(a[0], a[1], a[2]);
  last_point->GetCoord(b[0], b[1], b[2]);
  const double dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
  const double chord = std::sqrt(dx*dx + dy*dy + dz*dz);
  const double length = edge->CalcLength();
  if (!(chord > 1.0e-6 && length >= chord - 1.0e-6 && length < 1.0e9)) return false;
  // For any point on an arc, the excess path length bounds its distance from
  // the chord. Sampling also checks the curve's parameterization and endpoints.
  const double transverse_bound = 0.5 * std::sqrt(std::max(0.0, length*length - chord*chord));
  if (!(transverse_bound <= 0.05)) return false;
  CATCrvParam start, end;
  try { edge->GetVerticesParamsOnEdgeCurve(&start, &end); }
  catch (...) { return false; }
  double max_residual = 0.0;
  try
  {
    for (int i = 1; i <= 3; ++i)
    {
      CATCrvParam at;
      at.SetParam(i / 4.0, start, end);
      CATMathPoint point;
      curve->Eval(at, CATCrvEvalCommand::EvalPoint, &point);
      double p[3]; point.GetCoord(p);
      const double t = ((p[0]-a[0])*dx + (p[1]-a[1])*dy + (p[2]-a[2])*dz) / (chord*chord);
      const double rx = p[0]-a[0]-t*dx, ry = p[1]-a[1]-t*dy, rz = p[2]-a[2]-t*dz;
      const double residual = std::sqrt(rx*rx + ry*ry + rz*rz);
      if (!(t >= -1.0e-6 && t <= 1.0 + 1.0e-6 && residual <= 0.01)) return false;
      if (residual > max_residual) max_residual = residual;
    }
  }
  catch (...) { return false; }
  json << ",\"curve_type\":\"line\",\"curve_basis\":\"length_bound_and_curve_evaluation\""
       << ",\"straightness_residual_mm\":" << evidence::Number(max_residual)
       << ",\"straightness_bound_mm\":" << evidence::Number(transverse_bound);
  return true;
}

void WriteCurveGeometry(std::ostringstream& json, CATEdge* edge, bool& partial)
{
  CATGeometry* geometry = edge ? edge->GetGeometry() : 0;
  if (!geometry) { json << ",\"curve_type\":\"unavailable\""; partial = true; return; }
  CATCurve* curve = 0;
  const CATCurve* representation = 0;
  if (SUCCEEDED(geometry->QueryInterface(IID_CATCurve, reinterpret_cast<void**>(&curve))) && curve)
  {
    try
    {
      CATCrvLimits limits;
      short orientation = 0;
      representation = curve->GetGeometricRep(limits, orientation);
    }
    catch (...) { representation = 0; }
  }
  CATGeometry* canonical = representation ? const_cast<CATCurve*>(representation) : geometry;
  CATCircle* circle = 0;
  CATLine* line = 0;
  if (SUCCEEDED(canonical->QueryInterface(IID_CATCircle, reinterpret_cast<void**>(&circle))) && circle)
  {
    json << ",\"curve_type\":\"circle\",\"radius_mm\":" << evidence::Number(circle->GetRadius());
    CATConic* conic = 0;
    if (SUCCEEDED(canonical->QueryInterface(IID_CATConic, reinterpret_cast<void**>(&conic))) && conic)
    {
      CATMathPoint center;
      CATMathPlane support;
      CATMathVector axis_u, axis_v;
      conic->GetOrigin(center); conic->GetSupport(support);
      support.GetFirstDirection(axis_u); support.GetSecondDirection(axis_v);
      double xyz[3];
      center.GetCoord(xyz);
      json << ",\"center_mm\":[" << evidence::Number(xyz[0]) << "," << evidence::Number(xyz[1]) << "," << evidence::Number(xyz[2]) << "]";
      axis_u.GetCoord(xyz);
      json << ",\"axis_u\":[" << evidence::Number(xyz[0]) << "," << evidence::Number(xyz[1]) << "," << evidence::Number(xyz[2]) << "]";
      axis_v.GetCoord(xyz);
      json << ",\"axis_v\":[" << evidence::Number(xyz[0]) << "," << evidence::Number(xyz[1]) << "," << evidence::Number(xyz[2]) << "]";
      conic->Release();
    }
    else partial = true;
    circle->Release();
  }
  else if (SUCCEEDED(canonical->QueryInterface(IID_CATLine, reinterpret_cast<void**>(&line))) && line)
  { json << ",\"curve_type\":\"line\""; line->Release(); }
  else if (!WriteVerifiedStraightEdge(json, edge, curve))
  { json << ",\"curve_type\":\"other_exact_curve_unserialized\""; partial = true; }
  if (curve) curve->Release();
}

PropertyFact NativeBoundaryLoops(CATBody* body, const char* api)
{
  PropertyFact result = evidence::Failure("unavailable", api);
  if (!body) return result;
  try
  {
    CATLISTP(CATCell) faces;
    CATLISTP(CATCell) edges;
    body->GetAllCells(faces, 2);
    body->GetAllCells(edges, 1);
    if (faces.Size() == 0)
    {
      const int domains = body->GetNbDomains();
      if (domains == 0) return result;
      std::map<CATCell*, int> edge_indices;
      for (int e = 1; e <= edges.Size(); ++e) edge_indices[edges[e]] = e;
      std::set<int> visited;
      int visits = 0;
      bool partial = false;
      std::ostringstream json;
      json << "{\"source\":\"CATBody.GetDomain/CATDomain.GetCell\",\"faces\":["
           << "{\"face_index\":0,\"loops\":[";
      bool first_loop = true;
      for (int d = 1; d <= domains; ++d)
      {
        CATDomain* domain = body->GetDomain(d);
        if (!domain || domain->GetLowDimension() != 1) continue;
        if (!first_loop) json << ",";
        first_loop = false;
        json << "{\"domain_index\":" << d << ",\"location\":\"unknown\",\"edges\":[";
        const int uses = domain->GetNbCellUses();
        for (int rank = 1; rank <= uses; ++rank)
        {
          if (rank > 1) json << ",";
          CATOrientation orientation = CATOrientationUnknown;
          CATCell* cell = domain->GetCell(rank, &orientation);
          if (!cell) { partial = true; json << "null"; continue; }
          ++visits;
          const std::map<CATCell*, int>::const_iterator found = edge_indices.find(cell);
          if (found == edge_indices.end()) partial = true;
          else visited.insert(found->second);
          CATEdge* edge = static_cast<CATEdge*>(cell);
          json << "{\"edge_index\":" << (found == edge_indices.end() ? 0 : found->second)
               << ",\"orientation\":\"" << (orientation == CATOrientationPositive ? "positive" :
                  orientation == CATOrientationNegative ? "negative" : "unknown")
               << "\",\"length_mm\":" << evidence::Number(edge->CalcLength());
          CATVertex* start_vertex = 0;
          CATVertex* end_vertex = 0;
          edge->GetVertices(&start_vertex, &end_vertex);
          CATVertex* endpoints[2] = {start_vertex, end_vertex};
          const char* endpoint_keys[2] = {"start_mm", "end_mm"};
          for (int endpoint = 0; endpoint < 2; ++endpoint)
          {
            json << ",\"" << endpoint_keys[endpoint] << "\":";
            CATPoint* point = endpoints[endpoint] ? endpoints[endpoint]->GetPoint() : 0;
            if (!point) { json << "null"; continue; }
            double x, y, z;
            point->GetCoord(x, y, z);
            json << "[" << evidence::Number(x) << "," << evidence::Number(y)
                 << "," << evidence::Number(z) << "]";
          }
          try
          {
            CATCrvParam start_param, end_param;
            edge->GetVerticesParamsOnEdgeCurve(&start_param, &end_param);
            json << ",\"curve_start_param\":" << evidence::Number(start_param.GetParam())
                 << ",\"curve_end_param\":" << evidence::Number(end_param.GetParam());
          }
          catch (...) { partial = true; }
          WriteCurveGeometry(json, edge, partial);
          json << "}";
        }
        json << "]}";
      }
      json << "]}],\"expected_unique_edges\":" << edges.Size()
           << ",\"visited_edge_occurrences\":" << visits
           << ",\"visited_unique_edges\":" << visited.size() << "}";
      if (visited.size() != static_cast<size_t>(edges.Size())) partial = true;
      result = evidence::Text(json.str(), api);
      result.value_type = "json";
      if (partial) result.read_status = "partial";
      return result;
    }
    std::map<CATCell*, int> edge_indices;
    for (int e = 1; e <= edges.Size(); ++e) edge_indices[edges[e]] = e;
    std::set<int> visited;
    bool partial = false;
    int visits = 0;
    std::ostringstream json;
    json << "{\"source\":\"CATFace.CreateBoundaryIterator\",\"faces\":[";
    for (int f = 1; f <= faces.Size(); ++f)
    {
      if (f > 1) json << ",";
      json << "{\"face_index\":" << f << ",\"loops\":[";
      CATBoundaryIterator* iterator = 0;
      try { iterator = static_cast<CATFace*>(faces[f])->CreateBoundaryIterator(); }
      catch (...) { partial = true; }
      if (iterator)
      {
        int loop_index = 0;
        bool loop_open = false;
        bool first_edge = true;
        try
        {
          CATCell* cell = 0;
          CATSide side = CATSideUnknown;
          CATDomain* domain = 0;
          short new_domain = 0;
          CATOrientation orientation = CATOrientationUnknown;
          CATCrvParam start_param, end_param;
          while ((cell = iterator->Next(&side, &domain, &new_domain, NULL,
                                        &orientation, &start_param, &end_param)) != 0)
          {
            if (new_domain || !loop_open)
            {
              if (loop_open) json << "]}";
              if (loop_index++ > 0) json << ",";
              const char* location = "unknown";
              if (domain)
              {
                try
                {
                  const CATLocation native_location = domain->GetLocation(faces[f]);
                  location = native_location == CATLocationOuter ? "outer" :
                    native_location == CATLocationInner ? "inner" : "unknown";
                }
                catch (...) { partial = true; }
              }
              json << "{\"domain_index\":" << loop_index << ",\"location\":\"" << location << "\",\"edges\":[";
              loop_open = true;
              first_edge = true;
            }
            if (!first_edge) json << ",";
            first_edge = false;
            ++visits;
            std::map<CATCell*, int>::const_iterator found = edge_indices.find(cell);
            if (found == edge_indices.end()) partial = true;
            else visited.insert(found->second);
            json << "{\"edge_index\":" << (found == edge_indices.end() ? 0 : found->second)
                 << ",\"orientation\":\"" << (orientation == CATOrientationPositive ? "positive" :
                    orientation == CATOrientationNegative ? "negative" : "unknown")
                 << "\",\"side\":\"" << (side == CATSideLeft ? "left" : side == CATSideRight ? "right" : "unknown")
                 << "\",\"trim_start\":" << evidence::Number(start_param.GetParam())
                 << ",\"trim_end\":" << evidence::Number(end_param.GetParam());
            CATEdge* edge = static_cast<CATEdge*>(cell);
            json << ",\"length_mm\":" << evidence::Number(edge->CalcLength());
            try
            {
              CATCrvParam curve_start, curve_end;
              edge->GetVerticesParamsOnEdgeCurve(&curve_start, &curve_end);
              json << ",\"curve_start_param\":" << evidence::Number(curve_start.GetParam())
                   << ",\"curve_end_param\":" << evidence::Number(curve_end.GetParam());
            }
            catch (...) { partial = true; }
            CATVertex* start_vertex = 0;
            CATVertex* end_vertex = 0;
            edge->GetVertices(&start_vertex, &end_vertex);
            CATVertex* endpoints[2] = {start_vertex, end_vertex};
            const char* endpoint_keys[2] = {"start_mm", "end_mm"};
            for (int endpoint = 0; endpoint < 2; ++endpoint)
            {
              json << ",\"" << endpoint_keys[endpoint] << "\":";
              CATPoint* point = endpoints[endpoint] ? endpoints[endpoint]->GetPoint() : 0;
              if (!point) { json << "null"; continue; }
              double x, y, z;
              point->GetCoord(x, y, z);
              json << "[" << evidence::Number(x) << "," << evidence::Number(y)
                   << "," << evidence::Number(z) << "]";
            }
            WriteCurveGeometry(json, edge, partial);
            json << "}";
          }
        }
        catch (...) { partial = true; }
        if (loop_open) json << "]}";
        CATRemove(iterator);
      }
      else partial = true;
      json << "]}";
    }
    json << "],\"expected_unique_edges\":" << edges.Size()
         << ",\"visited_edge_occurrences\":" << visits
         << ",\"visited_unique_edges\":" << visited.size() << "}";
    if (visited.size() != static_cast<size_t>(edges.Size())) partial = true;
    result = evidence::Text(json.str(), api);
    result.value_type = "json";
    if (partial) result.read_status = "partial";
  }
  catch (...) { result = evidence::Failure("exception", api); }
  return result;
}
}

std::vector<PropertyFact> ReadCompositeGeometry(CATICciPly* ply)
{
  std::vector<PropertyFact> facts;
  const char* contour_api = "CATICciPly.GetGeometry/CATIGeometricalElement.GetBodyResult";
  PropertyFact vertices = evidence::Failure("unavailable", contour_api);
  PropertyFact perimeter = evidence::Failure("unavailable", contour_api);
  PropertyFact contour_boundaries = evidence::Failure("unavailable", "CATICciPly.GetGeometry/CATFace.CreateBoundaryIterator");
  try
  {
    CATISpecObject_var contour;
    CaaInterfaceGuard<CATIGeometricalElement> geometry;
    if (SUCCEEDED(ply->GetGeometry(contour)) && contour != NULL_var &&
        SUCCEEDED(contour->QueryInterface(IID_CATIGeometricalElement, reinterpret_cast<void**>(&geometry.Out()))) && geometry.Get())
    {
      CATBody_var body = geometry.Get()->GetBodyResult();
      if (body != NULL_var)
      {
        contour_boundaries = NativeBoundaryLoops(body, "CATICciPly.GetGeometry/CATFace.CreateBoundaryIterator");
        CATLISTP(CATCell) cells;
        body->GetAllCells(cells, 0);
        std::ostringstream points;
        points << "[";
        for (int i = 1; i <= cells.Size(); ++i)
        {
          CATPoint* point = static_cast<CATVertex*>(cells[i])->GetPoint();
          if (!point) throw "vertex geometry unavailable";
          double x, y, z;
          point->GetCoord(x, y, z);
          if (i > 1) points << ",";
          points << "[" << evidence::Number(x) << "," << evidence::Number(y) << "," << evidence::Number(z) << "]";
        }
        points << "]";
        vertices = evidence::Text(points.str(), contour_api);
        vertices.value_type = "json";
        vertices.raw_unit = "mm";
        // 顶点按 CATBody 枚举顺序保留，不能冒充已排序的外轮廓或把孔环拼成一个环。
        Add(facts, "composite_contour_vertex_order", evidence::Text("native_cell_enumeration_not_loop_order", contour_api));
        CATLISTP(CATCell) edges;
        body->GetAllCells(edges, 1);
        double length = 0;
        for (int j = 1; j <= edges.Size(); ++j) length += static_cast<CATEdge*>(edges[j])->CalcLength();
        perimeter = Numeric(length, "mm", "CATICciPly.GetGeometry/CATEdge.CalcLength");
      }
    }
  }
  catch (...)
  {
    if (vertices.read_status != "available") vertices.read_status = "exception";
    perimeter.read_status = "exception";
  }
  Add(facts, "composite_contour_vertices_mm", vertices);
  Add(facts, "composite_contour_length_mm", perimeter);
  Add(facts, "composite_contour_native_boundary_loops", contour_boundaries);

  PropertyFact surface_boundaries = evidence::Failure("unavailable", "CATICciCompositesGeometry.GetResult/CATFace.CreateBoundaryIterator");
  try
  {
    CATICciCompositesGeometry_var composite_geometry;
    CATISpecObject_var result_spec;
    CaaInterfaceGuard<CATIGeometricalElement> surface_geometry;
    if (SUCCEEDED(ply->GetCompositesGeometry(composite_geometry)) && composite_geometry != NULL_var &&
        SUCCEEDED(composite_geometry->GetResult(result_spec)) && result_spec != NULL_var &&
        SUCCEEDED(result_spec->QueryInterface(IID_CATIGeometricalElement,
                  reinterpret_cast<void**>(&surface_geometry.Out()))) && surface_geometry.Get())
      surface_boundaries = NativeBoundaryLoops(surface_geometry.Get()->GetBodyResult(),
        "CATICciCompositesGeometry.GetResult/CATFace.CreateBoundaryIterator");
  }
  catch (...) { surface_boundaries = evidence::Failure("exception", "CATICciCompositesGeometry.GetResult/CATFace.CreateBoundaryIterator"); }
  Add(facts, "composite_surface_native_boundary_loops", surface_boundaries);

  const char* surface_api = "CATICciPly.GetCompositesGeometry/CATIInertia.GetInertia";
  PropertyFact area = evidence::Failure("unavailable", surface_api);
  try
  {
    CATICciCompositesGeometry_var shell;
    CaaInterfaceGuard<CATIInertia> inertia;
    if (SUCCEEDED(ply->GetCompositesGeometry(shell)) && shell != NULL_var &&
        SUCCEEDED(shell->QueryInterface(IID_CATIInertia, reinterpret_cast<void**>(&inertia.Out()))) && inertia.Get())
    {
      double density = 0, mass = 0, volume = 0, surface = 0;
      double position[3] = {0}, matrix[9] = {0}, axes[9] = {0}, moments[3] = {0};
      if (SUCCEEDED(inertia.Get()->GetInertia(&density, &mass, position, matrix, axes, moments, &volume, &surface)))
      {
        area = Numeric(surface, "m2", surface_api);
        Add(facts, "composite_center_x_m", Numeric(position[0], "m", surface_api));
        Add(facts, "composite_center_y_m", Numeric(position[1], "m", surface_api));
        Add(facts, "composite_center_z_m", Numeric(position[2], "m", surface_api));
        // 复材曲面的默认面密度不是铺层材料密度；其 mass 不能作为铺层重量入库。
      }
      else area.read_status = "failed";
    }
  }
  catch (...) { area.read_status = "exception"; }
  Add(facts, "composite_area_m2", area);
  return facts;
}
}
