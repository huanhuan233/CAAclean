// 声明包级重建路线规划及精确几何、网格和树属性的能力摘要。
#ifndef CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H
#define CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

// 只选择已有证据允许的重建路线，不在这里创建 CAD 实体。
class ReconstructionPlanner
{
public:
  // 将路线和逐实体统计写回包，保留不完整几何的诊断。
  bool Plan(ReconstructionPackage& package);
};

// 包级能力摘要同时保留逐体完整性和真实网格可用性。
struct ReconstructionCompleteness
{
  size_t body_count;
  size_t exact_body_count;
  size_t incomplete_body_count;
  bool has_tessellation_coordinates;
  bool has_tree_or_properties;

  // 中文：初始状态没有可重建的 body，也不假设网格可用。
  ReconstructionCompleteness();
  // 中文：全部 body 完整时才宣称整包支持精确 B-Rep。
  bool SupportsExactBrep() const;
  // 中文：真实三角形可用、但精确 B-Rep 不完整时选择网格路线。
  bool SupportsTessellation() const;
};

// 汇总 B-Rep 与显示证据，供规划器统一判断能力。
class ReconstructionCompletenessEvaluator
{
public:
  // 中文：从逐体 B-Rep 结果和真实三角形汇总包级重建能力。
  ReconstructionCompleteness Evaluate(const ReconstructionPackage& package) const;
};

}

#endif
