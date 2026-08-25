#ifndef CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H
#define CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H

#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaIdentityResolver
{
public:
  bool Resolve(CaptureIdRegistry& ids, ReconstructionPackage& package);
};

}

#endif
