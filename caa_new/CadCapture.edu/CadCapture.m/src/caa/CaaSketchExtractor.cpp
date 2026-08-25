#include "caa/CaaSketchExtractor.h"

namespace cadcapture {

bool CaaSketchExtractor::Extract(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "sketch_extractor";
  report.AddDiagnostic("info", "not_implemented", "sketch", "Sketch extraction is not implemented in bootstrap", report.stage);
  return true;
}

}
