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

class CaaCapabilityLease
{
public:
  CaaCapabilityLease();
  ~CaaCapabilityLease();

  bool IsAvailable() const;
  CapabilityStatus Status() const;
  void Reset(CATBaseUnknown* value, CapabilityStatus status);
  void Release();

  template <class T>
  T* As() const
  {
    return reinterpret_cast<T*>(_value);
  }

private:
  CaaCapabilityLease(const CaaCapabilityLease&);
  CaaCapabilityLease& operator=(const CaaCapabilityLease&);

  CATBaseUnknown* _value;
  CapabilityStatus _status;
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
      _cache[subject_id + "|" + capability] = CapabilityUnavailable;
      Record(capability, subject_id, CapabilityUnavailable, "native object is null", package);
      return CapabilityUnavailable;
    }
    try
    {
      if (FAILED(object->QueryInterface(interface_id, reinterpret_cast<void**>(&out))) || !out)
      {
        _cache[subject_id + "|" + capability] = CapabilityUnsupported;
        Record(capability, subject_id, CapabilityUnsupported, "QueryInterface returned unsupported", package);
        return CapabilityUnsupported;
      }
      _cache[subject_id + "|" + capability] = CapabilityAvailable;
      Record(capability, subject_id, CapabilityAvailable, "QueryInterface succeeded", package);
      return CapabilityAvailable;
    }
    catch (...)
    {
      out = 0;
      _cache[subject_id + "|" + capability] = CapabilityException;
      Record(capability, subject_id, CapabilityException, "QueryInterface raised an exception", package);
      return CapabilityException;
    }
  }

  template <class T>
  CapabilityStatus Acquire(CATBaseUnknown* object,
                           const IID& interface_id,
                           const std::string& capability,
                           const std::string& subject_id,
                           ReconstructionPackage& package,
                           CaaCapabilityLease& lease)
  {
    T* out = 0;
    const CapabilityStatus status = Query<T>(object, interface_id, capability, subject_id, package, out);
    if (status == CapabilityAvailable)
      lease.Reset(reinterpret_cast<CATBaseUnknown*>(out), status);
    else
      lease.Reset(0, status);
    return status;
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
