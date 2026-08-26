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

struct NativeObjectBinding
{
  std::string object_id;
  void* native_spec_object;

  NativeObjectBinding() : native_spec_object(0) {}
};

struct ReconstructionPackage
{
  DocumentGraph document_graph;
  std::vector<ProductReferenceEntity> product_references;
  std::vector<ProductOccurrence> product_occurrences;
  std::vector<ObjectEntity> objects;
  std::vector<NativeObjectBinding> native_object_bindings;
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
  std::string capture_status;

  ReconstructionPackage() : capture_status("bootstrap") {}
};

}

#endif
