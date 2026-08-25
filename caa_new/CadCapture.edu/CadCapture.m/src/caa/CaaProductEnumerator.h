#ifndef CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaProductEnumerator
{
public:
  bool Enumerate(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
