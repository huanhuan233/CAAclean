#ifndef CADCAPTURE_MODEL_PMIIR_H
#define CADCAPTURE_MODEL_PMIIR_H

#include <string>

namespace cadcapture {

struct PmiEntity
{
  std::string pmi_id;
  std::string subject_id;
  std::string pmi_kind;
  std::string read_status;

  PmiEntity() : read_status("unavailable") {}
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
