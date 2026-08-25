#ifndef CADCAPTURE_CAA_CAACAPABILITYBROKER_H
#define CADCAPTURE_CAA_CAACAPABILITYBROKER_H

#include "model/ReconstructionPackage.h"
#include <CATBaseUnknown.h>
#include <CATErrorDef.h>
#include <map>
#include <string>

namespace cadcapture {

enum CapabilityStatus
{
  CapabilityAvailable,
  CapabilityUnsupported,
  CapabilityUnavailable,
  CapabilityException
};

class CaaCapabilityBroker
{
public:
  CapabilityStatus Check(const std::string& capability,
                         ReconstructionPackage& package);

  template <class T>
  CapabilityStatus Query(CATBaseUnknown* object,
                         const IID& interface_id,
                         const std::string& capability,
                         const std::string& subject_id,
                         ReconstructionPackage& package,
                         T*& out)
  {
    out = 0;
    if (!object)
    {
      Record(capability, subject_id, CapabilityUnavailable, "native object is null", package);
      return CapabilityUnavailable;
    }
    try
    {
      if (FAILED(object->QueryInterface(interface_id, reinterpret_cast<void**>(&out))) || !out)
      {
        Record(capability, subject_id, CapabilityUnsupported, "QueryInterface returned unsupported", package);
        return CapabilityUnsupported;
      }
      Record(capability, subject_id, CapabilityAvailable, "QueryInterface succeeded", package);
      return CapabilityAvailable;
    }
    catch (...)
    {
      out = 0;
      Record(capability, subject_id, CapabilityException, "QueryInterface raised an exception", package);
      return CapabilityException;
    }
  }

  void Record(const std::string& capability,
              const std::string& subject_id,
              CapabilityStatus status,
              const std::string& message,
              ReconstructionPackage& package);

private:
  std::map<std::string, CapabilityStatus> _cache;
};

}

#endif
