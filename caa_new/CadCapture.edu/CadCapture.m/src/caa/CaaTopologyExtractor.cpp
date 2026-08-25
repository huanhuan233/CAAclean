#include "caa/CaaTopologyExtractor.h"

namespace cadcapture {

bool CaaTopologyExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "topology",
                                               "Topology extraction is not implemented in Phase 1A",
                                               "topology_extractor"));
  return true;
}

}
