#include "output/NormalizedArtifactWriter.h"
#include "output/JsonSupport.h"
#include <direct.h>
#include <fstream>
#include <sstream>

namespace cadcapture {

static bool EnsureDirectory(const std::string& path)
{
  if (path.empty())
    return false;
  if (_mkdir(path.c_str()) == 0)
    return true;
  return true;
}

static std::string Indent(bool pretty, int depth)
{
  if (!pretty)
    return "";
  return std::string(depth * 2, ' ');
}

static std::string NewLine(bool pretty)
{
  return pretty ? "\n" : "";
}

static bool WriteText(const std::string& path, const std::string& text, std::string& error)
{
  std::ofstream out(path.c_str(), std::ios::out | std::ios::binary);
  if (!out)
  {
    error = "failed to open output file: " + path;
    return false;
  }
  out << text;
  if (!out)
  {
    error = "failed to write output file: " + path;
    return false;
  }
  return true;
}

static bool WriteJsonLines(const ReconstructionPackage& package,
                           const std::string& output_dir,
                           std::string& error)
{
  std::ostringstream objects;
  size_t i;
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    objects << "{"
            << JsonQuote("object_id") << ":" << JsonQuote(object.object_id) << ","
            << JsonQuote("document_id") << ":" << JsonQuote(object.document_id) << ","
            << JsonQuote("object_kind") << ":" << JsonQuote(object.object_kind) << ","
            << JsonQuote("display_name") << ":" << JsonQuote(object.display_name) << ","
            << JsonQuote("internal_name") << ":" << JsonQuote(object.internal_name) << ","
            << JsonQuote("startup_type") << ":" << JsonQuote(object.startup_type) << ","
            << JsonQuote("update_status") << ":" << JsonQuote(object.update_status) << ","
            << JsonQuote("capture_status") << ":" << JsonQuote(object.capture_status)
            << "}\n";
  }

  std::ostringstream occurrences;
  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    occurrences << "{"
                << JsonQuote("occurrence_id") << ":" << JsonQuote(occurrence.occurrence_id) << ","
                << JsonQuote("object_id") << ":" << JsonQuote(occurrence.object_id) << ","
                << JsonQuote("parent_occurrence_id") << ":" << JsonQuote(occurrence.parent_occurrence_id) << ","
                << JsonQuote("document_id") << ":" << JsonQuote(occurrence.document_id) << ","
                << JsonQuote("tree_path") << ":" << JsonQuote(occurrence.tree_path) << ","
                << JsonQuote("occurrence_path") << ":" << JsonQuote(occurrence.occurrence_path) << ","
                << JsonQuote("source_index") << ":" << occurrence.source_index << ","
                << JsonQuote("container_index") << ":" << occurrence.container_index << ","
                << JsonQuote("capture_status") << ":" << JsonQuote(occurrence.capture_status)
                << "}\n";
  }

  if (!WriteText(output_dir + "\\object_entities.jsonl", objects.str(), error))
    return false;
  if (!WriteText(output_dir + "\\tree_occurrences.jsonl", occurrences.str(), error))
    return false;
  return true;
}

bool NormalizedArtifactWriter::Write(const ReconstructionPackage& package,
                                     const CaptureReport& report,
                                     const std::string& output_dir,
                                     bool pretty,
                                     const std::string& legacy_projection_status,
                                     std::string& error)
{
  if (!EnsureDirectory(output_dir))
  {
    error = "failed to create output directory";
    return false;
  }

  std::ostringstream manifest;
  const std::string nl = NewLine(pretty);
  const std::string i1 = Indent(pretty, 1);
  manifest << "{" << nl
           << i1 << JsonQuote("schema_version") << ":" << (pretty ? " " : "") << JsonQuote("caa_capture_new_v0") << "," << nl
           << i1 << JsonQuote("parser_version") << ":" << (pretty ? " " : "") << JsonQuote("0.1.0") << "," << nl
           << i1 << JsonQuote("architecture") << ":" << (pretty ? " " : "") << JsonQuote("deep_module_bootstrap") << "," << nl
           << i1 << JsonQuote("document_count") << ":" << (pretty ? " " : "") << report.document_count << "," << nl
           << i1 << JsonQuote("object_count") << ":" << (pretty ? " " : "") << report.object_count << "," << nl
           << i1 << JsonQuote("occurrence_count") << ":" << (pretty ? " " : "") << report.occurrence_count << "," << nl
           << i1 << JsonQuote("property_count") << ":" << (pretty ? " " : "") << report.property_count << "," << nl
           << i1 << JsonQuote("selected_reconstruction_route") << ":" << (pretty ? " " : "") << JsonQuote(package.reconstruction_plan) << "," << nl
           << i1 << JsonQuote("capture_status") << ":" << (pretty ? " " : "") << JsonQuote(package.capture_status) << "," << nl
           << i1 << JsonQuote("native_document_open_status") << ":" << (pretty ? " " : "") << JsonQuote(package.document_graph.documents.empty() ? "unavailable" : package.document_graph.documents[0].native_document_open_status) << "," << nl
           << i1 << JsonQuote("legacy_projection_status") << ":" << (pretty ? " " : "") << JsonQuote(legacy_projection_status) << nl
           << "}" << nl;

  std::ostringstream report_json;
  report_json << "{" << nl
              << i1 << JsonQuote("success") << ":" << (pretty ? " " : "") << (report.success ? "true" : "false") << "," << nl
              << i1 << JsonQuote("exit_code") << ":" << (pretty ? " " : "") << report.exit_code << "," << nl
              << i1 << JsonQuote("stage") << ":" << (pretty ? " " : "") << JsonQuote(report.stage) << "," << nl
              << i1 << JsonQuote("message") << ":" << (pretty ? " " : "") << JsonQuote(report.message) << "," << nl
              << i1 << JsonQuote("diagnostic_count") << ":" << (pretty ? " " : "") << static_cast<int>(report.diagnostics.size()) << nl
              << "}" << nl;

  std::ostringstream plan_json;
  plan_json << "{" << nl
            << i1 << JsonQuote("route") << ":" << (pretty ? " " : "") << JsonQuote(package.reconstruction_plan) << "," << nl
            << i1 << JsonQuote("status") << ":" << (pretty ? " " : "") << JsonQuote("bootstrap_minimal") << nl
            << "}" << nl;

  if (!WriteText(output_dir + "\\manifest.json", manifest.str(), error))
    return false;
  if (!WriteText(output_dir + "\\capture_report.json", report_json.str(), error))
    return false;
  if (!WriteText(output_dir + "\\reconstruction_plan.json", plan_json.str(), error))
    return false;
  if (!WriteJsonLines(package, output_dir, error))
    return false;
  return true;
}

}
