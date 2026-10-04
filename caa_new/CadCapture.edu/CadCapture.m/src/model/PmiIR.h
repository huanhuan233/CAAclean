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
  std::string coordinate_frame_status;
  std::string plane_origin;
  std::string plane_x_axis;
  std::string plane_y_axis;
  std::string plane_normal;
  std::string camera_status;
  long set_index;
  long tps_count;
  long geometry_reference_count;
  std::string read_status;

  PmiEntity()
    : set_index(0),
      tps_count(0),
      geometry_reference_count(0),
      read_status("unavailable"),
      ownership_status("unresolved"),
      coordinate_frame_status("unavailable"),
      camera_status("unavailable")
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

struct FtaRawField
{
  std::string key;
  std::string raw_value;
  std::string unit;
  std::string read_status;
  std::string source_api;

  FtaRawField() : read_status("unavailable") {}
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
  std::string native_alias;
  std::vector<FtaRawField> raw_fields;
  long annotation_ttrs_count;
  std::string annotation_ttrs_status;
  std::string native_geometry_link_status;

  FtaSemanticEntity()
    : component_index(0),
      semantic_interface_count(0),
      all_semantic_interface_count(0),
      semantic_check_status_raw(-1),
      annotation_ttrs_count(0),
      annotation_ttrs_status("unavailable"),
      native_geometry_link_status("unresolved"),
      validation_text_status("unavailable"),
      annotation_text_status("unsupported"),
      topology_mapping_status("not_available")
  {
  }
};

}

#endif
