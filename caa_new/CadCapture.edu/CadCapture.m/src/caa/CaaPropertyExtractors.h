#ifndef CADCAPTURE_CAA_CAAPROPERTYEXTRACTORS_H
#define CADCAPTURE_CAA_CAAPROPERTYEXTRACTORS_H

#include "caa/CaaCapabilityBroker.h"
#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"

namespace cadcapture {

class CaaPropertyExtractors
{
public:
  bool Extract(CaptureIdRegistry& ids,
               CaaCapabilityBroker& broker,
               ReconstructionPackage& package);
};

}

#endif
