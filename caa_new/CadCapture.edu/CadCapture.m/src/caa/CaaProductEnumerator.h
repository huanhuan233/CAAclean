#ifndef CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H
#define CADCAPTURE_CAA_CAAPRODUCTENUMERATOR_H

#include "caa/CaaDocumentHandle.h"
#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

class CaaProductEnumerator
{
public:
  bool Enumerate(CaaDocumentHandle& document_handle,
                 ReconstructionPackage& package,
                 std::string& error);
};

}

#endif
