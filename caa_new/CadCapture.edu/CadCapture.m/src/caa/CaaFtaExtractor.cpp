#include "caa/CaaFtaExtractor.h"

namespace cadcapture {

bool CaaFtaExtractor::Extract(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "fta_extractor";
  report.AddDiagnostic("info", "not_implemented", "fta", "FTA extraction is not implemented in bootstrap", report.stage);
  return true;
}

}
