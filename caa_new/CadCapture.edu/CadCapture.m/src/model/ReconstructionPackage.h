// 汇集文档、对象、几何和语义证据以及采集期间的原生绑定。
#ifndef CADCAPTURE_MODEL_RECONSTRUCTIONPACKAGE_H
#define CADCAPTURE_MODEL_RECONSTRUCTIONPACKAGE_H

#include "model/DocumentGraph.h"
#include "model/ObjectIdentity.h"
#include "model/OccurrenceGraph.h"
#include "model/ProductStructure.h"
#include "model/PropertyFacts.h"
#include "model/SemanticFacts.h"
#include "model/GeometryIR.h"
#include "model/TopologyIR.h"
#include "model/PmiIR.h"
#include "model/CaptureStatus.h"
#include <string>
#include <vector>

namespace cadcapture {

// 仅在原生对象有效期间把包内 ID 关联到会话指针；本结构不执行引用计数或释放。
struct NativeObjectBinding
{
  std::string object_id;
  void* native_spec_object;

  NativeObjectBinding() : native_spec_object(0) {}
};

// Session-only identity. Never serialize a CATDocument pointer as a stable ID.
// 文档指针只用于当前会话内的身份匹配，不能序列化为跨会话稳定 ID。
struct NativeDocumentBinding
{
  std::string document_id;
  void* native_document;
  NativeDocumentBinding() : native_document(0) {}
};

// 各采集阶段共同填充的证据包，实体之间以 ID 连接，原生绑定仅供采集期间使用。
struct ReconstructionPackage
{
  DocumentGraph document_graph;
  std::vector<ProductReferenceEntity> product_references;
  std::vector<ProductOccurrence> product_occurrences;
  std::vector<ObjectEntity> objects;
  std::vector<NativeObjectBinding> native_object_bindings;
  std::vector<NativeDocumentBinding> native_document_bindings;
  OccurrenceGraph occurrence_graph;
  std::vector<PropertyFact> properties;
  std::vector<SemanticFacet> semantic_facets;
  std::vector<FeatureDependency> feature_dependencies;
  std::vector<GeometryEntity> geometry;
  std::vector<MeshTriangleEntity> mesh_triangles;
  std::vector<TopologyEntity> topology;
  std::vector<TopologyRelation> topology_relations;
  std::vector<NativeTopologyWireEntity> topology_wires;
  std::vector<NativeTopologyCoedgeEntity> topology_coedges;
  std::vector<NativeFeatureResultCellEntity> native_feature_result_cells;
  std::vector<NativeFeatureTopologyLinkEntity> native_feature_topology_links;
  std::vector<PmiEntity> pmi;
  std::vector<PmiAssociation> pmi_associations;
  std::vector<FtaSemanticEntity> fta_semantics;
  std::vector<Diagnostic> diagnostics;
  std::string reconstruction_plan;
  size_t exact_brep_body_count;
  size_t incomplete_brep_body_count;
  std::string capture_status;

  // 中文：新包默认没有经过逐体 B-Rep 判定，不能凭空声明精确体。
  ReconstructionPackage() : exact_brep_body_count(0), incomplete_brep_body_count(0),
                            capture_status("bootstrap") {}
};

}

#endif
