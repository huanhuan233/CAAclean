#include "caa/CaaCapabilityBroker.h"

namespace cadcapture {

CapabilityStatus CaaCapabilityBroker::Check(const std::string& capability,
                                            ReconstructionPackage& package,
                                            CaptureReport& report)
{
  (void)package;
  report.stage = "capability_broker";
  report.AddDiagnostic("info", "not_implemented", capability, "Capability query is not implemented in bootstrap", report.stage);
  return CapabilityUnavailable;
}

}
