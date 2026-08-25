#include "caa/CaaNativeFeatureExtractors.h"

namespace cadcapture {

bool CaaNativeFeatureExtractors::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "native_features",
                                               "Native feature extraction is not implemented in Phase 1A",
                                               "native_feature_extractors"));
  return true;
}

}
