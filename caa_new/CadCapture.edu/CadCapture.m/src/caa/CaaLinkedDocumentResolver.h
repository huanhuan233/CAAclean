#ifndef CADCAPTURE_CAA_CAALINKEDDOCUMENTRESOLVER_H
#define CADCAPTURE_CAA_CAALINKEDDOCUMENTRESOLVER_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaLinkedDocumentResolver
{
public:
  // 中文：审计上游文档链接和关联定义，不在此重复打开或伪造关联文档。
  void Resolve(ReconstructionPackage& package);
};

}

#endif
