#ifndef CADCAPTURE_MODEL_CAPTUREIDREGISTRY_H
#define CADCAPTURE_MODEL_CAPTUREIDREGISTRY_H

#include <string>

namespace cadcapture {

class CaptureIdRegistry
{
public:
  CaptureIdRegistry();

  std::string NextDocumentId();
  std::string NextObjectId();
  std::string NextOccurrenceId();
  std::string NextProductReferenceId();
  std::string NextProductOccurrenceId();
  std::string NextDocumentLinkId();

private:
  std::string Next(const char* prefix, long& value);

  long _document_index;
  long _object_index;
  long _occurrence_index;
  long _product_reference_index;
  long _product_occurrence_index;
  long _document_link_index;
};

}

#endif
