#include "caa/CaaGeometryExtractor.h"

namespace cadcapture {

bool CaaGeometryExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "geometry",
                                               "Geometry extraction is planned until legacy exact geometry evidence is migrated",
                                               "geometry_extractor"));
  return true;
}

}
