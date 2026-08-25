#include "caa/CaaProductEnumerator.h"

namespace cadcapture {

bool CaaProductEnumerator::Enumerate(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "product",
                                               "CATProduct recursive enumeration is not implemented in Phase 1A",
                                               "product_enumerator"));
  return true;
}

}
