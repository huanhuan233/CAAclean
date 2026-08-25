#ifndef CADCAPTURE_CAA_CAAPROPERTYEXTRACTORS_H
#define CADCAPTURE_CAA_CAAPROPERTYEXTRACTORS_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaPropertyExtractors
{
public:
  bool Extract(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
