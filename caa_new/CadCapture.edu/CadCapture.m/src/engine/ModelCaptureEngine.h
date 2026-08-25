#ifndef CADCAPTURE_ENGINE_MODELCAPTUREENGINE_H
#define CADCAPTURE_ENGINE_MODELCAPTUREENGINE_H

#include "engine/CapturePolicy.h"
#include "engine/CaptureReport.h"
#include "engine/CaptureRequest.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class ModelCaptureEngine
{
public:
  bool Capture(const CaptureRequest& request,
               const CapturePolicy& policy,
               ReconstructionPackage& package,
               CaptureReport& report,
               std::string& error);
};

}

#endif
