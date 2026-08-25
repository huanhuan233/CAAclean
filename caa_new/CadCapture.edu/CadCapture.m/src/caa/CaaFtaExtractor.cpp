#include "caa/CaaFtaExtractor.h"

namespace cadcapture {

bool CaaFtaExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "fta",
                                               "FTA extraction is not implemented in Phase 1A",
                                               "fta_extractor"));
  return true;
}

}
