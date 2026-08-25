#include "output/LegacyArtifactProjection.h"

namespace cadcapture {

std::string LegacyArtifactProjection::ProjectionStatus(const ReconstructionPackage& package) const
{
  (void)package;
  return "bootstrap_not_enabled";
}

}
