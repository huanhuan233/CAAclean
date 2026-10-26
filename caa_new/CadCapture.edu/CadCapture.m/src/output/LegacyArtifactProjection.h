/* 声明将重建包投影为旧版消费格式并核验树关系的接口。 */
#ifndef CADCAPTURE_OUTPUT_LEGACYARTIFACTPROJECTION_H
#define CADCAPTURE_OUTPUT_LEGACYARTIFACTPROJECTION_H

#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

/* 将同一重建包投影为兼容产物；写出目录由仓储提供，发布事务由仓储管理。 */
class LegacyArtifactProjection
{
public:
  /* 返回当前兼容投影模式名称，不据此声明模型几何已完整采集。 */
  std::string ProjectionStatus(const ReconstructionPackage& package) const;
  /* 写出兼容文件并检查树关系端点；写入失败可能已留下部分文件，由仓储处理暂存。 */
  bool Write(const ReconstructionPackage& package,
             const std::string& output_dir,
             std::string& error) const;
  /* 确认每条非根树关系的父子位置均存在于兼容特征集合中。 */
  bool ValidateRelationEndpoints(const ReconstructionPackage& package,
                                 std::string& error) const;
};

}

#endif
