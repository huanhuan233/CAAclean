#include "caa/CaaSketchExtractor.h"

namespace cadcapture {

bool CaaSketchExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "sketch",
                                               "Sketch extraction is not implemented in Phase 1A",
                                               "sketch_extractor"));
  return true;
}

}
