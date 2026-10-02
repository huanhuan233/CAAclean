#ifndef CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H
#define CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H

#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaIdentityResolver
{
public:
  // 中文：审计上游已经采集的身份，不改写稳定 ID，也不冒充新解析。
  void Resolve(ReconstructionPackage& package);
};

}

#endif
