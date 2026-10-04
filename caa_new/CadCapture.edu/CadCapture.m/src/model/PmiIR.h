#ifndef CADCAPTURE_MODEL_PMIIR_H
#define CADCAPTURE_MODEL_PMIIR_H

#include <string>
#include <vector>

namespace cadcapture {

struct PmiEntity
{
  std::string pmi_id;
  std::string subject_id;
  std::string pmi_kind;
  std::string source_api;
  std::string evidence_status;
  std::string alias;
  std::string owning_document_id;
  std::string ownership_status;
  std::string parent_pmi_id;
  long set_index;
  long tps_count;
  long geometry_reference_count;
  std::string read_status;

  PmiEntity()
    : set_index(0),
      tps_count(0),
      geometry_reference_count(0),
      read_status("unavailable"),
      ownership_status("unresolved")
  {
  }
};

struct PmiAssociation
{
  std::string pmi_id;
  std::string target_id;
  std::string association_kind;
  std::string read_status;

  PmiAssociation() : read_status("unavailable") {}
};

struct FtaSemanticEntity
{
  std::string fta_semantic_id;
  std::string fta_set_id;
  long component_index;
  std::string read_status;
  std::string component_kind;
  std::vector<std::string> supported_interface_keys;
  long semantic_interface_count;
  long all_semantic_interface_count;
  std::string validation_text;
  std::string validation_text_status;
  std::string annotation_text;
  std::string annotation_text_status;
  std::string annotation_text_source;
  long semantic_check_status_raw;
  std::string semantic_check_diagnostic;
  std::string topology_mapping_status;
  std::string value_source;

  FtaSemanticEntity()
    : component_index(0),
      semantic_interface_count(0),
      all_semantic_interface_count(0),
      semantic_check_status_raw(-1),
      validation_text_status("unavailable"),
      annotation_text_status("unsupported"),
      topology_mapping_status("not_available")
  {
  }
};

}

#endif
