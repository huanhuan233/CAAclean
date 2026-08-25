#ifndef CADCAPTURE_OUTPUT_NORMALIZEDARTIFACTWRITER_H
#define CADCAPTURE_OUTPUT_NORMALIZEDARTIFACTWRITER_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class NormalizedArtifactWriter
{
public:
  bool Write(const ReconstructionPackage& package,
             const CaptureReport& report,
             const std::string& output_dir,
             bool pretty,
             const std::string& legacy_projection_status,
             std::string& error);
};

}

#endif
