/* 汇总关联文档链接和定义的解析状态并输出诊断。 */
#include "caa/CaaLinkedDocumentResolver.h"
#include "model/CaptureEvidenceSummary.h"

namespace cadcapture {

// 中文：真实链接与定义均齐全才报告可用，缺失时保留部分状态供包级策略处理。
void CaaLinkedDocumentResolver::Resolve(ReconstructionPackage& package)
{
  const std::string status = CaptureEvidenceSummary::LinkedDocuments(package);
  package.diagnostics.push_back(MakeDiagnostic(status == "partial" ? "warning" : "info",
                                               "linked_document_resolution_" + status, "links",
                                               status == "available" ? "Linked document references and definitions were captured upstream"
                                               : status == "partial" ? "Some linked documents or definitions remain unresolved"
                                               : "No external linked document requires resolution",
                                               "linked_document_resolver"));
}

}
