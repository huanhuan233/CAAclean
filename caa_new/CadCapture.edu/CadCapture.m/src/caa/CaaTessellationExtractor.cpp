#include "caa/CaaTessellationExtractor.h"

namespace cadcapture {

bool CaaTessellationExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "tessellation",
                                               "Tessellation extraction is planned until legacy mesh evidence is migrated",
                                               "tessellation_extractor"));
  return true;
}

}
