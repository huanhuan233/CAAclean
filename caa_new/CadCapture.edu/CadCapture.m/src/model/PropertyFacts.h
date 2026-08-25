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
  std::string display_value;
  std::string display_unit;
  std::string value_type;
  std::string source_api;
  std::string read_status;
  std::string authority;
  long display_order;
  bool read_only;

  PropertyFact() : value_type("string"), read_status("unavailable"), display_order(0), read_only(true) {}
};

}

#endif
