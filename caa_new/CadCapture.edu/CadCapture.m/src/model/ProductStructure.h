#ifndef CADCAPTURE_MODEL_PRODUCTSTRUCTURE_H
#define CADCAPTURE_MODEL_PRODUCTSTRUCTURE_H

#include <string>
#include <vector>

namespace cadcapture {

struct ProductReferenceEntity
{
  std::string reference_id;
  std::string referenced_document_id;
  std::string part_number;
  std::string display_name;
  std::string reference_document_name;
  std::string reference_document_kind;
  std::string definition_status;
  std::string value_source;
  std::string identity_method;
  std::vector<std::string> diagnostic_ids;

  ProductReferenceEntity()
    : definition_status("unavailable"),
      value_source("unavailable"),
      identity_method("unavailable")
  {
  }
};

}

#endif
