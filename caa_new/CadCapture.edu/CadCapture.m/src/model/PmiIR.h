#ifndef CADCAPTURE_MODEL_PMIIR_H
#define CADCAPTURE_MODEL_PMIIR_H

#include <string>

namespace cadcapture {

struct PmiEntity
{
  std::string pmi_id;
  std::string subject_id;
  std::string pmi_kind;
  std::string source_api;
  std::string evidence_status;
  long set_index;
  long tps_count;
  long geometry_reference_count;
  std::string read_status;

  PmiEntity()
    : set_index(0),
      tps_count(0),
      geometry_reference_count(0),
      read_status("unavailable")
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

}

#endif
