#include "model/SdkCatalog.h"
#include <fstream>
#include <sstream>

namespace cadcapture {

static std::string ReadTextFile(const std::string& path, std::string& error)
{
  std::ifstream in(path.c_str(), std::ios::in | std::ios::binary);
  if (!in)
  {
    error = "failed to open catalog file: " + path;
    return "";
  }
  std::ostringstream buffer;
  buffer << in.rdbuf();
  return buffer.str();
}

static std::string ExtractStringField(const std::string& object_text, const std::string& field)
{
  const std::string pattern = "\"" + field + "\"";
  std::string::size_type pos = object_text.find(pattern);
  if (pos == std::string::npos)
    return "";
  pos = object_text.find(':', pos + pattern.size());
  if (pos == std::string::npos)
    return "";
  pos = object_text.find('"', pos + 1);
  if (pos == std::string::npos)
    return "";

  std::string value;
  bool escaped = false;
  ++pos;
  for (; pos < object_text.size(); ++pos)
  {
    const char c = object_text[pos];
    if (escaped)
    {
      value += c;
      escaped = false;
    }
    else if (c == '\\')
    {
      escaped = true;
    }
    else if (c == '"')
    {
      break;
    }
    else
    {
      value += c;
    }
  }
  return value;
}

static bool ExtractBoolField(const std::string& object_text, const std::string& field)
{
  const std::string pattern = "\"" + field + "\"";
  std::string::size_type pos = object_text.find(pattern);
  if (pos == std::string::npos)
    return false;
  pos = object_text.find(':', pos + pattern.size());
  if (pos == std::string::npos)
    return false;
  ++pos;
  while (pos < object_text.size() &&
         (object_text[pos] == ' ' || object_text[pos] == '\t' ||
          object_text[pos] == '\r' || object_text[pos] == '\n'))
  {
    ++pos;
  }
  return object_text.find("true", pos) == pos;
}

static std::vector<std::string> ExtractStringArrayField(const std::string& object_text, const std::string& field)
{
  std::vector<std::string> values;
  const std::string pattern = "\"" + field + "\"";
  std::string::size_type pos = object_text.find(pattern);
  if (pos == std::string::npos)
    return values;
  pos = object_text.find('[', pos + pattern.size());
  if (pos == std::string::npos)
    return values;
  const std::string::size_type end = object_text.find(']', pos + 1);
  if (end == std::string::npos)
    return values;

  while (pos < end)
  {
    pos = object_text.find('"', pos + 1);
    if (pos == std::string::npos || pos > end)
      break;
    std::string value;
    bool escaped = false;
    ++pos;
    for (; pos < end; ++pos)
    {
      const char c = object_text[pos];
      if (escaped)
      {
        value += c;
        escaped = false;
      }
      else if (c == '\\')
      {
        escaped = true;
      }
      else if (c == '"')
      {
        break;
      }
      else
      {
        value += c;
      }
    }
    values.push_back(value);
  }
  return values;
}

static std::string ExtractCapabilitiesArray(const std::string& text)
{
  const std::string pattern = "\"capabilities\"";
  std::string::size_type pos = text.find(pattern);
  if (pos == std::string::npos)
    return "";
  pos = text.find('[', pos + pattern.size());
  if (pos == std::string::npos)
    return "";

  int depth = 0;
  std::string::size_type i;
  for (i = pos; i < text.size(); ++i)
  {
    if (text[i] == '[')
      ++depth;
    else if (text[i] == ']')
    {
      --depth;
      if (depth == 0)
        return text.substr(pos + 1, i - pos - 1);
    }
  }
  return "";
}

static bool NextObject(const std::string& array_text, std::string::size_type& cursor, std::string& object_text)
{
  std::string::size_type begin = array_text.find('{', cursor);
  if (begin == std::string::npos)
    return false;
  int depth = 0;
  std::string::size_type i;
  for (i = begin; i < array_text.size(); ++i)
  {
    if (array_text[i] == '{')
      ++depth;
    else if (array_text[i] == '}')
    {
      --depth;
      if (depth == 0)
      {
        object_text = array_text.substr(begin, i - begin + 1);
        cursor = i + 1;
        return true;
      }
    }
  }
  return false;
}

CapabilityVerificationStage SdkCatalog::StageFromString(const std::string& status)
{
  if (status == "indexed") return CapabilityStageIndexed;
  if (status == "header_verified") return CapabilityStageHeaderVerified;
  if (status == "compile_verified") return CapabilityStageCompileVerified;
  if (status == "runtime_verified") return CapabilityStageRuntimeVerified;
  if (status == "extractor_implemented") return CapabilityStageExtractorImplemented;
  if (status == "fixture_verified") return CapabilityStageFixtureVerified;
  if (status == "reconstruction_verified") return CapabilityStageReconstructionVerified;
  return CapabilityStageUnknown;
}

bool SdkCatalog::IsStageAtLeast(const std::string& status, const std::string& required_status)
{
  const CapabilityVerificationStage actual = StageFromString(status);
  const CapabilityVerificationStage required = StageFromString(required_status);
  if (actual == CapabilityStageUnknown || required == CapabilityStageUnknown)
    return false;
  return actual >= required;
}

bool SdkCatalog::LoadCapabilityCoverage(const std::string& path, std::string& error)
{
  _capabilities.clear();
  const std::string text = ReadTextFile(path, error);
  if (!error.empty())
    return false;

  const std::string array_text = ExtractCapabilitiesArray(text);
  if (array_text.empty())
  {
    error = "capability catalog has no capabilities array";
    return false;
  }

  std::string::size_type cursor = 0;
  std::string object_text;
  while (NextObject(array_text, cursor, object_text))
  {
    CapabilityRecord record;
    record.capability_id = ExtractStringField(object_text, "capability_id");
    record.family = ExtractStringField(object_text, "family");
    record.status = ExtractStringField(object_text, "status");
    record.extractor = ExtractStringField(object_text, "extractor");
    record.fixture_verified = ExtractBoolField(object_text, "fixture_verified");
    record.reconstruction_verified = ExtractBoolField(object_text, "reconstruction_verified");
    record.headers = ExtractStringArrayField(object_text, "headers");
    record.frameworks = ExtractStringArrayField(object_text, "frameworks");
    if (!record.capability_id.empty())
      _capabilities.push_back(record);
  }

  if (_capabilities.empty())
  {
    error = "capability catalog contains no readable capability records";
    return false;
  }
  return true;
}

const CapabilityRecord* SdkCatalog::FindCapability(const std::string& capability_id) const
{
  size_t i;
  for (i = 0; i < _capabilities.size(); ++i)
  {
    if (_capabilities[i].capability_id == capability_id)
      return &_capabilities[i];
  }
  return 0;
}

bool SdkCatalog::CapabilityAtLeast(const std::string& capability_id, const std::string& required_status) const
{
  const CapabilityRecord* record = FindCapability(capability_id);
  if (!record)
    return false;
  return IsStageAtLeast(record->status, required_status);
}

size_t SdkCatalog::CapabilityCount() const
{
  return _capabilities.size();
}

}
