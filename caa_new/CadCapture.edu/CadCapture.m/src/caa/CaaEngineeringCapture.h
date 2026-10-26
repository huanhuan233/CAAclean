// 声明读取公式依赖、几何引用及扫掠中心线工程证据的入口。
#ifndef CADCAPTURE_CAA_ENGINEERING_CAPTURE_H
#define CADCAPTURE_CAA_ENGINEERING_CAPTURE_H
#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"
namespace cadcapture {
// 原生绑定只在所属文档存活时使用；计算结果作为普通属性保存在采集包中。
class CaaEngineeringCapture {
public:
  // 在原生对象注册完成后采集关系与中心线；结果沿现有属性和依赖契约输出。
  // first_binding 是本批原生绑定起点；末尾的路径投影仍检查全包已有几何事实。
  void Extract(CaptureIdRegistry& ids, ReconstructionPackage& package, size_t first_binding = 0);
};
}
#endif
