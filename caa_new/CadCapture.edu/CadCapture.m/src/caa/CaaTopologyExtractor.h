#ifndef CADCAPTURE_CAA_CAATOPOLOGYEXTRACTOR_H
#define CADCAPTURE_CAA_CAATOPOLOGYEXTRACTOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaTopologyExtractor
{
public:
  bool Extract(ReconstructionPackage& package);
};

}

#endif
