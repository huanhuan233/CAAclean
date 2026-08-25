#ifndef CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H
#define CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H

#include "model/ReconstructionPackage.h"
#include "model/CaptureIdRegistry.h"

namespace cadcapture {

class CaaNativeFeatureExtractors
{
public:
  bool Extract(CaptureIdRegistry& ids, ReconstructionPackage& package);
};

}

#endif
