#include "model/GeometryStatusProjector.h"
#include <map>

namespace cadcapture {
namespace {

struct GeometryEvidence
{
  bool topology;
  bool exact;
  bool partial;
  bool failed;
  bool mesh;
  GeometryEvidence() : topology(false), exact(false), partial(false), failed(false), mesh(false) {}
};

// 中文：将单条拓扑的读取结果合并到其真实归属对象，不推断其他兄弟节点。
void ObserveTopology(GeometryEvidence& evidence, const TopologyEntity& entity)
{
  evidence.topology = true;
  const std::string& status = entity.geometry_status;
  if (status == "exact" || status == "exact_surface" || status == "exact_curve")
    evidence.exact = true;
  else if (status.find("partial") != std::string::npos || status == "unknown")
    evidence.partial = true;
  else if (status == "failed" || status == "integrity_error" || entity.read_status == "failed")
    evidence.failed = true;
}

// 中文：仅在真实三角形存在时记为网格，空范围不冒充可用几何。
void ObserveGeometry(GeometryEvidence& evidence, const GeometryEntity& entity)
{
  if (entity.representation_status == "failed" || entity.representation_status == "integrity_error")
    evidence.failed = true;
  if (entity.triangle_count > 0 &&
      (entity.representation_status == "success" || entity.representation_status == "available"))
    evidence.mesh = true;
}

// 中文：状态只表示该对象拥有的证据，不等同于完整参数化重建等级。
std::string EvidenceStatus(const GeometryEvidence& evidence)
{
  if (evidence.failed && (evidence.exact || evidence.mesh || evidence.topology))
    return "partial";
  if (evidence.failed)
    return "failed";
  if (evidence.partial)
    return "partial";
  if (evidence.exact)
    return "exact";
  if (evidence.mesh)
    return "mesh_available";
  if (evidence.topology)
    return "topology_only";
  return "not_available";
}

// 中文：CATPart 文档根与 MechanicalPart 代表最终体；普通特征不能继承整件几何。
bool UsesDocumentBody(const ObjectEntity& object)
{
  return object.object_kind == "catia_document" || object.startup_type == "MechanicalPart" ||
         object.startup_type == "Part";
}

// 中文：更新已有事实或追加唯一事实，保持属性页字段与旧数据库结构兼容。
void PutStatus(CaptureIdRegistry& ids, ReconstructionPackage& package,
               std::map<std::string, size_t>& existing,
               const ObjectEntity& object, const std::string& value)
{
  PropertyFact* fact = 0;
  std::map<std::string, size_t>::iterator found = existing.find(object.object_id);
  if (found != existing.end())
    fact = &package.properties[found->second];
  else
  {
    PropertyFact created;
    created.property_id = ids.NextPropertyFactId();
    created.subject_id = object.object_id;
    package.properties.push_back(created);
    existing[object.object_id] = package.properties.size() - 1;
    fact = &package.properties.back();
  }
  fact->tab_id = "attributes";
  fact->tab_label = "Attributes";
  fact->group_id = "identity";
  fact->group_label = "Identity";
  fact->group = "identity";
  fact->key = "geometry_status";
  fact->display_name = "Geometry status";
  fact->raw_value = value;
  fact->raw_display_text = value;
  fact->display_value = value;
  fact->value_type = "string";
  fact->source_api = "GeometryStatusProjector";
  fact->read_status = "available";
  fact->authority = "captured_native_topology";
  fact->display_order = 70;
  fact->read_only = true;
}

}

// 中文：全部拓扑采集后一次投影对象状态，旧事实可原位更新且重复调用不新增记录。
void GeometryStatusProjector::Apply(CaptureIdRegistry& ids, ReconstructionPackage& package) const
{
  std::map<std::string, GeometryEvidence> evidence_by_subject;
  size_t i;
  for (i = 0; i < package.topology.size(); ++i)
    ObserveTopology(evidence_by_subject[package.topology[i].subject_id], package.topology[i]);
  for (i = 0; i < package.geometry.size(); ++i)
    ObserveGeometry(evidence_by_subject[package.geometry[i].subject_id], package.geometry[i]);

  std::map<std::string, size_t> existing;
  for (i = 0; i < package.properties.size(); ++i)
  {
    if (package.properties[i].key == "geometry_status")
      existing[package.properties[i].subject_id] = i;
  }
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    std::map<std::string, GeometryEvidence>::const_iterator direct = evidence_by_subject.find(object.object_id);
    std::string status = direct == evidence_by_subject.end() ? "not_available" : EvidenceStatus(direct->second);
    if (status == "not_available" && UsesDocumentBody(object))
    {
      std::map<std::string, GeometryEvidence>::const_iterator document =
        evidence_by_subject.find(object.document_id);
      if (document != evidence_by_subject.end())
        status = EvidenceStatus(document->second);
    }
    PutStatus(ids, package, existing, object, status);
  }
}

}
