#include "model/CaptureIdRegistry.h"
#include <sstream>

namespace cadcapture {

CaptureIdRegistry::CaptureIdRegistry()
  : _document_index(1),
    _object_index(1),
    _occurrence_index(1),
    _product_reference_index(1),
    _product_occurrence_index(1),
    _document_link_index(1)
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

}
