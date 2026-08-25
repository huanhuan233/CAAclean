#include "caa/CaaNativeFeatureExtractors.h"

namespace cadcapture {

bool CaaNativeFeatureExtractors::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "native_features",
                                               "Native feature decoding is planned until legacy feature evidence is migrated",
                                               "native_feature_extractors"));
  return true;
}

}
