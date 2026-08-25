#ifndef CADCAPTURE_MODEL_TOPOLOGYIR_H
#define CADCAPTURE_MODEL_TOPOLOGYIR_H

#include <string>

namespace cadcapture {

struct TopologyEntity
{
  std::string topology_id;
  std::string subject_id;
  std::string topology_kind;
  std::string read_status;

  TopologyEntity() : read_status("unavailable") {}
};

struct TopologyRelation
{
  std::string from_topology_id;
  std::string to_topology_id;
  std::string relation_kind;
  std::string read_status;

  TopologyRelation() : read_status("unavailable") {}
};

}

#endif
