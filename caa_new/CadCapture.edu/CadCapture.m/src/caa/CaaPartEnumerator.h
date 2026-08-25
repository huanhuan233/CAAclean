#ifndef CADCAPTURE_CAA_CAAPARTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPARTENUMERATOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class CaaPartEnumerator
{
public:
  bool Enumerate(CaaDocumentHandle& document_handle,
                 ReconstructionPackage& package,
                 std::string& error);
};

}

#endif
