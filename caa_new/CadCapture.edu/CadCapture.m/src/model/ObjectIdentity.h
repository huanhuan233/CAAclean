#ifndef CADCAPTURE_MODEL_OBJECTIDENTITY_H
#define CADCAPTURE_MODEL_OBJECTIDENTITY_H

#include <string>

namespace cadcapture {

enum IdentityStabilityScope
{
  IdentityDocumentLocal,
  IdentitySessionLocal,
  IdentityUnavailable
};

struct ObjectIdentity
{
  std::string stable_id;
  std::string native_label;
  IdentityStabilityScope scope;
  std::string read_status;

  ObjectIdentity() : scope(IdentityUnavailable), read_status("unavailable") {}
};

struct ObjectEntity
{
  std::string object_id;
  std::string document_id;
  std::string object_kind;
  std::string display_name;
  std::string internal_name;
  std::string startup_type;
  std::string update_status;
  ObjectIdentity identity;
  std::string capture_status;

  ObjectEntity() : capture_status("unavailable") {}
};

}

#endif
