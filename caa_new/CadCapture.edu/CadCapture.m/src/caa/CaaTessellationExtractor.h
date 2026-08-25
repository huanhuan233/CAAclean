#ifndef CADCAPTURE_CAA_CAATESSELLATIONEXTRACTOR_H
#define CADCAPTURE_CAA_CAATESSELLATIONEXTRACTOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaTessellationExtractor
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
