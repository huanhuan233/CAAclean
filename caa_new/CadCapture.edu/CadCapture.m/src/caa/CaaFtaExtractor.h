#ifndef CADCAPTURE_CAA_CAAFTAEXTRACTOR_H
#define CADCAPTURE_CAA_CAAFTAEXTRACTOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaFtaExtractor
{
public:
  bool Extract(CaaDocumentHandle& document_handle,
               CaptureIdRegistry& ids,
               ReconstructionPackage& package);
};

}

#endif
