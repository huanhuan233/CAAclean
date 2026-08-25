#include "caa/CaaIdentityResolver.h"

namespace cadcapture {

bool CaaIdentityResolver::Resolve(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "identity_resolver";
  report.AddDiagnostic("info", "stage_executed", "identity", "CaaIdentityResolver executed", report.stage);
  return true;
}

}
