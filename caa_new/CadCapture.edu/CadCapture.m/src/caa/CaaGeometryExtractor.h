#ifndef CADCAPTURE_CAA_CAAGEOMETRYEXTRACTOR_H
#define CADCAPTURE_CAA_CAAGEOMETRYEXTRACTOR_H

#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaGeometryExtractor
{
public:
  bool Extract(ReconstructionPackage& package);
};

}

#endif
