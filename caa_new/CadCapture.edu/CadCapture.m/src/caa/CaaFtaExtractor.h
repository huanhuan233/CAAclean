#ifndef CADCAPTURE_CAA_CAAFTAEXTRACTOR_H
#define CADCAPTURE_CAA_CAAFTAEXTRACTOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaFtaExtractor
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
