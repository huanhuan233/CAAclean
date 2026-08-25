#include "caa/CaaNativeFeatureExtractors.h"

namespace cadcapture {

static const char* CanonicalFromStartupType(const std::string& startup_type)
{
  if (startup_type == "EdgeFillet") return "fillet";
  if (startup_type == "Draft") return "draft";
  if (startup_type == "Chamfer") return "chamfer";
  if (startup_type == "Shaft") return "shaft";
  if (startup_type == "Groove") return "groove";
  if (startup_type == "Rib") return "rib";
  if (startup_type == "Slot") return "slot";
  if (startup_type == "Shell") return "shell";
  if (startup_type == "Thickness") return "thickness";
  if (startup_type == "RectPattern") return "rectangular_pattern";
  if (startup_type == "CircPattern") return "circular_pattern";
  if (startup_type == "UserPattern") return "user_pattern";
  if (startup_type == "Add") return "add";
  if (startup_type == "Remove") return "remove";
  if (startup_type == "Assemble") return "assemble";
  if (startup_type == "Intersect") return "intersect";
  if (startup_type == "GSMPoint" || startup_type == "GSMPointCoord") return "point";
  if (startup_type == "GSMLine" || startup_type == "GSMLinePtPt") return "line";
  if (startup_type == "GSMPlane" || startup_type == "GSMPlaneOffset") return "plane";
  if (startup_type == "AxisSystem") return "axis_system";
  if (startup_type == "GSMExtrude") return "gsd_extrude";
  if (startup_type == "GSMRevol") return "gsd_revolve";
  if (startup_type == "GSMOffset") return "gsd_offset";
  return "";
}

bool CaaNativeFeatureExtractors::Extract(CaptureIdRegistry& ids, ReconstructionPackage& package)
{
  size_t i;
  long type_only_count = 0;
  long generic_count = 0;
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    SemanticFacet facet;
    facet.facet_id = ids.NextSemanticFacetId();
    facet.subject_id = object.object_id;
    facet.source_api = "ObjectEntity.startup_type";
    facet.read_status = "available";

    const char* canonical = CanonicalFromStartupType(object.startup_type);
    if (canonical[0])
    {
      facet.facet_kind = "native_feature_type";
      facet.canonical_family = canonical;
      facet.decoder_id = "StartupTypeCanonicalDecoder";
      facet.decode_level = "type_only";
      facet.decode_status = "type_only";
      facet.payload_extraction_status = "not_available";
      ++type_only_count;
    }
    else
    {
      facet.facet_kind = "opaque_native_object";
      facet.canonical_family = "opaque";
      facet.decoder_id = "generic";
      facet.decode_level = "generic";
      facet.decode_status = "available";
      facet.payload_extraction_status = "not_available";
      ++generic_count;
    }
    package.semantic_facets.push_back(facet);
  }

  package.diagnostics.push_back(MakeDiagnostic("info", "native_feature_type_only",
                                               "native_features",
                                               "Startup type canonical semantic facets emitted; dedicated native parameter payloads remain unavailable until migrated",
                                               "native_feature_extractors"));
  (void)type_only_count;
  (void)generic_count;
  return true;
}

}
