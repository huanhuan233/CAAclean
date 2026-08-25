#include "caa/CaaLinkedDocumentResolver.h"

namespace cadcapture {

bool CaaLinkedDocumentResolver::Resolve(ReconstructionPackage& package, CaptureReport& report)
{
  (void)package;
  report.stage = "linked_document_resolver";
  report.AddDiagnostic("info", "not_implemented", "links", "Linked document resolution is not implemented in bootstrap", report.stage);
  return true;
}

}
