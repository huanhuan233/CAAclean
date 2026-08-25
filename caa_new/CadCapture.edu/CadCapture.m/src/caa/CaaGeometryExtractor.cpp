#include "caa/CaaGeometryExtractor.h"

namespace cadcapture {

bool CaaGeometryExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "geometry",
                                               "Geometry extraction is not implemented in Phase 1A",
                                               "geometry_extractor"));
  return true;
}

}
