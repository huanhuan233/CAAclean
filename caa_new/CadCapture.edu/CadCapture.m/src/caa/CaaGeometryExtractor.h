#ifndef CADCAPTURE_CAA_CAAGEOMETRYEXTRACTOR_H
#define CADCAPTURE_CAA_CAAGEOMETRYEXTRACTOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaGeometryExtractor
{
public:
  // 中文：审计拓扑阶段的几何证据；本模块不重复提取 CAA 几何。
  void Extract(ReconstructionPackage& package);
};

}

#endif
