#include "caa/CaaCapabilityBroker.h"

namespace cadcapture {

CapabilityStatus CaaCapabilityBroker::Check(const std::string& capability,
                                            ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", capability,
                                               "Capability query is not implemented in bootstrap",
                                               "capability_broker"));
  return CapabilityUnavailable;
}

}
