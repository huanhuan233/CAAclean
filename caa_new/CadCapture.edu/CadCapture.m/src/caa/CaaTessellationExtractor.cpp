#include "caa/CaaTessellationExtractor.h"

namespace cadcapture {

bool CaaTessellationExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "tessellation",
                                               "Tessellation extraction is not implemented in Phase 1A",
                                               "tessellation_extractor"));
  return true;
}

}
