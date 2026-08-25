#include "caa/CaaTessellationExtractor.h"

namespace cadcapture {

bool CaaTessellationExtractor::Extract(ReconstructionPackage& package)
{
  if (!package.geometry.empty())
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "tessellation_ranges_available", "tessellation",
                                                 "Face tessellation range summaries were emitted from CATICGMBodyTessellator",
                                                 "tessellation_extractor"));
    return true;
  }
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "tessellation",
                                               "Tessellation extraction is planned until legacy mesh evidence is migrated",
                                               "tessellation_extractor"));
  return true;
}

}
