#ifndef CADCAPTURE_CAA_CAALINKEDDOCUMENTRESOLVER_H
#define CADCAPTURE_CAA_CAALINKEDDOCUMENTRESOLVER_H

#include "engine/CaptureReport.h"
#include "model/ReconstructionPackage.h"

namespace cadcapture {

class CaaLinkedDocumentResolver
{
public:
  bool Resolve(ReconstructionPackage& package, CaptureReport& report);
};

}

#endif
