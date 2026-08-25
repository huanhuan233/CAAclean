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

struct ReconstructionPackage
{
  DocumentGraph document_graph;
  std::vector<ProductReferenceEntity> product_references;
  std::vector<ProductOccurrence> product_occurrences;
  std::vector<ObjectEntity> objects;
  OccurrenceGraph occurrence_graph;
  std::vector<PropertyFact> properties;
  std::vector<SemanticFacet> semantic_facets;
  std::vector<FeatureDependency> feature_dependencies;
  std::vector<GeometryEntity> geometry;
  std::vector<TopologyEntity> topology;
  std::vector<TopologyRelation> topology_relations;
  std::vector<PmiEntity> pmi;
  std::vector<PmiAssociation> pmi_associations;
  std::vector<Diagnostic> diagnostics;
  std::string reconstruction_plan;
  std::string capture_status;

  ReconstructionPackage() : capture_status("bootstrap") {}
};

}

#endif
