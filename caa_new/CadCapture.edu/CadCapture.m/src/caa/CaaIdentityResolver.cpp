#include "caa/CaaIdentityResolver.h"

namespace cadcapture {

bool CaaIdentityResolver::Resolve(CaptureIdRegistry& ids, ReconstructionPackage& package)
{
  (void)ids;
  package.diagnostics.push_back(MakeDiagnostic("info", "stage_executed", "identity",
                                               "CaaIdentityResolver executed", "identity_resolver"));
  return true;
}

}
