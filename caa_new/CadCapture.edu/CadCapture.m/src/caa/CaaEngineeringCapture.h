#ifndef CADCAPTURE_CAA_ENGINEERING_CAPTURE_H
#define CADCAPTURE_CAA_ENGINEERING_CAPTURE_H
#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"
namespace cadcapture {
class CaaEngineeringCapture {
public:
  // 在原生对象注册完成后采集关系与中心线；结果沿现有属性和依赖契约输出。
  void Extract(CaptureIdRegistry& ids, ReconstructionPackage& package, size_t first_binding = 0);
};
}
#endif
