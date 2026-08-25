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
  std::string capture_status;

  ObjectOccurrence() : source_index(0), container_index(0), capture_status("unavailable") {}
};

struct ProductOccurrence
{
  std::string occurrence_id;
  std::string referenced_document_id;
  std::string instance_name;
  std::string capture_status;

  ProductOccurrence() : capture_status("unavailable") {}
};

struct OccurrenceGraph
{
  std::vector<ObjectOccurrence> object_occurrences;
  std::vector<ProductOccurrence> product_occurrences;
};

}

#endif
