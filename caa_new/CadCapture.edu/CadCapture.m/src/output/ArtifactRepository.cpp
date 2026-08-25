#include "output/ArtifactRepository.h"
#include "output/LegacyArtifactProjection.h"
#include "output/NormalizedArtifactWriter.h"

namespace cadcapture {

bool ArtifactRepository::Commit(const ReconstructionPackage& package,
                                const CaptureReport& report,
                                const std::string& output_dir,
                                bool pretty,
                                std::string& error)
{
  LegacyArtifactProjection legacy;
  NormalizedArtifactWriter writer;
  const std::string legacy_status = legacy.ProjectionStatus(package);
  if (!writer.Write(package, report, output_dir, pretty, legacy_status, error))
    return false;
  return legacy.Write(package, output_dir, error);
}

}
