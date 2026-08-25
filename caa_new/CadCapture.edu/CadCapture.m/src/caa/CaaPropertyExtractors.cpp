#include "caa/CaaPropertyExtractors.h"

namespace cadcapture {

bool CaaPropertyExtractors::Extract(ReconstructionPackage& package)
{
  if (!package.document_graph.documents.empty())
  {
    PropertyFact fact;
    fact.subject_id = package.document_graph.documents[0].document_id;
    fact.group = "native_open";
    fact.key = "native_document_open_status";
    fact.display_name = "Native document open status";
    fact.raw_value = package.document_graph.documents[0].native_document_open_status;
    fact.display_value = fact.raw_value;
    fact.value_type = "string";
    fact.source_api = "bootstrap";
    fact.read_status = "available";
    package.properties.push_back(fact);
  }
  package.diagnostics.push_back(MakeDiagnostic("info", "stage_executed", "properties",
                                               "CaaPropertyExtractors executed", "property_extractors"));
  return true;
}

}
