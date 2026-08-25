#include "caa/CaaPropertyExtractors.h"

#include <CATBaseUnknown.h>
#include <CATICkeInst.h>
#include <CATICkeParm.h>
#include <CATICkeType.h>
#include <CATIInertia.h>
#include <CATISpecObject.h>
#include <CATUnicodeString.h>
#include <sstream>
#include <vector>

namespace cadcapture {

static std::string DoubleToString(double value)
{
  std::ostringstream out;
  out.precision(17);
  out << value;
  return out.str();
}

static std::string LongToString(long value)
{
  std::ostringstream out;
  out << value;
  return out.str();
}

static std::string UnicodeToUtf8Local(const CATUnicodeString& value)
{
  const size_t capacity = static_cast<size_t>(value.GetLengthInChar() + 1) * 4 + 1;
  std::vector<char> buffer(capacity, 0);
  size_t byte_count = 0;
  value.ConvertToUTF8(&buffer[0], &byte_count);
  if (byte_count >= buffer.size())
    byte_count = buffer.size() - 1;
  buffer[byte_count] = 0;
  return std::string(&buffer[0], byte_count);
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

static CATISpecObject* FindNativeSpecObject(const ReconstructionPackage& package,
                                            const std::string& object_id)
{
  size_t i;
  for (i = 0; i < package.native_object_bindings.size(); ++i)
  {
    if (package.native_object_bindings[i].object_id == object_id)
      return static_cast<CATISpecObject*>(package.native_object_bindings[i].native_spec_object);
  }
  return 0;
}

static void AddMechanicalInertiaFacts(CaptureIdRegistry& ids,
                                      CaaCapabilityBroker& broker,
                                      ReconstructionPackage& package,
                                      const ObjectEntity& object,
                                      CATISpecObject* spec)
{
  if (!spec)
    return;

  CaaCapabilityLease inertia_lease;
  broker.Acquire<CATIInertia>(spec, IID_CATIInertia, "mechanical.CATIInertia",
                              object.object_id, package, inertia_lease);
  CATIInertia* inertia = inertia_lease.As<CATIInertia>();
  if (!inertia)
    return;

  double density = 0.0;
  double mass = 0.0;
  double position[3] = { 0.0, 0.0, 0.0 };
  double matrix[9] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };
  double components[9] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };
  double values[3] = { 0.0, 0.0, 0.0 };
  double volume = 0.0;
  double area = 0.0;

  HRESULT result = E_FAIL;
  try
  {
    result = inertia->GetInertia(&density, &mass, position, matrix, components, values, &volume, &area);
  }
  catch (...)
  {
    AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
            "catia_property_mechanical_status", "Mechanical status", "inertia_read_exception",
            "string", "CATIInertia.GetInertia", 1000);
    return;
  }

  if (FAILED(result))
  {
    AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
            "catia_property_mechanical_status", "Mechanical status", "inertia_read_failed",
            "string", "CATIInertia.GetInertia", 1000);
    return;
  }

  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_mechanical_status", "Mechanical status", "available",
          "string", "CATIInertia.GetInertia", 1000);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_density_kg_m3", "Density", DoubleToString(density),
          "number", "CATIInertia.GetInertia", 1010);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_mass_kg", "Mass", DoubleToString(mass),
          "number", "CATIInertia.GetInertia", 1020);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_volume_m3", "Volume", DoubleToString(volume),
          "number", "CATIInertia.GetInertia", 1030);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_area_m2", "Area", DoubleToString(area),
          "number", "CATIInertia.GetInertia", 1040);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_center_x_mm", "Center X", DoubleToString(position[0] * 1000.0),
          "number", "CATIInertia.GetInertia", 1050);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_center_y_mm", "Center Y", DoubleToString(position[1] * 1000.0),
          "number", "CATIInertia.GetInertia", 1060);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia", "Inertia",
          "catia_property_center_z_mm", "Center Z", DoubleToString(position[2] * 1000.0),
          "number", "CATIInertia.GetInertia", 1070);

  const char* matrix_keys[9] = {
    "catia_property_ixx_kg_m2", "catia_property_ixy_kg_m2", "catia_property_ixz_kg_m2",
    "catia_property_iyx_kg_m2", "catia_property_iyy_kg_m2", "catia_property_iyz_kg_m2",
    "catia_property_izx_kg_m2", "catia_property_izy_kg_m2", "catia_property_izz_kg_m2"
  };
  const char* matrix_names[9] = {
    "Ixx", "Ixy", "Ixz", "Iyx", "Iyy", "Iyz", "Izx", "Izy", "Izz"
  };
  long i;
  for (i = 0; i < 9; ++i)
  {
    AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "inertia_matrix", "Inertia matrix",
            matrix_keys[i], matrix_names[i], DoubleToString(matrix[i]),
            "number", "CATIInertia.GetInertia", 1100 + i);
  }

  const char* axis_keys[9] = {
    "catia_property_principal_axis_x1", "catia_property_principal_axis_y1", "catia_property_principal_axis_z1",
    "catia_property_principal_axis_x2", "catia_property_principal_axis_y2", "catia_property_principal_axis_z2",
    "catia_property_principal_axis_x3", "catia_property_principal_axis_y3", "catia_property_principal_axis_z3"
  };
  const char* axis_names[9] = {
    "Principal axis X1", "Principal axis Y1", "Principal axis Z1",
    "Principal axis X2", "Principal axis Y2", "Principal axis Z2",
    "Principal axis X3", "Principal axis Y3", "Principal axis Z3"
  };
  for (i = 0; i < 9; ++i)
  {
    AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "principal_axes", "Principal axes",
            axis_keys[i], axis_names[i], DoubleToString(components[i]),
            "number", "CATIInertia.GetInertia", 1200 + i);
  }

  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "principal_moments", "Principal moments",
          "catia_property_principal_moment_1_kg_m2", "Principal moment 1", DoubleToString(values[0]),
          "number", "CATIInertia.GetInertia", 1300);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "principal_moments", "Principal moments",
          "catia_property_principal_moment_2_kg_m2", "Principal moment 2", DoubleToString(values[1]),
          "number", "CATIInertia.GetInertia", 1310);
  AddFact(ids, package, object.object_id, "mechanical", "Mechanical", "principal_moments", "Principal moments",
          "catia_property_principal_moment_3_kg_m2", "Principal moment 3", DoubleToString(values[2]),
          "number", "CATIInertia.GetInertia", 1320);
}

static void AddKnowledgeParameterFacts(CaptureIdRegistry& ids,
                                       CaaCapabilityBroker& broker,
                                       ReconstructionPackage& package,
                                       const ObjectEntity& object,
                                       CATISpecObject* spec)
{
  if (!spec)
    return;

  CaaCapabilityLease parameter_lease;
  broker.Acquire<CATICkeParm>(spec, IID_CATICkeParm, "knowledgeware.CATICkeParm",
                              object.object_id, package, parameter_lease);
  CATICkeParm* parameter = parameter_lease.As<CATICkeParm>();
  if (!parameter)
    return;

  try
  {
    const CATICkeType_var parameter_type = parameter->Type();
    if (parameter_type == NULL_var || static_cast<int>(parameter_type->IsaString()) == 0)
      return;
    const CATICkeInst_var value = parameter->Value();
    if (value == NULL_var)
    {
      AddFact(ids, package, object.object_id, "knowledgeware", "Knowledgeware", "parameter", "Parameter",
              "catia_parameter_value_status", "Value status", "value_unavailable",
              "string", "CATICkeParm.Value", 2000);
      return;
    }
    AddFact(ids, package, object.object_id, "knowledgeware", "Knowledgeware", "parameter", "Parameter",
            "catia_parameter_kind", "Parameter kind", "string",
            "string", "CATICkeParm.Type", 2010);
    AddFact(ids, package, object.object_id, "knowledgeware", "Knowledgeware", "parameter", "Parameter",
            "catia_parameter_name", "Parameter name",
            object.display_name.empty() ? object.internal_name : object.display_name,
            "string", "CATISpecObject.GetDisplayName", 2020);
    AddFact(ids, package, object.object_id, "knowledgeware", "Knowledgeware", "parameter", "Parameter",
            "catia_parameter_value_text", "Parameter value", UnicodeToUtf8Local(value->AsString()),
            "string", "CATICkeParm.Value.AsString", 2030);
  }
  catch (...)
  {
    AddFact(ids, package, object.object_id, "knowledgeware", "Knowledgeware", "parameter", "Parameter",
            "catia_parameter_value_status", "Value status", "value_exception",
            "string", "CATICkeParm.Value", 2000);
  }
}

bool CaaPropertyExtractors::Extract(CaptureIdRegistry& ids,
                                    CaaCapabilityBroker& broker,
                                    ReconstructionPackage& package)
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

    CATISpecObject* spec = FindNativeSpecObject(package, object.object_id);
    AddMechanicalInertiaFacts(ids, broker, package, object, spec);
    AddKnowledgeParameterFacts(ids, broker, package, object, spec);
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
                                               "CaaPropertyExtractors emitted additive PropertyFact records from captured evidence and live CATIA Public interfaces",
                                               "property_extractors"));
  return true;
}

}
