#ifndef CADCAPTURE_MODEL_GEOMETRYSTATUSPROJECTOR_H
#define CADCAPTURE_MODEL_GEOMETRYSTATUSPROJECTOR_H

#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

// 中文：把最终拓扑和几何证据归属到对象属性，供入库与前端面板复用。
class GeometryStatusProjector
{
public:
  // 中文：在全部文档拓扑采集结束后更新每个对象唯一的 geometry_status 属性。
  void Apply(CaptureIdRegistry& ids, ReconstructionPackage& package) const;
};

}

#endif
