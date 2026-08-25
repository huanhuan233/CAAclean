#ifndef CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H
#define CADCAPTURE_CAA_CAAIDENTITYRESOLVER_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaIdentityResolver
{
public:
  bool Resolve(ReconstructionPackage& package);
};

}

#endif
