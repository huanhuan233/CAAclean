/* 定义几何表示摘要和可序列化的三角网格坐标记录。 */
#ifndef CADCAPTURE_MODEL_GEOMETRYIR_H
#define CADCAPTURE_MODEL_GEOMETRYIR_H

#include <string>

namespace cadcapture {

/* 区分曲线、曲面和离散网格；未知值表示尚未得到具体类型。 */
enum GeometryKind
{
  GeometryUnknown,
  GeometryCurve,
  GeometrySurface,
  GeometryTessellation
};

/* 记录几何表示的所属对象、拓扑面和三角形范围；摘要计数与真实顶点数据分开保存。 */
struct GeometryEntity
{
  std::string geometry_id;
  std::string subject_id;
  std::string body_topology_id;
  std::string topology_id;
  std::string geometry_kind;
  GeometryKind kind;
  std::string value_source;
  long primitive_index;
  /* 三角形起点与数量描述采集到的范围；估算数量不等于已输出的三角形。 */
  long triangle_start;
  long triangle_count;
  long point_count;
  long isolated_triangle_count;
  long strip_count;
  long fan_count;
  long polygon_count;
  long estimated_triangle_count;
  short face_orientation_side;
  bool planar;
  std::string representation_status;

  GeometryEntity()
    : kind(GeometryUnknown),
      primitive_index(0),
      triangle_start(0),
      triangle_count(0),
      point_count(0),
      isolated_triangle_count(0),
      strip_count(0),
      fan_count(0),
      polygon_count(0),
      estimated_triangle_count(0),
      face_orientation_side(0),
      planar(false),
      representation_status("unavailable")
  {
  }
};

/* 保存三角形与面映射的关联，以及按三个 xyz 顶点连续排列的毫米坐标。 */
struct MeshTriangleEntity
{
  std::string triangle_id;
  std::string mesh_map_id;
  std::string body_id;
  std::string face_cell_id;
  long triangle_index;
  long triangle_index_in_face;
  int vertex_ranks[3];
  double vertices_mm[9];
  /* 只有可用标志为真时才能消费法向量；默认零值不表示有效法向。 */
  bool normal_available;
  double normal[3];
  std::string source_primitive;
  std::string value_source;

  MeshTriangleEntity()
    : triangle_index(0),
      triangle_index_in_face(0),
      normal_available(false)
  {
    vertex_ranks[0] = vertex_ranks[1] = vertex_ranks[2] = 0;
    int i;
    for (i = 0; i < 9; ++i)
      vertices_mm[i] = 0.0;
    normal[0] = normal[1] = normal[2] = 0.0;
  }
};

}

#endif
