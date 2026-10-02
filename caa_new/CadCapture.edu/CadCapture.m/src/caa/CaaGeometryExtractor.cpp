#include "caa/CaaGeometryExtractor.h"
#include "model/CaptureEvidenceSummary.h"

namespace cadcapture {

// 中文：按精确参数与真实网格分级，不把任意空摘要标为可用几何。
void CaaGeometryExtractor::Extract(ReconstructionPackage& package)
{
  if (CaptureEvidenceSummary::HasExactGeometry(package))
  {
    package.diagnostics.push_back(MakeDiagnostic("info", "exact_geometry_evidence_available", "geometry",
                                                 "Exact geometry parameters were emitted by topology extraction",
                                                 "geometry_extractor"));
    return;
  }
  package.diagnostics.push_back(MakeDiagnostic("info", CaptureEvidenceSummary::HasMesh(package) ? "mesh_geometry_evidence_available" : "exact_geometry_unavailable", "geometry",
                                               CaptureEvidenceSummary::HasMesh(package) ? "Only tessellation evidence is available; exact geometry was not established"
                                                                                        : "No exact geometry evidence was established",
                                               "geometry_extractor"));
}

}
