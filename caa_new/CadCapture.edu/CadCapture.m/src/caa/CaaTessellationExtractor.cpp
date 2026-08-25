#include "caa/CaaTessellationExtractor.h"

namespace cadcapture {

bool CaaTessellationExtractor::Extract(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "tessellation_extractor";
  report.AddDiagnostic("info", "not_implemented", "tessellation", "Tessellation extraction is not implemented in bootstrap", report.stage);
  return true;
}

}
