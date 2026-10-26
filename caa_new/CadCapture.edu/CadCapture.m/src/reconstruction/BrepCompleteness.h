// 定义逐实体 B-Rep 完整性结果与评估接口，避免跨实体拼凑重建证据。
#ifndef CADCAPTURE_RECONSTRUCTION_BREPCOMPLETENESS_H
#define CADCAPTURE_RECONSTRUCTION_BREPCOMPLETENESS_H

#include "model/ReconstructionPackage.h"
#include <string>
#include <vector>

namespace cadcapture {

// 保留单个实体的状态和首个不完整原因，便于诊断具体证据缺口。
struct BrepBodyStatus
{
  std::string body_id;
  std::string status;
  std::string reason;
};

// 汇总逐实体结果，精确与不完整实体分别计数。
struct BrepCompleteness
{
  std::vector<BrepBodyStatus> bodies;
  size_t exact_body_count;
  size_t incomplete_body_count;
  // 初始没有已核验实体，不能把空结果当作完整 B-Rep。
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
