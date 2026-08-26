#ifndef CADCAPTURE_MODEL_TOPOLOGYIR_H
#define CADCAPTURE_MODEL_TOPOLOGYIR_H

#include <string>
#include <vector>

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
  std::string geometry_orientation;
  std::string exact_geometry_type;
  std::string geometry_parameters_json;
  std::string parameter_domain_json;
  std::string bounding_box_json;
  std::string material_side;
  std::vector<std::string> boundary_cell_ids;
  std::vector<std::string> adjacent_cell_ids;
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

struct NativeTopologyWireEntity
{
  std::string wire_id;
  std::string body_id;
  long wire_index;
  std::string wire_kind;
  std::string owning_face_id;
  long owning_face_topology_index;
  long edge_count;
  std::string closed_status;
  std::string value_source;

  NativeTopologyWireEntity()
    : wire_index(0),
      owning_face_topology_index(0),
      edge_count(0),
      closed_status("unknown")
  {
  }
};

struct NativeTopologyCoedgeEntity
{
  std::string coedge_id;
  std::string body_id;
  std::string wire_id;
  std::string owning_face_id;
  std::string edge_cell_id;
  std::string previous_coedge_id;
  std::string next_coedge_id;
  long coedge_index;
  long coedge_index_in_wire;
  short edge_orientation_side;
  std::string orientation_status;
  std::string value_source;

  NativeTopologyCoedgeEntity()
    : coedge_index(0),
      coedge_index_in_wire(0),
      edge_orientation_side(0)
  {
  }
};

struct NativeFeatureResultCellEntity
{
  std::string result_cell_id;
  std::string result_id;
  std::string source_feature_id;
  long result_cell_index;
  long dimension;
  std::string cell_kind;
  bool has_center;
  double center_mm[3];
  bool area_mm2_available;
  double area_mm2;
  bool length_mm_available;
  double length_mm;
  std::string read_status;
  std::string stable_id_method;
  std::string value_source;

  NativeFeatureResultCellEntity()
    : result_cell_index(0),
      dimension(-1),
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

struct NativeFeatureTopologyLinkEntity
{
  std::string link_id;
  std::string source_feature_id;
  std::string result_id;
  std::string result_cell_id;
  std::string final_cell_id;
  std::string final_body_id;
  std::string mapping_direction;
  std::string mapping_status;
  std::string mapping_method;
  std::string authority;
  std::string persistent_reference;
  std::string relation_kind;
  std::vector<std::string> candidate_final_cell_ids;
  double confidence;
  double center_residual_mm;
  double measure_residual;
  long candidate_count;

  NativeFeatureTopologyLinkEntity()
    : confidence(0.0),
      center_residual_mm(0.0),
      measure_residual(0.0),
      candidate_count(0)
  {
  }
};

}

#endif
