#ifndef CADCAPTURE_CAA_CAADOCUMENTSCANNER_H
#define CADCAPTURE_CAA_CAADOCUMENTSCANNER_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class CaaDocumentScanner
{
public:
  bool Scan(const std::string& input_path,
            CaaDocumentHandle& document_handle,
            CaptureIdRegistry& ids,
            ReconstructionPackage& package,
            std::string& error);
};

}

#endif
