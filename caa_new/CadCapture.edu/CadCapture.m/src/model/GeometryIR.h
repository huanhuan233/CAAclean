#ifndef CADCAPTURE_MODEL_GEOMETRYIR_H
#define CADCAPTURE_MODEL_GEOMETRYIR_H

#include <string>

namespace cadcapture {

enum GeometryKind
{
  GeometryUnknown,
  GeometryCurve,
  GeometrySurface,
  GeometryTessellation
};

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
