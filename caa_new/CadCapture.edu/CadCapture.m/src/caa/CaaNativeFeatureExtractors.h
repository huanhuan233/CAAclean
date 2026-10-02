#ifndef CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H
#define CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H

#include "caa/CaaCapabilityBroker.h"
#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"
#include <string>

namespace cadcapture {

class CaaNativeFeatureExtractors
{
public:
  // 中文：采集尚未解码的对象，供根文档的常规链路使用。
  bool Extract(CaptureIdRegistry& ids,
               CaaCapabilityBroker& broker,
               ReconstructionPackage& package);

  // 中文：关联文档仍打开时只解码该文档对象，避免关闭后访问失效的原生绑定。
  bool ExtractForDocument(CaptureIdRegistry& ids,
                          CaaCapabilityBroker& broker,
                          ReconstructionPackage& package,
                          const std::string& document_id);
};

}

#endif
