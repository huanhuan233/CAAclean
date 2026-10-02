#ifndef CADCAPTURE_MODEL_CAPTUREEVIDENCESUMMARY_H
#define CADCAPTURE_MODEL_CAPTUREEVIDENCESUMMARY_H

#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

// 中文：按真实证据汇总占位阶段可声明的能力，不改变原生模型。
class CaptureEvidenceSummary
{
public:
  // 中文：仅真实顶点三角形或非零有效三角范围算可用网格。
  static bool HasMesh(const ReconstructionPackage& package);
  // 中文：精确参数化曲线/曲面须同时有类型和参数，纯拓扑不算精确几何。
  static bool HasExactGeometry(const ReconstructionPackage& package);
  // 中文：返回关联文档的可用、部分或不适用状态。
  static std::string LinkedDocuments(const ReconstructionPackage& package);
  // 中文：统计上游枚举阶段已捕获的对象身份，不冒充当前阶段新解析。
  static size_t CapturedIdentities(const ReconstructionPackage& package);
};

}

#endif
