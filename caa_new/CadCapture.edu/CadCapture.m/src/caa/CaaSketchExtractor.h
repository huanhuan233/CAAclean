#ifndef CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H
#define CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaSketchExtractor
{
public:
  // 中文：明确报告当前版本未单独采集草图，不伪造采集成功。
  void Extract(ReconstructionPackage& package);
};

}

#endif
