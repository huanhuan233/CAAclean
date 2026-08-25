#ifndef CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H
#define CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaIdentityResolver
{
public:
  bool Resolve(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
