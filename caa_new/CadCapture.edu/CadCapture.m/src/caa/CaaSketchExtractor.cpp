#include "caa/CaaSketchExtractor.h"

namespace cadcapture {

// 中文：草图尚无专用 IR，此处仅告知缺口，不产生证据。
void CaaSketchExtractor::Extract(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "sketch",
                                               "Standalone sketch evidence is not implemented; generic spec tree remains available",
                                               "sketch_extractor"));
}

}
