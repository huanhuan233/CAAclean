#ifndef CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H
#define CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaSketchExtractor
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
