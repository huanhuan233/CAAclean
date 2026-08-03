#include "CadParseContracts.h"

#include <iomanip>
#include <sstream>
#include <ctime>

namespace cadparse
{
ParseStatistics::ParseStatistics()
  : enumerated_total(0), typed_count(0), generic_count(0), opaque_count(0), failed_count(0),
    container_count(0), relation_count(0), unknown_native_type_count(0),
    interface_probe_success_count(0), interface_probe_failure_count(0), document_open_ms(0),
    traversal_ms(0), decoder_ms(0), output_ms(0), total_ms(0)
{
}

bool ParseStatistics::IsConserved() const
{
  return enumerated_total == typed_count + generic_count + opaque_count + failed_count;
}

std::string ParseContext::AddDiagnostic(const char* severity, const char* stage, const char* code,
                                        const char* message, const std::string& feature_id)
{
  DiagnosticRecord diagnostic;
  std::ostringstream id;
  id << "D" << std::setw(6) << std::setfill('0') << diagnostics.size() + 1;
  diagnostic.diagnostic_id = id.str();
  diagnostic.severity = severity ? severity : "error";
  diagnostic.stage = stage ? stage : "unknown";
  diagnostic.code = code ? code : "UNKNOWN";
  diagnostic.message = message ? message : "";
  diagnostic.feature_id = feature_id;
  diagnostics.push_back(diagnostic);
  return diagnostic.diagnostic_id;
}

const char* GenericFeatureDecoder::GetDecoderId() const { return "generic"; }
int GenericFeatureDecoder::GetPriority() const { return -1000; }
bool GenericFeatureDecoder::Match(const TypeFingerprint&, const INativeObjectView&) const { return true; }

DecodeResult GenericFeatureDecoder::Decode(const INativeObjectView& view, ParseContext& context,
                                           FeatureRecord& output)
{
  std::string error;
  if (!view.ReadBasicAttributes(output, error))
  {
    const std::string id = context.AddDiagnostic("warning", "generic", "GENERIC_READ_FAILED",
                                                 error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(id);
    return DecodeResult(false, "opaque", error.c_str());
  }
  output.decoder_id = GetDecoderId();
  output.decode_level = "generic";
  output.decode_status = "success";
  return DecodeResult(true, "generic");
}

DecodeResult OpaqueObjectRecorder::Record(const INativeObjectView& view, ParseContext& context,
                                          FeatureRecord& output, const std::string& stage,
                                          const std::string& reason)
{
  output.fingerprint = view.GetFingerprint();
  output.decoder_id = "opaque";
  output.decode_level = "opaque";
  output.decode_status = "recorded";
  output.attributes["failure_stage"] = stage;
  output.attributes["error_code"] = "OPAQUE_OBJECT";
  output.attributes["error_description"] = reason;
  const std::string id = context.AddDiagnostic("warning", stage.c_str(), "OPAQUE_OBJECT",
                                               reason.c_str(), output.feature_id);
  output.diagnostic_ids.push_back(id);
  return DecodeResult(true, "opaque", reason.c_str());
}

void DecoderRegistry::Register(IFeatureDecoder* decoder)
{
  if (decoder)
    _decoders.push_back(decoder);
}

std::string FeatureTypeFingerprintBuilder::StableKey(const TypeFingerprint& fingerprint)
{
  std::ostringstream key;
  key << fingerprint.native_type << '\x1f' << fingerprint.startup_type << '\x1f'
      << fingerprint.container_kind << '\x1f' << fingerprint.internal_name << '\x1f'
      << fingerprint.display_name;
  std::vector<std::string>::const_iterator super_type = fingerprint.super_types.begin();
  for (; super_type != fingerprint.super_types.end(); ++super_type) key << '\x1f' << *super_type;
  std::vector<std::string>::const_iterator interface_key =
    fingerprint.supported_interface_keys.begin();
  for (; interface_key != fingerprint.supported_interface_keys.end(); ++interface_key)
    key << '\x1f' << *interface_key;
  return key.str();
}

void FeatureTypeCatalog::Observe(const TypeFingerprint& fingerprint)
{
  _keys.insert(FeatureTypeFingerprintBuilder::StableKey(fingerprint));
}

size_t FeatureTypeCatalog::Count() const { return _keys.size(); }

bool DecoderMatchEngine::IsBetter(const IFeatureDecoder* candidate,
                                  const IFeatureDecoder* current)
{
  return candidate && (!current || candidate->GetPriority() > current->GetPriority() ||
    (candidate->GetPriority() == current->GetPriority() &&
     std::string(candidate->GetDecoderId()) < current->GetDecoderId()));
}

void UnknownTypeCollector::Observe(const TypeFingerprint& fingerprint)
{
  if (!fingerprint.native_type.empty()) return;
  const std::string key = fingerprint.startup_type.empty() ? "<unavailable>" : fingerprint.startup_type;
  _unknown_types.insert(key);
}

size_t UnknownTypeCollector::Count() const { return _unknown_types.size(); }

bool CoverageTracker::Validate(const ParseStatistics& statistics)
{
  return statistics.IsConserved();
}

IFeatureDecoder* DecoderRegistry::Find(const TypeFingerprint& fingerprint,
                                       const INativeObjectView& view,
                                       ParseContext& context) const
{
  IFeatureDecoder* best = 0;
  int equal_best_count = 0;
  std::vector<IFeatureDecoder*>::const_iterator it = _decoders.begin();
  for (; it != _decoders.end(); ++it)
  {
    IFeatureDecoder* candidate = *it;
    bool matched = false;
    try
    {
      matched = candidate->Match(fingerprint, view);
    }
    catch (...)
    {
      context.AddDiagnostic("warning", "registry", "DECODER_MATCH_EXCEPTION",
                            candidate->GetDecoderId(), "");
      continue;
    }
    if (!matched)
      continue;

    if (!best || candidate->GetPriority() > best->GetPriority())
    {
      best = candidate;
      equal_best_count = 1;
    }
    else if (candidate->GetPriority() == best->GetPriority())
    {
      ++equal_best_count;
      if (DecoderMatchEngine::IsBetter(candidate, best))
        best = candidate;
    }
  }
  if (best && equal_best_count > 1)
    context.AddDiagnostic("warning", "registry", "DECODER_PRIORITY_TIE",
                          "stable decoder id tie break", "");
  return best;
}

FeatureTypeRegistry::FeatureTypeRegistry() {}

void FeatureTypeRegistry::Register(IFeatureDecoder* decoder)
{
  _registry.Register(decoder);
}

DecodeResult FeatureTypeRegistry::DecodeObject(const INativeObjectView& view, ParseContext& context,
                                               FeatureRecord& output)
{
  const clock_t decode_start = clock();
  output.fingerprint = view.GetFingerprint();
  const FeatureRecord fallback_base = output;
  IFeatureDecoder* decoder = _registry.Find(output.fingerprint, view, context);
  DecodeResult result(false, "failed", "no typed decoder");

  if (decoder)
  {
    try
    {
      result = decoder->Decode(view, context, output);
    }
    catch (...)
    {
      const std::string id = context.AddDiagnostic("warning", "decoder", "DECODER_EXCEPTION",
                                                   decoder->GetDecoderId(), output.feature_id);
      output.diagnostic_ids.push_back(id);
      result = DecodeResult(false, "failed", "typed decoder exception");
    }
  }

  if (!decoder || !result.success)
  {
    if (decoder && result.message != "typed decoder exception")
    {
      const std::string id = context.AddDiagnostic("warning", "decoder", "DECODER_FAILED",
                                                   result.message.c_str(), output.feature_id);
      output.diagnostic_ids.push_back(id);
    }
    const std::vector<std::string> failure_diagnostic_ids = output.diagnostic_ids;
    output = fallback_base;
    output.diagnostic_ids = failure_diagnostic_ids;
    result = _generic.Decode(view, context, output);
  }

  if (!result.success)
    result = _opaque.Record(view, context, output, "generic",
                            result.message.empty() ? "generic fallback unavailable" : result.message);

  ++context.statistics.enumerated_total;
  ++context.statistics.decoder_hits[output.decoder_id];
  if (result.level == "typed")
    ++context.statistics.typed_count;
  else if (result.level == "generic")
    ++context.statistics.generic_count;
  else if (result.level == "opaque")
    ++context.statistics.opaque_count;
  else
    ++context.statistics.failed_count;
  context.statistics.decoder_ms += static_cast<long>(
    (clock() - decode_start) * 1000 / CLOCKS_PER_SEC);
  return result;
}

std::string FeatureIdGenerator::Next()
{
  std::ostringstream id;
  id << "F" << std::setw(6) << std::setfill('0') << ++_next;
  return id.str();
}

std::string JsonEscape(const std::string& value)
{
  std::ostringstream output;
  std::string::const_iterator it = value.begin();
  for (; it != value.end(); ++it)
  {
    const unsigned char c = static_cast<unsigned char>(*it);
    if (c == '"') output << "\\\"";
    else if (c == '\\') output << "\\\\";
    else if (c == '\n') output << "\\n";
    else if (c == '\r') output << "\\r";
    else if (c == '\t') output << "\\t";
    else if (c < 0x20)
      output << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c)
             << std::dec;
    else
      output << *it;
  }
  return output.str();
}
}
