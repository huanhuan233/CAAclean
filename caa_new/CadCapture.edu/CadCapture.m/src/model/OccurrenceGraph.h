#ifndef CADCAPTURE_MODEL_OCCURRENCEGRAPH_H
#define CADCAPTURE_MODEL_OCCURRENCEGRAPH_H

#include <string>
#include <vector>

namespace cadcapture {

struct ObjectOccurrence
{
  std::string occurrence_id;
  std::string object_id;
  std::string parent_occurrence_id;
  std::string document_id;
  std::string occurrence_path;
  std::string tree_path;
  long source_index;
  long container_index;
  std::string occurrence_role;
  std::string enumeration_source;
  std::string presentation_status;
  std::string occurrence_kind;
  std::string product_occurrence_id;
  std::string reference_id;
  std::string referenced_document_id;
  std::string capture_status;

  ObjectOccurrence() : source_index(0), container_index(0), capture_status("unavailable") {}
};

struct ProductOccurrence
{
  std::string occurrence_id;
  std::string parent_occurrence_id;
  std::string reference_id;
  std::string referenced_document_id;
  std::string instance_name;
  std::string part_number;
  std::string tree_path;
  std::string occurrence_path;
  long depth;
  long source_index;
  long child_count;
  std::vector<double> transform_4x4;
  std::string transform_status;
  std::string transform_source;
  std::string load_status;
  std::string capture_status;
  std::string presentation_status;
  std::string feature_definition_root_id;
  std::vector<std::string> diagnostic_ids;

  ProductOccurrence()
    : depth(0),
      source_index(0),
      child_count(0),
      transform_status("unavailable"),
      transform_source("unavailable"),
      load_status("unavailable"),
      capture_status("unavailable"),
      presentation_status("visible")
  {
    transform_4x4.push_back(1.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(1.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(1.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(0.0);
    transform_4x4.push_back(1.0);
  }
};

struct OccurrenceGraph
{
  std::vector<ObjectOccurrence> object_occurrences;
};

}

#endif
