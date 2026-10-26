/* 汇总上游对象身份采集情况并说明会话身份的适用范围。 */
#include "caa/CaaIdentityResolver.h"
#include "model/CaptureEvidenceSummary.h"

namespace cadcapture {

// 中文：列出上游身份实际覆盖程度；会话本地 ID 不被宣传为跨版本稳定 ID。
void CaaIdentityResolver::Resolve(ReconstructionPackage& package)
{
  const size_t captured = CaptureEvidenceSummary::CapturedIdentities(package);
  package.diagnostics.push_back(MakeDiagnostic("info", captured ? "identity_upstream_available" : "identity_unavailable",
                                               "identity", captured ? "Object identities were captured by native enumerators; stable cross-session IDs are not inferred"
                                                                    : "No object identity evidence was captured",
                                               "identity_resolver"));
}

}
