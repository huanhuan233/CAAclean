#include "caa/CaaGeometryExtractor.h"

namespace cadcapture {

bool CaaGeometryExtractor::Extract(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "geometry_extractor";
  report.AddDiagnostic("info", "not_implemented", "geometry", "Geometry extraction is not implemented in bootstrap", report.stage);
  return true;
}

}
