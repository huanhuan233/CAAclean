#include "caa/CaaTopologyExtractor.h"

namespace cadcapture {

bool CaaTopologyExtractor::Extract(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "topology_extractor";
  report.AddDiagnostic("info", "not_implemented", "topology", "Topology extraction is not implemented in bootstrap", report.stage);
  return true;
}

}
