#ifndef CADCAPTURE_OUTPUT_ARTIFACTREPOSITORY_H
#define CADCAPTURE_OUTPUT_ARTIFACTREPOSITORY_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class ArtifactRepository
{
public:
  bool Commit(const ReconstructionPackage& package,
              const CaptureReport& report,
              const std::string& output_dir,
              bool pretty,
              std::string& error);
};

}

#endif
