#ifndef CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H
#define CADCAPTURE_CAA_CAANATIVEFEATUREEXTRACTORS_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaNativeFeatureExtractors
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
