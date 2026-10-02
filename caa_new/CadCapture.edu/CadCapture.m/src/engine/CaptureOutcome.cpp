#include "engine/CaptureOutcome.h"

namespace cadcapture {
namespace {

// 中文：能力探针只说明某个可选接口不可用，不代表已采集的主树缺失。
bool IsRequiredFailure(const Diagnostic& diagnostic)
{
  if (diagnostic.severity == "error") return true;
  if (diagnostic.severity != "warning") return false;
  return diagnostic.code != "capability_unsupported";
}

}

// 中文：树证据与必需阶段诊断共同决定状态，不再无条件写 partial。
bool CaptureOutcome::Finalize(ReconstructionPackage& package, const CapturePolicy& policy,
                              std::string& error)
{
  std::string failure;
  if (package.document_graph.documents.empty() || package.objects.empty() ||
      (package.occurrence_graph.object_occurrences.empty() && package.product_occurrences.empty()))
    failure = "required_native_tree_empty";
  for (size_t i = 0; i < package.diagnostics.size(); ++i)
  {
    if (IsRequiredFailure(package.diagnostics[i]))
    {
      failure = package.diagnostics[i].code;
      break;
    }
  }
  package.capture_status = failure.empty() ? "complete" : "partial";
  if (!failure.empty() && !policy.allow_partial_capture)
  {
    error = "strict capture policy rejected partial package: " + failure;
    return false;
  }
  error.clear();
  return true;
}

}
