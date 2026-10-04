#ifndef CADCAPTURE_CAA_CAAFTATYPEDREADER_H
#define CADCAPTURE_CAA_CAAFTATYPEDREADER_H

#include "model/PmiIR.h"

class CATITPSComponent;

namespace cadcapture {

// Reads only values exposed by the installed R21 interfaces. Unknown semantics
// remain raw fields with explicit status; this function never changes a model.
void ReadFtaTypedFields(CATITPSComponent* component, FtaSemanticEntity& entity);

}

#endif
