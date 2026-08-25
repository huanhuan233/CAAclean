#include "model/CaptureIdRegistry.h"
#include <sstream>

namespace cadcapture {

CaptureIdRegistry::CaptureIdRegistry()
  : _document_index(1),
    _object_index(1),
    _occurrence_index(1),
    _product_reference_index(1),
    _product_occurrence_index(1),
    _document_link_index(1),
    _property_fact_index(1),
    _semantic_facet_index(1),
    _geometry_index(1),
    _topology_index(1),
    _pmi_index(1),
    _diagnostic_index(1)
{
}

std::string CaptureIdRegistry::Next(const char* prefix, long& value)
{
  std::ostringstream out;
  out << prefix << value++;
  return out.str();
}

std::string CaptureIdRegistry::NextDocumentId()
{
  return Next("doc_", _document_index);
}

std::string CaptureIdRegistry::NextObjectId()
{
  return Next("object_", _object_index);
}

std::string CaptureIdRegistry::NextOccurrenceId()
{
  return Next("occurrence_", _occurrence_index);
}

std::string CaptureIdRegistry::NextProductReferenceId()
{
  return Next("product_reference_", _product_reference_index);
}

std::string CaptureIdRegistry::NextProductOccurrenceId()
{
  return Next("product_occurrence_", _product_occurrence_index);
}

std::string CaptureIdRegistry::NextDocumentLinkId()
{
  return Next("document_link_", _document_link_index);
}

std::string CaptureIdRegistry::NextPropertyFactId()
{
  return Next("property_fact_", _property_fact_index);
}

std::string CaptureIdRegistry::NextSemanticFacetId()
{
  return Next("semantic_facet_", _semantic_facet_index);
}

std::string CaptureIdRegistry::NextGeometryId()
{
  return Next("geometry_", _geometry_index);
}

std::string CaptureIdRegistry::NextTopologyId()
{
  return Next("topology_", _topology_index);
}

std::string CaptureIdRegistry::NextPmiId()
{
  return Next("pmi_", _pmi_index);
}

std::string CaptureIdRegistry::NextDiagnosticId()
{
  return Next("diagnostic_", _diagnostic_index);
}

}
