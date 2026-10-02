#ifndef CADCAPTURE_RECONSTRUCTION_BREPCOMPLETENESS_H
#define CADCAPTURE_RECONSTRUCTION_BREPCOMPLETENESS_H

#include "model/ReconstructionPackage.h"
#include <string>
#include <vector>

namespace cadcapture {

struct BrepBodyStatus
{
  std::string body_id;
  std::string status;
  std::string reason;
};

struct BrepCompleteness
{
  std::vector<BrepBodyStatus> bodies;
  size_t exact_body_count;
  size_t incomplete_body_count;
  BrepCompleteness() : exact_body_count(0), incomplete_body_count(0) {}
};

// 中文：逐体判定精确 B-Rep 能否独立重建，不跨 body 拼凑证据。
class BrepCompletenessEvaluator
{
public:
  // 中文：每个主实体和 ResultOUT 的所有必要面、边、顶点、闭合线框都须齐全。
  BrepCompleteness Evaluate(const ReconstructionPackage& package) const;
};

}

#endif
