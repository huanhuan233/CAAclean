#include "reconstruction/BrepCompleteness.h"
#include <map>
#include <set>

namespace cadcapture {
namespace {

typedef std::map<std::string, const TopologyEntity*> TopologyIndex;
typedef std::map<std::string, const NativeTopologyCoedgeEntity*> CoedgeIndex;
typedef std::map<std::string, std::vector<const TopologyEntity*> > BodyCells;
typedef std::map<std::string, std::vector<const NativeTopologyWireEntity*> > FaceWires;

// 中文：参数、读取状态和父体必须同时有效；只检查某一张精确面不足以代表整件。
bool ExactCell(const TopologyEntity& cell)
{
  return cell.geometry_status == "exact" && !cell.exact_geometry_type.empty() &&
         !cell.geometry_parameters_json.empty() &&
         (cell.read_status == "success" || cell.read_status == "available");
}

// 中文：全部边界端点必须是当前体的已读顶点。
bool ValidBoundary(const TopologyEntity& cell, const std::string& body_id,
                   const TopologyIndex& cells, const std::string& kind)
{
  if (cell.boundary_cell_ids.empty()) return false;
  for (size_t i = 0; i < cell.boundary_cell_ids.size(); ++i)
  {
    TopologyIndex::const_iterator endpoint = cells.find(cell.boundary_cell_ids[i]);
    if (endpoint == cells.end() || endpoint->second->parent_topology_id != body_id ||
        endpoint->second->topology_kind != kind ||
        (endpoint->second->read_status != "success" && endpoint->second->read_status != "available"))
      return false;
  }
  return true;
}

// 中文：线框要求闭合标记、边数一致，且每条有向边前后引用在同一线框内互相吻合。
bool ClosedWire(const NativeTopologyWireEntity& wire, const std::string& body_id,
                const TopologyIndex& cells, const CoedgeIndex& coedges,
                const std::map<std::string, std::vector<const NativeTopologyCoedgeEntity*> >& by_wire)
{
  if (wire.body_id != body_id || wire.closed_status.find("closed") != 0 || wire.edge_count <= 0)
    return false;
  std::map<std::string, std::vector<const NativeTopologyCoedgeEntity*> >::const_iterator found = by_wire.find(wire.wire_id);
  if (found == by_wire.end() || found->second.size() != static_cast<size_t>(wire.edge_count))
    return false;
  for (size_t i = 0; i < found->second.size(); ++i)
  {
    const NativeTopologyCoedgeEntity& coedge = *found->second[i];
    TopologyIndex::const_iterator edge = cells.find(coedge.edge_cell_id);
    CoedgeIndex::const_iterator previous = coedges.find(coedge.previous_coedge_id);
    CoedgeIndex::const_iterator next = coedges.find(coedge.next_coedge_id);
    if (coedge.body_id != body_id || coedge.owning_face_id != wire.owning_face_id ||
        edge == cells.end() || edge->second->parent_topology_id != body_id ||
        edge->second->topology_kind != "edge" || previous == coedges.end() || next == coedges.end() ||
        previous->second->wire_id != wire.wire_id || next->second->wire_id != wire.wire_id ||
        previous->second->next_coedge_id != coedge.coedge_id ||
        next->second->previous_coedge_id != coedge.coedge_id)
      return false;
  }
  return true;
}

// 中文：单体完整性只看本体子节点，混合装配中的其他 body 不能补齐此体缺口。
std::string BodyFailure(const TopologyEntity& body, const TopologyIndex& cells,
                        const BodyCells& by_body, const FaceWires& by_face,
                        const CoedgeIndex& coedges,
                        const std::map<std::string, std::vector<const NativeTopologyCoedgeEntity*> >& by_wire,
                        const std::set<std::string>& invalid_relation_bodies)
{
  if (body.read_status != "success" && body.read_status != "available") return "body_read_failed";
  if (body.face_count <= 0 || body.edge_count <= 0 || body.vertex_count <= 0 || body.volume_count <= 0)
    return "body_counts_unavailable";
  long face_count = 0, edge_count = 0, vertex_count = 0, volume_count = 0;
  BodyCells::const_iterator children = by_body.find(body.topology_id);
  if (children == by_body.end()) return "body_child_count_mismatch";
  for (size_t i = 0; i < children->second.size(); ++i)
  {
    const TopologyEntity& cell = *children->second[i];
    if (cell.read_status == "integrity_error" || cell.geometry_status == "integrity_error")
      return "topology_integrity_error";
    if (cell.topology_kind == "face")
    {
      ++face_count;
      if (!ExactCell(cell) || !ValidBoundary(cell, body.topology_id, cells, "edge"))
        return "face_exact_boundary_incomplete";
      FaceWires::const_iterator face_wires = by_face.find(cell.topology_id);
      if (face_wires == by_face.end() || face_wires->second.empty()) return "face_wire_missing";
      std::set<std::string> wire_edges;
      for (size_t wire_index = 0; wire_index < face_wires->second.size(); ++wire_index)
      {
        const NativeTopologyWireEntity& wire = *face_wires->second[wire_index];
        if (!ClosedWire(wire, body.topology_id, cells, coedges, by_wire)) return "face_wire_not_closed";
        std::map<std::string, std::vector<const NativeTopologyCoedgeEntity*> >::const_iterator group = by_wire.find(wire.wire_id);
        for (size_t coedge_index = 0; coedge_index < group->second.size(); ++coedge_index)
          wire_edges.insert(group->second[coedge_index]->edge_cell_id);
      }
      for (size_t edge_index = 0; edge_index < cell.boundary_cell_ids.size(); ++edge_index)
        if (wire_edges.find(cell.boundary_cell_ids[edge_index]) == wire_edges.end())
          return "face_boundary_coedge_missing";
    }
    else if (cell.topology_kind == "edge")
    {
      ++edge_count;
      if (!ExactCell(cell) || !ValidBoundary(cell, body.topology_id, cells, "vertex"))
        return "edge_exact_boundary_incomplete";
    }
    else if (cell.topology_kind == "vertex")
    {
      ++vertex_count;
      if (cell.read_status != "success" && cell.read_status != "available") return "vertex_read_failed";
    }
    else if (cell.topology_kind == "volume")
    {
      ++volume_count;
      if (cell.read_status != "success" && cell.read_status != "available") return "volume_read_failed";
    }
  }
  if (face_count != body.face_count || edge_count != body.edge_count ||
      vertex_count != body.vertex_count || volume_count != body.volume_count)
    return "body_child_count_mismatch";
  if (invalid_relation_bodies.find(body.topology_id) != invalid_relation_bodies.end())
    return "topology_relation_integrity_error";
  return "";
}

}

// 中文：输出逐体证据状态；只有所有主实体及 ResultOUT 均闭合且精确才可选 exact_brep。
BrepCompleteness BrepCompletenessEvaluator::Evaluate(const ReconstructionPackage& package) const
{
  TopologyIndex cells;
  CoedgeIndex coedges;
  BodyCells by_body;
  FaceWires by_face;
  std::set<std::string> invalid_relation_bodies;
  std::map<std::string, std::vector<const NativeTopologyCoedgeEntity*> > by_wire;
  for (size_t i = 0; i < package.topology.size(); ++i)
  {
    cells[package.topology[i].topology_id] = &package.topology[i];
    if (!package.topology[i].parent_topology_id.empty())
      by_body[package.topology[i].parent_topology_id].push_back(&package.topology[i]);
  }
  for (size_t i = 0; i < package.topology_wires.size(); ++i)
    by_face[package.topology_wires[i].owning_face_id].push_back(&package.topology_wires[i]);
  for (size_t i = 0; i < package.topology_coedges.size(); ++i)
  {
    const NativeTopologyCoedgeEntity& coedge = package.topology_coedges[i];
    coedges[coedge.coedge_id] = &coedge;
    by_wire[coedge.wire_id].push_back(&coedge);
  }
  for (size_t i = 0; i < package.topology_relations.size(); ++i)
  {
    const TopologyRelation& relation = package.topology_relations[i];
    if (relation.read_status != "integrity_error") continue;
    TopologyIndex::const_iterator from = cells.find(relation.from_topology_id);
    TopologyIndex::const_iterator to = cells.find(relation.to_topology_id);
    if (from != cells.end()) invalid_relation_bodies.insert(from->second->parent_topology_id.empty() ? from->second->topology_id : from->second->parent_topology_id);
    if (to != cells.end()) invalid_relation_bodies.insert(to->second->parent_topology_id.empty() ? to->second->topology_id : to->second->parent_topology_id);
  }
  BrepCompleteness result;
  for (size_t i = 0; i < package.topology.size(); ++i)
  {
    const TopologyEntity& body = package.topology[i];
    if (body.topology_kind != "body" && body.source_kind != "catishapefeaturebody_resultout") continue;
    BrepBodyStatus status;
    status.body_id = body.topology_id;
    status.reason = BodyFailure(body, cells, by_body, by_face, coedges, by_wire,
                                invalid_relation_bodies);
    status.status = status.reason.empty() ? "exact" : "partial";
    if (status.reason.empty()) ++result.exact_body_count;
    else ++result.incomplete_body_count;
    result.bodies.push_back(status);
  }
  return result;
}

}
