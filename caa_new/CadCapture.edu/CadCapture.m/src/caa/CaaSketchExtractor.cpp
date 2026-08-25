#include "caa/CaaSketchExtractor.h"

namespace cadcapture {

bool CaaSketchExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "planned", "sketch",
                                               "Sketch evidence extraction is planned until legacy sketch references are migrated",
                                               "sketch_extractor"));
  return true;
}

}
