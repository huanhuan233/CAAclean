#ifndef CADCAPTURE_MODEL_PROPERTYFACTS_H
#define CADCAPTURE_MODEL_PROPERTYFACTS_H

#include <string>

namespace cadcapture {

struct PropertyFact
{
  std::string property_id;
  std::string subject_id;
  std::string tab_id;
  std::string tab_label;
  std::string group_id;
  std::string group_label;
  std::string group;
  std::string key;
  std::string display_name;
  std::string raw_value;
  std::string raw_unit;
  std::string raw_display_text;
  std::string display_value;
  std::string display_unit;
  std::string value_type;
  bool has_normalized_numeric_value;
  double normalized_numeric_value;
  std::string normalized_unit;
  std::string normalization_status;
  std::string source_api;
  std::string read_status;
  std::string authority;
  long display_order;
  bool read_only;
  std::string hidden_status;

  PropertyFact()
    : value_type("string"),
      has_normalized_numeric_value(false),
      normalized_numeric_value(0.0),
      normalization_status("not_applicable"),
      read_status("unavailable"),
      display_order(0),
      read_only(true),
      hidden_status("unknown")
  {
  }
};

}

#endif
