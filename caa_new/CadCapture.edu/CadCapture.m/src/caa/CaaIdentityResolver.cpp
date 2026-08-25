#include "caa/CaaIdentityResolver.h"

namespace cadcapture {

bool CaaIdentityResolver::Resolve(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "stage_executed", "identity",
                                               "CaaIdentityResolver executed", "identity_resolver"));
  return true;
}

}
