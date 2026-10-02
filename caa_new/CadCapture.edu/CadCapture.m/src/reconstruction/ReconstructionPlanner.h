#ifndef CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H
#define CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONPLANNER_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class ReconstructionPlanner
{
public:
  bool Plan(ReconstructionPackage& package);
};

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

class ReconstructionCompletenessEvaluator
{
public:
  // 中文：从逐体 B-Rep 结果和真实三角形汇总包级重建能力。
  ReconstructionCompleteness Evaluate(const ReconstructionPackage& package) const;
};

}

#endif
