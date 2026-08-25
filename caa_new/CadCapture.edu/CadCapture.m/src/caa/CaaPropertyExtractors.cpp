#include "caa/CaaPropertyExtractors.h"

#include <sstream>

namespace cadcapture {

static std::string LongToString(long value)
{
  std::ostringstream out;
  out << value;
  return out.str();
}

static void AddFact(CaptureIdRegistry& ids,
                    ReconstructionPackage& package,
                    const std::string& subject_id,
                    const std::string& tab_id,
                    const std::string& tab_label,
                    const std::string& group_id,
                    const std::string& group_label,
                    const std::string& key,
                    const std::string& display_name,
                    const std::string& value,
                    const std::string& value_type,
                    const std::string& source_api,
                    long display_order)
{
  if (value.empty())
    return;
  PropertyFact fact;
  fact.property_id = ids.NextPropertyFactId();
  fact.subject_id = subject_id;
  fact.tab_id = tab_id;
  fact.tab_label = tab_label;
  fact.group_id = group_id;
  fact.group_label = group_label;
  fact.group = group_id;
  fact.key = key;
  fact.display_name = display_name;
  fact.raw_value = value;
  fact.display_value = value;
  fact.value_type = value_type;
  fact.source_api = source_api;
  fact.read_status = "available";
  fact.authority = "captured_native_tree";
  fact.display_order = display_order;
  fact.read_only = true;
  package.properties.push_back(fact);
}

bool CaaPropertyExtractors::Extract(CaptureIdRegistry& ids, ReconstructionPackage& package)
{
  size_t i;
  for (i = 0; i < package.document_graph.documents.size(); ++i)
  {
    const DocumentEntity& document = package.document_graph.documents[i];
    AddFact(ids, package, document.document_id, "attributes", "Attributes", "document", "Document",
            "document_kind", "Document kind", document.document_kind, "string", "DocumentGraph", 10);
    AddFact(ids, package, document.document_id, "attributes", "Attributes", "document", "Document",
            "display_name", "Display name", document.display_name, "string", "DocumentGraph", 20);
    AddFact(ids, package, document.document_id, "attributes", "Attributes", "document", "Document",
            "source_file_name", "Source file", document.source_file_name, "string", "DocumentGraph", 30);
    AddFact(ids, package, document.document_id, "attributes", "Attributes", "document", "Document",
            "load_status", "Load status", document.load_status, "string", "DocumentGraph", 40);
    AddFact(ids, package, document.document_id, "attributes", "Attributes", "document", "Document",
            "native_document_open_status", "Native open status", document.native_document_open_status, "string", "DocumentGraph", 50);
    AddFact(ids, package, document.document_id, "attributes", "Attributes", "document", "Document",
            "definition_status", "Definition status", document.definition_status, "string", "DocumentGraph", 60);
  }

  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    AddFact(ids, package, object.object_id, "attributes", "Attributes", "identity", "Identity",
            "display_name", "Display name", object.display_name, "string", "ObjectEntity", 10);
    AddFact(ids, package, object.object_id, "attributes", "Attributes", "identity", "Identity",
            "internal_name", "Internal name", object.internal_name, "string", "ObjectEntity", 20);
    AddFact(ids, package, object.object_id, "attributes", "Attributes", "identity", "Identity",
            "startup_type", "Startup type", object.startup_type, "string", "ObjectEntity", 30);
    AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "update", "Update",
            "update_status", "Update status", object.update_status, "string", "CATISpecObject.IsUpToDate", 40);
    AddFact(ids, package, object.object_id, "attributes", "Attributes", "identity", "Identity",
            "document_id", "Document ID", object.document_id, "string", "ObjectEntity", 50);
    AddFact(ids, package, object.object_id, "attributes", "Attributes", "identity", "Identity",
            "object_id", "Object ID", object.object_id, "string", "ObjectEntity", 60);
    AddFact(ids, package, object.object_id, "attributes", "Attributes", "identity", "Identity",
            "geometry_status", "Geometry status", package.geometry.empty() ? "not_available" : "available", "string", "GeometryIR", 70);
  }

  for (i = 0; i < package.occurrence_graph.object_occurrences.size(); ++i)
  {
    const ObjectOccurrence& occurrence = package.occurrence_graph.object_occurrences[i];
    AddFact(ids, package, occurrence.occurrence_id, "attributes", "Attributes", "occurrence", "Occurrence",
            "occurrence_id", "Occurrence ID", occurrence.occurrence_id, "string", "ObjectOccurrence", 10);
    AddFact(ids, package, occurrence.occurrence_id, "attributes", "Attributes", "occurrence", "Occurrence",
            "tree_path", "Tree path", occurrence.tree_path, "string", "ObjectOccurrence", 20);
    AddFact(ids, package, occurrence.occurrence_id, "attributes", "Attributes", "occurrence", "Occurrence",
            "source_index", "Source index", LongToString(occurrence.source_index), "integer", "ObjectOccurrence", 30);
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "occurrence", "Occurrence",
            "product_occurrence_id", "Product occurrence ID", occurrence.product_occurrence_id, "string", "ObjectOccurrence", 40);
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "occurrence", "Occurrence",
            "reference_id", "Reference ID", occurrence.reference_id, "string", "ObjectOccurrence", 50);
  }

  for (i = 0; i < package.product_occurrences.size(); ++i)
  {
    const ProductOccurrence& occurrence = package.product_occurrences[i];
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "product_instance", "Product instance",
            "instance_name", "Instance name", occurrence.instance_name, "string", "CATIProduct.GetPrdInstanceName", 10);
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "product_instance", "Product instance",
            "part_number", "Part number", occurrence.part_number, "string", "CATIProduct.GetPartNumber", 20);
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "product_instance", "Product instance",
            "reference_id", "Reference ID", occurrence.reference_id, "string", "ProductReferenceEntity", 30);
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "product_instance", "Product instance",
            "load_status", "Load status", occurrence.load_status, "string", "CaaProductEnumerator", 40);
    AddFact(ids, package, occurrence.occurrence_id, "product", "Product", "product_instance", "Product instance",
            "transform_status", "Transform status", occurrence.transform_status, "string", "CATIMovable.GetAbsPosition", 50);
  }

  package.diagnostics.push_back(MakeDiagnostic("info", "stage_executed", "properties",
                                               "CaaPropertyExtractors emitted additive PropertyFact records from captured evidence",
                                               "property_extractors"));
  return true;
}

}
