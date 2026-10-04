#ifndef CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H
#define CADCAPTURE_CAA_CAASKETCHEXTRACTOR_H

#include "model/ReconstructionPackage.h"
#include "caa/CaaCapabilityBroker.h"
#include "model/CaptureIdRegistry.h"

namespace cadcapture {

class CaaSketchExtractor
{
public:
  void Extract(CaptureIdRegistry& ids, CaaCapabilityBroker& broker, ReconstructionPackage& package);
  void ExtractForDocument(CaptureIdRegistry& ids, CaaCapabilityBroker& broker,
                          ReconstructionPackage& package, const std::string& document_id);
};

}

#endif
