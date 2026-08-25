#include "caa/CaaNativeFeatureExtractors.h"

namespace cadcapture {

bool CaaNativeFeatureExtractors::Extract(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "native_feature_extractors";
  report.AddDiagnostic("info", "not_implemented", "native_features", "Native feature extraction is not implemented in bootstrap", report.stage);
  return true;
}

}
