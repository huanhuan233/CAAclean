#ifndef CADCAPTURE_MODEL_SDKCATALOG_H
#define CADCAPTURE_MODEL_SDKCATALOG_H

#include <string>
#include <vector>

namespace cadcapture {

enum CapabilityVerificationStage
{
  CapabilityStageIndexed,
  CapabilityStageHeaderVerified,
  CapabilityStageCompileVerified,
  CapabilityStageRuntimeVerified,
  CapabilityStageExtractorImplemented,
  CapabilityStageFixtureVerified,
  CapabilityStageReconstructionVerified,
  CapabilityStageUnknown
};

struct ApiHeaderRecord
{
  std::string header;
  std::string framework;
  std::string relative_path;
  std::string status;

  ApiHeaderRecord() : status("indexed") {}
};

struct FrameworkRecord
{
  std::string framework;
  std::string root;
  std::string status;
  std::vector<std::string> public_headers;

  FrameworkRecord() : status("indexed") {}
};

struct CapabilityRecord
{
  std::string capability_id;
  std::string family;
  std::string status;
  std::string extractor;
  bool fixture_verified;
  bool reconstruction_verified;
  std::vector<std::string> headers;
  std::vector<std::string> frameworks;

  CapabilityRecord() : status("indexed"), fixture_verified(false), reconstruction_verified(false) {}
};

class SdkCatalog
{
public:
  bool LoadCapabilityCoverage(const std::string& path, std::string& error);
  const CapabilityRecord* FindCapability(const std::string& capability_id) const;
  bool CapabilityAtLeast(const std::string& capability_id, const std::string& required_status) const;
  size_t CapabilityCount() const;

  static CapabilityVerificationStage StageFromString(const std::string& status);
  static bool IsStageAtLeast(const std::string& status, const std::string& required_status);

private:
  std::vector<CapabilityRecord> _capabilities;
};

}

#endif
