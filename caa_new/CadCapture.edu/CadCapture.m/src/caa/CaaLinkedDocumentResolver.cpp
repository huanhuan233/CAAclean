#include "caa/CaaLinkedDocumentResolver.h"

namespace cadcapture {

bool CaaLinkedDocumentResolver::Resolve(CaaDocumentHandle& document_handle,
                                        CaptureIdRegistry& ids,
                                        ReconstructionPackage& package)
{
  (void)document_handle;
  (void)ids;
  package.diagnostics.push_back(MakeDiagnostic("info", "linked_document_resolution_partial", "links",
                                               "Linked document evidence is recorded from CATIProduct/CATILinkableObject when available; unresolved links remain explicit instead of being mapped to the root document",
                                               "linked_document_resolver"));
  return true;
}

}
