#include "caa/CaaTopologyExtractor.h"

namespace cadcapture {

bool CaaTopologyExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "topology",
                                               "Topology extraction is planned until legacy topology evidence is migrated",
                                               "topology_extractor"));
  return true;
}

}
