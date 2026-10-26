/* 声明装配结构枚举及根 CATPart 产品属性采集入口。 */
#ifndef CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class CaaProductEnumerator
{
public:
  bool Enumerate(CaaDocumentHandle& document_handle,
                 CaptureIdRegistry& ids,
                 ReconstructionPackage& package,
                 std::string& error);
};

}

#endif
