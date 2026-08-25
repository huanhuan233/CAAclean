#ifndef CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaProductEnumerator
{
public:
  bool Enumerate(ReconstructionPackage& package);
};

}

#endif
