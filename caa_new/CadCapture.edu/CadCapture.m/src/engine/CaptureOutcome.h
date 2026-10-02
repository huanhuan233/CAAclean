#ifndef CADCAPTURE_ENGINE_CAPTUREOUTCOME_H
#define CADCAPTURE_ENGINE_CAPTUREOUTCOME_H

#include "engine/CapturePolicy.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

// 中文：把必需采集阶段的诊断折叠成包级状态，并执行严格模式提交门禁。
class CaptureOutcome
{
public:
  // 中文：可选能力缺失不算必需阶段失败；严格模式遇到部分采集立即拒绝提交。
  static bool Finalize(ReconstructionPackage& package, const CapturePolicy& policy,
                       std::string& error);
};

}

#endif
