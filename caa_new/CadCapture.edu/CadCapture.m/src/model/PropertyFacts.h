#ifndef CADCAPTURE_MODEL_PROPERTYFACTS_H
#define CADCAPTURE_MODEL_PROPERTYFACTS_H

#include <string>

namespace cadcapture {

struct PropertyFact
{
  std::string subject_id;
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

  PropertyFact() : value_type("string"), read_status("unavailable") {}
};

}

#endif
