#ifndef CADCAPTURE_MODEL_SEMANTICFACTS_H
#define CADCAPTURE_MODEL_SEMANTICFACTS_H

#include <string>

namespace cadcapture {

struct SemanticFacet
{
  std::string facet_id;
  std::string subject_id;
  std::string facet_kind;
  std::string read_status;

  SemanticFacet() : read_status("unavailable") {}
};

struct FeatureDependency
{
  std::string from_feature_id;
  std::string to_feature_id;
  std::string dependency_kind;
  std::string read_status;

  FeatureDependency() : read_status("unavailable") {}
};

}

#endif
