#include "model/CaptureEvidenceSummary.h"
#include <map>

namespace cadcapture {

// 中文：拒绝把零三角形的占位范围当作前端可渲染网格。
bool CaptureEvidenceSummary::HasMesh(const ReconstructionPackage& package)
{
  if (!package.mesh_triangles.empty()) return true;
  for (size_t i = 0; i < package.geometry.size(); ++i)
  {
    const GeometryEntity& geometry = package.geometry[i];
    if (geometry.triangle_count > 0 &&
        (geometry.representation_status == "success" || geometry.representation_status == "partial"))
      return true;
  }
  return false;
}

// 中文：仅采集到类型与参数的拓扑几何可供精确重建判断。
bool CaptureEvidenceSummary::HasExactGeometry(const ReconstructionPackage& package)
{
  for (size_t i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& topology = package.topology[i];
    if (!topology.exact_geometry_type.empty() && !topology.geometry_parameters_json.empty() &&
        topology.geometry_status == "exact")
      return true;
  }
  return false;
}

// 中文：已加载的文档链接与关联件定义必须同时存在，才能声明解析可用。
std::string CaptureEvidenceSummary::LinkedDocuments(const ReconstructionPackage& package)
{
  std::map<std::string, bool> loaded_links;
  for (size_t i = 0; i < package.document_graph.links.size(); ++i)
  {
    const DocumentLink& link = package.document_graph.links[i];
    if (link.link_status == "loaded") loaded_links[link.reference_id] = true;
  }
  size_t candidate_count = 0;
  size_t resolved_count = 0;
  for (size_t i = 0; i < package.product_references.size(); ++i)
  {
    const ProductReferenceEntity& reference = package.product_references[i];
    if (reference.definition_status == "same_document_product_reference") continue;
    ++candidate_count;
    if (loaded_links.find(reference.reference_id) != loaded_links.end() &&
        (!reference.referenced_document_id.empty()) &&
        (reference.reference_document_kind != "catpart" || reference.definition_status == "definition_captured"))
      ++resolved_count;
  }
  if (candidate_count == 0) return "not_applicable";
  if (resolved_count == candidate_count) return "available";
  return "partial";
}

// 中文：只计数上游确实写入的身份，不把空的默认身份标成已解析。
size_t CaptureEvidenceSummary::CapturedIdentities(const ReconstructionPackage& package)
{
  size_t count = 0;
  for (size_t i = 0; i < package.objects.size(); ++i)
  {
    const ObjectIdentity& identity = package.objects[i].identity;
    if (!identity.capture_id.empty() && identity.read_status != "unavailable") ++count;
  }
  return count;
}

}
