#ifndef CADCAPTURE_CAA_CAAPARTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPARTENUMERATOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaPartEnumerator
{
public:
  bool Enumerate(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
