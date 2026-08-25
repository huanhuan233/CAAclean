#ifndef CADCAPTURE_MODEL_TOPOLOGYIR_H
#define CADCAPTURE_MODEL_TOPOLOGYIR_H

#include <string>

namespace cadcapture {

struct TopologyEntity
{
  std::string topology_id;
  std::string subject_id;
  std::string topology_kind;
  std::string parent_topology_id;
  std::string source_kind;
  std::string value_source;
  std::string stable_id_method;
  std::string stability_scope;
  long topology_index;
  long dimension;
  long vertex_count;
  long edge_count;
  long face_count;
  long volume_count;
  long domain_count;
  long internal_domain_count;
  bool has_center;
  double center_mm[3];
  bool area_mm2_available;
  double area_mm2;
  bool length_mm_available;
  double length_mm;
  std::string geometry_status;
  std::string measure_status;
  std::string read_status;

  TopologyEntity()
    : topology_index(0),
      dimension(-1),
      vertex_count(0),
      edge_count(0),
      face_count(0),
      volume_count(0),
      domain_count(0),
      internal_domain_count(0),
      has_center(false),
      area_mm2_available(false),
      area_mm2(0.0),
      length_mm_available(false),
      length_mm(0.0),
      read_status("unavailable")
  {
    center_mm[0] = center_mm[1] = center_mm[2] = 0.0;
  }
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
