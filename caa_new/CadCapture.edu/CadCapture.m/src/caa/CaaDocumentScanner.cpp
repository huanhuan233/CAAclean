#include "caa/CaaDocumentScanner.h"
#include <algorithm>
#include <cctype>

namespace cadcapture {

static std::string CaptureBaseName(const std::string& path)
{
  const std::string::size_type slash = path.find_last_of("\\/");
  if (slash == std::string::npos)
    return path;
  return path.substr(slash + 1);
}

static std::string CaptureExtension(const std::string& path)
{
  const std::string name = CaptureBaseName(path);
  const std::string::size_type dot = name.find_last_of('.');
  std::string ext;
  if (dot != std::string::npos)
    ext = name.substr(dot);
  std::transform(ext.begin(), ext.end(), ext.begin(), static_cast<int (*)(int)>(std::tolower));
  return ext;
}

bool CaaDocumentScanner::Scan(const CaptureRequest& request,
                              ReconstructionPackage& package,
                              CaptureReport& report,
                              std::string& error)
{
  DocumentEntity document;
  document.document_id = "doc_1";
  document.source_file_name = CaptureBaseName(request.input_path);
  document.native_document_open_status = "not_implemented_bootstrap";

  const std::string ext = CaptureExtension(request.input_path);
  if (ext == ".catpart")
  {
    document.document_kind = "catpart";
    document.capture_status = "partial";
  }
  else if (ext == ".catproduct")
  {
    document.document_kind = "catproduct";
    document.capture_status = "partial";
  }
  else
  {
    document.document_kind = "unsupported";
    document.capture_status = "unsupported";
    error = "unsupported input extension";
  }

  package.document_graph.AddDocument(document);
  report.stage = "document_scanner";
  report.AddDiagnostic("info", "stage_executed", document.document_id, "CaaDocumentScanner executed", report.stage);
  return document.document_kind != "unsupported";
}

}
