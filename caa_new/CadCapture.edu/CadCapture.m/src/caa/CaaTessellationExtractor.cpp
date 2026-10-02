#include "caa/CaaTessellationExtractor.h"
#include "model/CaptureEvidenceSummary.h"

namespace cadcapture {

// 中文：无三角形时明确报告不可用，即使 CAA 已创建空的面网格范围。
void CaaTessellationExtractor::Extract(ReconstructionPackage& package)
{
  if (CaptureEvidenceSummary::HasMesh(package))
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "tessellation_triangles_available", "tessellation",
                                                 "Nonzero triangle payloads were emitted by topology extraction",
                                                 "tessellation_extractor"));
    return;
  }
  package.diagnostics.push_back(MakeDiagnostic("info", "tessellation_unavailable", "tessellation",
                                               "No usable triangle payload was captured",
                                               "tessellation_extractor"));
}

}
