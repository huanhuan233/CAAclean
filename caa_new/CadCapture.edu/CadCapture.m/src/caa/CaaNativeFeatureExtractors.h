#ifndef CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H
#define CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H

#include "caa/CaaCapabilityBroker.h"
#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"

namespace cadcapture {

class CaaNativeFeatureExtractors
{
public:
  bool Extract(CaptureIdRegistry& ids,
               CaaCapabilityBroker& broker,
               ReconstructionPackage& package);
};

}

#endif
