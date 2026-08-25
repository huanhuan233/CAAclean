#ifndef CADCAPTURE_CAA_CAATESSELLATIONEXTRACTOR_H
#define CADCAPTURE_CAA_CAATESSELLATIONEXTRACTOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaTessellationExtractor
{
public:
  bool Extract(ReconstructionPackage& package);
};

}

#endif
