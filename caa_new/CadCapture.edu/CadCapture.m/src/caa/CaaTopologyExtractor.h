#ifndef CADCAPTURE_CAA_CAATOPOLOGYEXTRACTOR_H
#define CADCAPTURE_CAA_CAATOPOLOGYEXTRACTOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class CaaTopologyExtractor
{
public:
  // 中文：采集根 CATPart 的最终体和结果体，保留既有调用方式。
  bool Extract(CaaDocumentHandle& document_handle,
               CaptureIdRegistry& ids,
               ReconstructionPackage& package);

  // 中文：在指定 CATPart 文档仍打开时采集其拓扑，不与其他文档对象混配。
  bool ExtractForDocument(CaaDocumentHandle& document_handle,
                          CaptureIdRegistry& ids,
                          ReconstructionPackage& package,
                          const std::string& document_id);
};

}

#endif
