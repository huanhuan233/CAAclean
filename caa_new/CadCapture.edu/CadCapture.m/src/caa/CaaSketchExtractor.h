// 声明从活动文档绑定读取草图几何并写入语义分面的入口。
#ifndef CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H
#define CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H

#include "model/ReconstructionPackage.h"
#include "caa/CaaCapabilityBroker.h"
#include "model/CaptureIdRegistry.h"

namespace cadcapture {

// 使用包内原生绑定；调用期间对应 CATIA 文档必须保持打开。
class CaaSketchExtractor
{
public:
  // 补采全包草图，已由 NativeSketchDecoder 写出的对象跳过。
  void Extract(CaptureIdRegistry& ids, CaaCapabilityBroker& broker, ReconstructionPackage& package);
  // 仅处理指定文档；单个草图或元素不可读时保留其他可读结果。
  void ExtractForDocument(CaptureIdRegistry& ids, CaaCapabilityBroker& broker,
                          ReconstructionPackage& package, const std::string& document_id);
};

}

#endif
