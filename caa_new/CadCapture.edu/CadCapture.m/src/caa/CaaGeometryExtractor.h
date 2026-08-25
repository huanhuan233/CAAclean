#ifndef CADCAPTURE_CAA_CAAGEOMETRYEXTRACTOR_H
#define CADCAPTURE_CAA_CAAGEOMETRYEXTRACTOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaGeometryExtractor
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
