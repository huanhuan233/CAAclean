#include "caa/CaaCompositeGeometry.h"
#include "caa/CaaPropertyEvidence.h"
#include "caa/CaaGuards.h"
#include <CATICciPly.h>
#include <CATICciCompositesGeometry.h>
#include <CATIGeometricalElement.h>
#include <CATIInertia.h>
#include <CATBody.h>
#include <CATEdge.h>
#include <CATVertex.h>
#include <CATPoint.h>
#include <ListPOfCATCell.h>

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
}

std::vector<PropertyFact> ReadCompositeGeometry(CATICciPly* ply)
{
  std::vector<PropertyFact> facts;
  const char* contour_api = "CATICciPly.GetGeometry/CATIGeometricalElement.GetBodyResult";
  PropertyFact vertices = evidence::Failure("unavailable", contour_api);
  PropertyFact perimeter = evidence::Failure("unavailable", contour_api);
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
