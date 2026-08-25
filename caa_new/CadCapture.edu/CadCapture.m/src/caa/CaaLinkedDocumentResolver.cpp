#include "caa/CaaLinkedDocumentResolver.h"

namespace cadcapture {

bool CaaLinkedDocumentResolver::Resolve(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "not_implemented", "links",
                                               "Linked document resolution is not implemented in Phase 1A",
                                               "linked_document_resolver"));
  return true;
}

}
