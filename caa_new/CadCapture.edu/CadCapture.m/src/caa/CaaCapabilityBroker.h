#ifndef CADCAPTURE_CAA_CAACAPABILITYBROKER_H
#define CADCAPTURE_CAA_CAACAPABILITYBROKER_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

enum CapabilityStatus
{
  CapabilityAvailable,
  CapabilityUnsupported,
  CapabilityUnavailable,
  CapabilityException
};

class CaaCapabilityBroker
{
public:
  CapabilityStatus Check(const std::string& capability,
                         ReconstructionPackage& package,
                         CaptureReport& report);
};

}

#endif
