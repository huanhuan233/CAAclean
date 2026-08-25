#ifndef CADCAPTURE_CAA_CAATOPOLOGYEXTRACTOR_H
#define CADCAPTURE_CAA_CAATOPOLOGYEXTRACTOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaTopologyExtractor
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
