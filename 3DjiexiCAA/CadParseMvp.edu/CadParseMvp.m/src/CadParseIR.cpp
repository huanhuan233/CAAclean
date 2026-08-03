#include "CadParseIR.h"

#include <direct.h>
#include <errno.h>
#include <fstream>
#include <sstream>

namespace cadparse
{
static std::string JoinPath(const std::string& directory, const char* name)
{
  if (directory.empty())
    return name;
  const char last = directory[directory.size() - 1];
  return directory + ((last == '\\' || last == '/') ? "" : "\\") + name;
}

static bool EnsureDirectory(const std::string& path, std::string& error)
{
  if (path.empty())
  {
    error = "output directory is empty";
    return false;
  }

  std::string current;
  std::string::size_type i = 0;
  if (path.size() > 1 && path[1] == ':')
  {
    current = path.substr(0, 2);
    i = 2;
  }
  for (; i <= path.size(); ++i)
  {
    if (i < path.size() && path[i] != '\\' && path[i] != '/')
    {
      current += path[i];
      continue;
    }
    if (!current.empty() && current[current.size() - 1] != ':')
    {
      if (_mkdir(current.c_str()) != 0 && errno != EEXIST)
      {
        error = std::string("cannot create output directory: ") + current;
        return false;
      }
    }
    if (i < path.size() && (current.empty() || current[current.size() - 1] != '\\'))
      current += '\\';
  }
  return true;
}

static void WriteStringArray(std::ostream& output, const std::vector<std::string>& values)
{
  output << '[';
  std::vector<std::string>::const_iterator it = values.begin();
  for (; it != values.end(); ++it)
  {
    if (it != values.begin()) output << ',';
    output << '"' << JsonEscape(*it) << '"';
  }
  output << ']';
}

static void WriteStringMap(std::ostream& output, const std::map<std::string, std::string>& values)
{
  output << '{';
  std::map<std::string, std::string>::const_iterator it = values.begin();
  for (; it != values.end(); ++it)
  {
    if (it != values.begin()) output << ',';
    output << '"' << JsonEscape(it->first) << "\":\"" << JsonEscape(it->second) << '"';
  }
  output << '}';
}

static void WriteCountMap(std::ostream& output, const std::map<std::string, long>& values)
{
  output << '{';
  std::map<std::string, long>::const_iterator it = values.begin();
  for (; it != values.end(); ++it)
  {
    if (it != values.begin()) output << ',';
    output << '"' << JsonEscape(it->first) << "\":" << it->second;
  }
  output << '}';
}

static void WriteFeature(std::ostream& output, const FeatureRecord& record)
{
  output << "{\"feature_id\":\"" << JsonEscape(record.feature_id)
         << "\",\"parent_id\":\"" << JsonEscape(record.parent_id)
         << "\",\"traversal_index\":" << record.traversal_index
         << ",\"native_type\":\"" << JsonEscape(record.fingerprint.native_type)
         << "\",\"startup_type\":\"" << JsonEscape(record.fingerprint.startup_type)
         << "\",\"super_types\":";
  WriteStringArray(output, record.fingerprint.super_types);
  output << ",\"display_name\":\"" << JsonEscape(record.fingerprint.display_name)
         << "\",\"internal_name\":\"" << JsonEscape(record.fingerprint.internal_name)
         << "\",\"container_kind\":\"" << JsonEscape(record.fingerprint.container_kind)
         << "\",\"tree_path\":\"" << JsonEscape(record.tree_path)
         << "\",\"supported_interface_keys\":";
  WriteStringArray(output, record.fingerprint.supported_interface_keys);
  output << ",\"update_status\":\"" << JsonEscape(record.update_status)
         << "\",\"visibility\":\"" << JsonEscape(record.visibility)
         << "\",\"decoder_id\":\"" << JsonEscape(record.decoder_id)
         << "\",\"decode_level\":\"" << JsonEscape(record.decode_level)
         << "\",\"decode_status\":\"" << JsonEscape(record.decode_status)
         << "\",\"attributes\":";
  WriteStringMap(output, record.attributes);
  output << ",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

static bool OpenOutput(std::ofstream& output, const std::string& path, std::string& error)
{
  output.open(path.c_str(), std::ios::out | std::ios::binary | std::ios::trunc);
  if (!output)
  {
    error = std::string("cannot write output file: ") + path;
    return false;
  }
  return true;
}

static bool FinishOutput(std::ofstream& output, const char* artifact, std::string& error)
{
  output.flush();
  if (!output)
  {
    error = std::string("write failed for artifact: ") + artifact;
    output.close();
    return false;
  }
  output.close();
  if (!output)
  {
    error = std::string("close failed for artifact: ") + artifact;
    return false;
  }
  return true;
}

JsonArtifactWriter::JsonArtifactWriter(bool pretty) : _pretty(pretty) {}

bool JsonArtifactWriter::Write(const std::vector<FeatureRecord>& features,
                               const std::vector<RelationRecord>& relations,
                               const ParseContext& context,
                               const std::string& output_dir,
                               std::string& error)
{
  if (!CoverageTracker::Validate(context.statistics))
  {
    error = "coverage conservation failed";
    return false;
  }
  if (!EnsureDirectory(output_dir, error))
    return false;

  std::ofstream output;
  if (!OpenOutput(output, JoinPath(output_dir, "features.jsonl"), error)) return false;
  std::vector<FeatureRecord>::const_iterator feature = features.begin();
  for (; feature != features.end(); ++feature)
  {
    WriteFeature(output, *feature);
    output << '\n';
  }
  if (!FinishOutput(output, "features.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "relations.jsonl"), error)) return false;
  std::vector<RelationRecord>::const_iterator relation = relations.begin();
  for (; relation != relations.end(); ++relation)
    output << "{\"kind\":\"" << JsonEscape(relation->kind) << "\",\"from_id\":\""
           << JsonEscape(relation->from_id) << "\",\"to_id\":\""
           << JsonEscape(relation->to_id) << "\"}\n";
  if (!FinishOutput(output, "relations.jsonl", error)) return false;

  const char* spacing = _pretty ? "\n  " : "";
  if (!OpenOutput(output, JoinPath(output_dir, "manifest.json"), error)) return false;
  output << '{' << spacing << "\"schema_version\":\"cad_parse_mvp_v0\","
         << spacing << "\"feature_count\":" << features.size() << ','
         << spacing << "\"relation_count\":" << relations.size() << ','
         << spacing << "\"runtime_info\":";
  WriteStringMap(output, context.runtime_info);
  if (_pretty) output << '\n';
  output << "}\n";
  if (!FinishOutput(output, "manifest.json", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "diagnostics.json"), error)) return false;
  output << "[";
  std::vector<DiagnosticRecord>::const_iterator diagnostic = context.diagnostics.begin();
  for (; diagnostic != context.diagnostics.end(); ++diagnostic)
  {
    if (diagnostic != context.diagnostics.begin()) output << ',';
    output << "{\"diagnostic_id\":\"" << JsonEscape(diagnostic->diagnostic_id)
           << "\",\"severity\":\"" << JsonEscape(diagnostic->severity)
           << "\",\"stage\":\"" << JsonEscape(diagnostic->stage)
           << "\",\"code\":\"" << JsonEscape(diagnostic->code)
           << "\",\"message\":\"" << JsonEscape(diagnostic->message)
           << "\",\"feature_id\":\"" << JsonEscape(diagnostic->feature_id) << "\"}";
  }
  output << "]\n";
  if (!FinishOutput(output, "diagnostics.json", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "coverage.json"), error)) return false;
  output << "{\"enumerated_total\":" << context.statistics.enumerated_total
         << ",\"typed_count\":" << context.statistics.typed_count
         << ",\"generic_count\":" << context.statistics.generic_count
         << ",\"opaque_count\":" << context.statistics.opaque_count
         << ",\"failed_count\":" << context.statistics.failed_count
         << ",\"container_count\":" << context.statistics.container_count
         << ",\"relation_count\":" << context.statistics.relation_count
         << ",\"unknown_native_type_count\":" << context.statistics.unknown_native_type_count
         << ",\"interface_probe_success_count\":" << context.statistics.interface_probe_success_count
         << ",\"interface_probe_failure_count\":" << context.statistics.interface_probe_failure_count
         << ",\"document_open_ms\":" << context.statistics.document_open_ms
         << ",\"traversal_ms\":" << context.statistics.traversal_ms
         << ",\"decoder_ms\":" << context.statistics.decoder_ms
         << ",\"output_ms\":" << context.statistics.output_ms
         << ",\"total_ms\":" << context.statistics.total_ms
         << ",\"decoder_hits\":";
  WriteCountMap(output, context.statistics.decoder_hits);
  output << "}\n";
  if (!FinishOutput(output, "coverage.json", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "parser.log"), error)) return false;
  output << "schema=cad_parse_mvp_v0\nfeatures=" << features.size()
         << "\nrelations=" << relations.size() << "\ncoverage_conserved=true\n";
  feature = features.begin();
  for (; feature != features.end(); ++feature)
    output << "decoder_match feature_id=" << feature->feature_id
           << " decoder=" << feature->decoder_id
           << " level=" << feature->decode_level
           << " status=" << feature->decode_status << '\n';
  diagnostic = context.diagnostics.begin();
  for (; diagnostic != context.diagnostics.end(); ++diagnostic)
    output << "diagnostic id=" << diagnostic->diagnostic_id
           << " stage=" << diagnostic->stage
           << " code=" << diagnostic->code
           << " feature_id=" << diagnostic->feature_id
           << " message=" << JsonEscape(diagnostic->message) << '\n';
  if (!FinishOutput(output, "parser.log", error)) return false;
  return true;
}
}
