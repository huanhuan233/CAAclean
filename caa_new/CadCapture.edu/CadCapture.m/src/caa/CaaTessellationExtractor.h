#ifndef CADCAPTURE_CAA_CAATESSELLATIONEXTRACTOR_H
#define CADCAPTURE_CAA_CAATESSELLATIONEXTRACTOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaTessellationExtractor
{
public:
  // 中文：审计拓扑阶段的真实三角形产物，不按范围记录数宣称网格可用。
  void Extract(ReconstructionPackage& package);
};

}

#endif
