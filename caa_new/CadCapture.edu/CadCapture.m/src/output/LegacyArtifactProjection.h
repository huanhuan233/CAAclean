#ifndef CADCAPTURE_OUTPUT_LEGACYARTIFACTPROJECTION_H
#define CADCAPTURE_OUTPUT_LEGACYARTIFACTPROJECTION_H

#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class LegacyArtifactProjection
{
public:
  std::string ProjectionStatus(const ReconstructionPackage& package) const;
};

}

#endif
