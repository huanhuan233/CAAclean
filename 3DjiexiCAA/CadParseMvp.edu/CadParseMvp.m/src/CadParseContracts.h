#ifndef CAD_PARSE_CONTRACTS_H
#define CAD_PARSE_CONTRACTS_H

#include <map>
#include <set>
#include <string>
#include <vector>

namespace cadparse
{
struct TypeFingerprint
{
  std::string native_type;
  std::string startup_type;
  std::vector<std::string> super_types;
  std::vector<std::string> supported_interface_keys;
  std::string container_kind;
  std::string internal_name;
  std::string display_name;
};

struct FeatureRecord
{
  FeatureRecord() : traversal_index(0) {}

  std::string feature_id;
  std::string parent_id;
  long traversal_index;
  TypeFingerprint fingerprint;
  std::string tree_path;
  std::string update_status;
  std::string visibility;
  std::string decoder_id;
  std::string decode_level;
  std::string decode_status;
  std::map<std::string, std::string> attributes;
  std::vector<std::string> diagnostic_ids;
};

struct RelationRecord
{
  std::string kind;
  std::string from_id;
  std::string to_id;
};

struct DiagnosticRecord
{
  std::string diagnostic_id;
  std::string severity;
  std::string stage;
  std::string code;
  std::string message;
  std::string feature_id;
};

struct DecodeResult
{
  DecodeResult(bool ok = true, const char* result_level = "typed", const char* detail = "")
    : success(ok), level(result_level), message(detail) {}

  bool success;
  std::string level;
  std::string message;
};

struct ParseStatistics
{
  ParseStatistics();
  bool IsConserved() const;

  long enumerated_total;
  long typed_count;
  long generic_count;
  long opaque_count;
  long failed_count;
  long container_count;
  long relation_count;
  long unknown_native_type_count;
  long interface_probe_success_count;
  long interface_probe_failure_count;
  long document_open_ms;
  long traversal_ms;
  long decoder_ms;
  long output_ms;
  long total_ms;
  std::map<std::string, long> decoder_hits;
};

class ParseContext
{
public:
  std::string AddDiagnostic(const char* severity, const char* stage, const char* code,
                            const char* message, const std::string& feature_id);

  ParseStatistics statistics;
  std::vector<DiagnosticRecord> diagnostics;
  std::map<std::string, std::string> runtime_info;
};

class INativeObjectView
{
public:
  virtual ~INativeObjectView() {}
  virtual const TypeFingerprint& GetFingerprint() const = 0;
  virtual bool ReadBasicAttributes(FeatureRecord& output, std::string& error) const = 0;
};

class IArtifactWriter
{
public:
  virtual ~IArtifactWriter() {}
  virtual bool Write(const std::vector<FeatureRecord>& features,
                     const std::vector<RelationRecord>& relations,
                     const ParseContext& context,
                     const std::string& output_dir,
                     std::string& error) = 0;
};

class IFeatureDecoder
{
public:
  virtual ~IFeatureDecoder() {}
  virtual const char* GetDecoderId() const = 0;
  virtual int GetPriority() const = 0;
  virtual bool Match(const TypeFingerprint& fingerprint,
                     const INativeObjectView& object_view) const = 0;
  virtual DecodeResult Decode(const INativeObjectView& object_view,
                              ParseContext& context,
                              FeatureRecord& output) = 0;
};

class GenericFeatureDecoder : public IFeatureDecoder
{
public:
  const char* GetDecoderId() const;
  int GetPriority() const;
  bool Match(const TypeFingerprint&, const INativeObjectView&) const;
  DecodeResult Decode(const INativeObjectView&, ParseContext&, FeatureRecord&);
};

class OpaqueObjectRecorder
{
public:
  DecodeResult Record(const INativeObjectView&, ParseContext&, FeatureRecord&,
                      const std::string& stage, const std::string& reason);
};

class DecoderRegistry
{
public:
  void Register(IFeatureDecoder* decoder);
  IFeatureDecoder* Find(const TypeFingerprint&, const INativeObjectView&, ParseContext&) const;

private:
  std::vector<IFeatureDecoder*> _decoders;
};

class FeatureTypeFingerprintBuilder
{
public:
  static std::string StableKey(const TypeFingerprint& fingerprint);
};

class FeatureTypeCatalog
{
public:
  void Observe(const TypeFingerprint& fingerprint);
  size_t Count() const;

private:
  std::set<std::string> _keys;
};

class DecoderMatchEngine
{
public:
  static bool IsBetter(const IFeatureDecoder* candidate, const IFeatureDecoder* current);
};

class InterfaceProbeService
{
public:
  virtual ~InterfaceProbeService() {}
  virtual bool Probe(const char* interface_key, TypeFingerprint& fingerprint,
                     ParseStatistics& statistics) = 0;
};

class UnknownTypeCollector
{
public:
  void Observe(const TypeFingerprint& fingerprint);
  size_t Count() const;

private:
  std::set<std::string> _unknown_types;
};

class CoverageTracker
{
public:
  static bool Validate(const ParseStatistics& statistics);
};

class FeatureTypeRegistry
{
public:
  FeatureTypeRegistry();
  void Register(IFeatureDecoder* decoder);
  DecodeResult DecodeObject(const INativeObjectView&, ParseContext&, FeatureRecord&);

private:
  DecoderRegistry _registry;
  GenericFeatureDecoder _generic;
  OpaqueObjectRecorder _opaque;
};

class FeatureIdGenerator
{
public:
  FeatureIdGenerator() : _next(0) {}
  std::string Next();

private:
  long _next;
};

std::string JsonEscape(const std::string& value);

class SelfTestSuite
{
public:
  int RunAll();
};
}

#endif
