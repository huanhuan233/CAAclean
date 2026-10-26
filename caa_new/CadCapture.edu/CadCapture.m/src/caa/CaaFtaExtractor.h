/* 声明从已打开文档采集 FTA 集合、视图、捕获和标注证据的入口。 */
#ifndef CADCAPTURE_CAA_CAAFTAEXTRACTOR_H
#define CADCAPTURE_CAA_CAAFTAEXTRACTOR_H

#include "caa/CaaCapabilityBroker.h"
#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

/* 采集结果分别追加至 PMI 层级、FTA 语义、关联和诊断集合。 */
class CaaFtaExtractor
{
public:
  /* document_handle 须保持有效；true 表示流程可继续，完整性应检查实体状态和诊断。 */
  bool Extract(CaaDocumentHandle& document_handle,
               CaptureIdRegistry& ids,
               CaaCapabilityBroker& broker,
               ReconstructionPackage& package);
};

}

#endif
