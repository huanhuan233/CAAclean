#include "caa/CaaGeometryExtractor.h"

namespace cadcapture {

bool CaaGeometryExtractor::Extract(ReconstructionPackage& package)
{
  if (!package.geometry.empty())
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "geometry_summary_available", "geometry",
                                                 "Geometry/tessellation summary records were emitted by topology extraction",
                                                 "geometry_extractor"));
    return true;
  }
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "geometry",
                                               "Geometry extraction is planned until legacy exact geometry evidence is migrated",
                                               "geometry_extractor"));
  return true;
}

}
