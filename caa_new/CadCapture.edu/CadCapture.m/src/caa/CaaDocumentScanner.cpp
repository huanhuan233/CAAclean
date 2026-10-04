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

bool CaaDocumentScanner::Scan(const std::string& input_path,
                              CaaDocumentHandle& document_handle,
                              CaptureIdRegistry& ids,
                              ReconstructionPackage& package,
                              std::string& error)
{
  if (!document_handle.OpenReadOnly(input_path, error))
    return false;

  DocumentEntity document;
  document.document_id = ids.NextDocumentId();
  document.source_file_name = CaptureBaseName(input_path);
  document.display_name = document_handle.DisplayName();
  if (document.display_name.empty())
    document.display_name = document.source_file_name;
  document.load_status = "loaded";
  document.native_document_open_status = "opened_read_only";
  document.definition_status = "root_document";
  document.identity_method = "opened_document_handle";

  const std::string ext = CaptureExtension(input_path);
  if (ext == ".catpart")
  {
    document.document_kind = "catpart";
    document.capture_status = "opened";
  }
  else if (ext == ".catproduct")
  {
    document.document_kind = "catproduct";
    document.capture_status = "opened";
  }
  else
  {
    document.document_kind = "unsupported";
    document.capture_status = "unsupported";
    error = "unsupported input extension";
  }

  package.document_graph.AddDocument(document);
  NativeDocumentBinding binding;
  binding.document_id = document.document_id;
  binding.native_document = document_handle.NativeDocumentForCaaOnly();
  package.native_document_bindings.push_back(binding);
  package.diagnostics.push_back(MakeDiagnostic("info", "document_opened", document.document_id,
                                               "CaaDocumentScanner opened native CATIA document read-only",
                                               "document_scanner"));
  return document.document_kind != "unsupported";
}

}
