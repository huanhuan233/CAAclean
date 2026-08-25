#include "caa/CaaLinkedDocumentResolver.h"

namespace cadcapture {

bool CaaLinkedDocumentResolver::Resolve(ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic("info", "linked_document_resolution_deferred", "links",
                                               "Phase 1B records same-document CATProduct references; external linked document opening is deferred unless exposed by the root product traversal",
                                               "linked_document_resolver"));
  return true;
}

}
