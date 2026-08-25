#include "caa/CaaCapabilityBroker.h"

namespace cadcapture {

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
         capability == "product.part_definition_projection";
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
