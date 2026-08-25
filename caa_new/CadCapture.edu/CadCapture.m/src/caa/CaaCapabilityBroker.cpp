#include "caa/CaaCapabilityBroker.h"

namespace cadcapture {

CaaCapabilityLease::CaaCapabilityLease()
  : _value(0),
    _status(CapabilityUnavailable)
{
}

CaaCapabilityLease::~CaaCapabilityLease()
{
  Release();
}

bool CaaCapabilityLease::IsAvailable() const
{
  return _status == CapabilityAvailable && _value != 0;
}

CapabilityStatus CaaCapabilityLease::Status() const
{
  return _status;
}

void CaaCapabilityLease::Reset(CATBaseUnknown* value, CapabilityStatus status)
{
  Release();
  _value = value;
  _status = status;
}

void CaaCapabilityLease::Release()
{
  if (_value)
  {
    _value->Release();
    _value = 0;
  }
  _status = CapabilityUnavailable;
}

static const char* StatusText(CapabilityStatus status)
{
  switch (status)
  {
  case CapabilityAvailable: return "available";
  case CapabilityUnsupported: return "unsupported";
  case CapabilityUnavailable: return "unavailable";
  case CapabilityException: return "exception";
  }
  return "unavailable";
}

static bool IsCompiledCapability(const std::string& capability)
{
  return capability == "native_access" ||
         capability == "document.native_open" ||
         capability == "part.native_spec_tree" ||
         capability == "product.native_bom" ||
         capability == "product.reference_instance_separation" ||
         capability == "product.absolute_transform" ||
         capability == "product.linked_document_resolution" ||
         capability == "product.part_definition_projection" ||
         capability == "mechanical.CATIInertia" ||
         capability == "knowledgeware.CATICkeParm" ||
         capability == "native_feature.CATIAHole" ||
         capability == "native_feature.CATIAPad" ||
         capability == "native_feature.CATIAPocket";
}

CapabilityStatus CaaCapabilityBroker::Check(const std::string& capability,
                                            ReconstructionPackage& package)
{
  std::map<std::string, CapabilityStatus>::iterator found = _cache.find(capability);
  if (found != _cache.end())
    return found->second;
  const CapabilityStatus status = IsCompiledCapability(capability) ? CapabilityAvailable : CapabilityUnsupported;
  _cache[capability] = status;
  Record(capability, capability, status,
         IsCompiledCapability(capability) ? "compiled capability is enabled" : "capability is not compiled in this stage",
         package);
  return status;
}

void CaaCapabilityBroker::Record(const std::string& capability,
                                 const std::string& subject_id,
                                 CapabilityStatus status,
                                 const std::string& message,
                                 ReconstructionPackage& package)
{
  package.diagnostics.push_back(MakeDiagnostic(status == CapabilityAvailable ? "info" : "warning",
                                               std::string("capability_") + StatusText(status),
                                               subject_id.empty() ? capability : subject_id,
                                               capability + ": " + message,
                                               "capability_broker"));
}

}
