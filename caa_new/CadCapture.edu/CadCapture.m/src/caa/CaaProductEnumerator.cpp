#include "caa/CaaProductEnumerator.h"

namespace cadcapture {

bool CaaProductEnumerator::Enumerate(ReconstructionPackage& package, CaptureReport& report)
{
  if (package.document_graph.documents.size() == 1 &&
      package.document_graph.documents[0].document_kind == "catproduct")
  {
    ObjectEntity object;
    object.object_id = "object_1";
    object.document_id = "doc_1";
    object.object_kind = "product_document_root";
    object.capture_status = "partial";
    package.objects.push_back(object);
  }
  report.stage = "product_enumerator";
  report.AddDiagnostic("info", "not_implemented", "product", "CATProduct recursive enumeration is not implemented in bootstrap", report.stage);
  return true;
}

}
