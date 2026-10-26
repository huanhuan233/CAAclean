/* 定义拓扑单元、环与共边以及特征结果到最终体的映射证据。 */
#ifndef CADCAPTURE_MODEL_TOPOLOGYIR_H
#define CADCAPTURE_MODEL_TOPOLOGYIR_H

#include <string>
#include <vector>

namespace cadcapture {

/* 拓扑体或单元的结构与几何证据；缺少精确参数时仍可保留拓扑和测量信息。 */
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
  /* 坐标和长度为毫米、面积为平方毫米；读取时须同时检查各自可用标志。 */
  bool has_center;
  double center_mm[3];
  bool area_mm2_available;
  double area_mm2;
  bool length_mm_available;
  double length_mm;
  std::string geometry_orientation;
  std::string exact_geometry_type;
  /* 已编码的几何参数、参数域和包围盒 JSON 片段由输出层原样嵌入。 */
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

/* 拓扑实体之间的有向关系，以类型和读取状态说明证据含义。 */
struct TopologyRelation
{
  std::string from_topology_id;
  std::string to_topology_id;
  std::string relation_kind;
  std::string read_status;

  TopologyRelation() : read_status("unavailable") {}
};

/* 记录体内的边环及所属面，闭合状态可独立保持未知。 */
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

/* 记录边在环中的一次有向使用，通过前后共边 ID 保留遍历次序。 */
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

/* 保存特征中间结果体的单元及测量值，结果单元 ID 与最终体单元 ID 分开。 */
struct NativeFeatureResultCellEntity
{
  std::string result_cell_id;
  std::string result_id;
  std::string source_feature_id;
  long result_cell_index;
  long dimension;
  std::string cell_kind;
  /* 坐标和长度为毫米、面积为平方毫米；读取时须同时检查各自可用标志。 */
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

/* 保存结果单元到最终体单元的映射证据、候选集合和残差，未确认候选不能视为唯一匹配。 */
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
  /* 当前面匹配保存面积差，单位为平方毫米；中心残差单独使用毫米。 */
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
