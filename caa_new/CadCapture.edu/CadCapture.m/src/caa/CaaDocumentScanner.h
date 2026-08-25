#ifndef CADCAPTURE_CAA_CAADOCUMENTSCANNER_H
#define CADCAPTURE_CAA_CAADOCUMENTSCANNER_H

#include "engine/CaptureRequest.h"
#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class CaaDocumentScanner
{
public:
  bool Scan(const CaptureRequest& request,
            ReconstructionPackage& package,
            CaptureReport& report,
            std::string& error);
};

}

#endif
