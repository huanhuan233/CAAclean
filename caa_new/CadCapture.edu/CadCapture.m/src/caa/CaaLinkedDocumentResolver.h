#ifndef CADCAPTURE_CAA_CAALINKEDDOCUMENTRESOLVER_H
#define CADCAPTURE_CAA_CAALINKEDDOCUMENTRESOLVER_H

#include "caa/CaaDocumentHandle.h"
#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaLinkedDocumentResolver
{
public:
  bool Resolve(CaaDocumentHandle& document_handle,
               CaptureIdRegistry& ids,
               ReconstructionPackage& package);
};

}

#endif
