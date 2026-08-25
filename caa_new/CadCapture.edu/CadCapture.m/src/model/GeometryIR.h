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
  GeometryKind kind;
  std::string representation_status;

  GeometryEntity() : kind(GeometryUnknown), representation_status("unavailable") {}
};

}

#endif
