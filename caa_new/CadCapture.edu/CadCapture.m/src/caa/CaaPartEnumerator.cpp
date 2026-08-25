#include "caa/CaaPartEnumerator.h"

namespace cadcapture {

bool CaaPartEnumerator::Enumerate(ReconstructionPackage& package, CaptureReport& report)
{
  if (package.document_graph.documents.size() == 1 &&
      package.document_graph.documents[0].document_kind == "catpart")
  {
    ObjectEntity object;
    object.object_id = "object_1";
    object.document_id = "doc_1";
    object.object_kind = "part_document_root";
    object.capture_status = "partial";
    object.identity.stable_id = "doc_1:root";
    object.identity.native_label = "bootstrap part root";
    object.identity.scope = IdentityDocumentLocal;
    object.identity.read_status = "bootstrap";
    package.objects.push_back(object);

    ObjectOccurrence occurrence;
    occurrence.occurrence_id = "occurrence_1";
    occurrence.object_id = object.object_id;
    occurrence.document_id = object.document_id;
    occurrence.occurrence_path = "/part";
    occurrence.capture_status = "partial";
    package.occurrence_graph.object_occurrences.push_back(occurrence);
  }
  report.stage = "part_enumerator";
  report.AddDiagnostic("info", "stage_executed", "part", "CaaPartEnumerator executed", report.stage);
  return true;
}

}
