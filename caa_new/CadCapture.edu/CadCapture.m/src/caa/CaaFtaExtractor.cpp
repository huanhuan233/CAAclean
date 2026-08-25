#include "caa/CaaFtaExtractor.h"

namespace cadcapture {

bool CaaFtaExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "fta",
                                               "FTA extraction is planned until legacy evidence is migrated",
                                               "fta_extractor"));
  return true;
}

}
