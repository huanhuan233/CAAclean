#include "caa/CaaSketchExtractor.h"
#include "caa/CaaNativeBindingIndex.h"
#include <CATIACircle2D.h>
#include <CATIACurve2D.h>
#include <CATIAGeometricElement.h>
#include <CATIAGeometricElements.h>
#include <CATIAGeometry2D.h>
#include <CATIALine2D.h>
#include <CATIAPoint2D.h>
#include <CATIASketch.h>
#include <CATISpecObject.h>
#include <CATSafeArray.h>
#include <CATVariant.h>
#include <windows.h>
#include <float.h>
#include <cmath>
#include <iomanip>
#include <sstream>

namespace cadcapture {

template <class T> class SketchGuard
{
public:
  SketchGuard() : _ptr(0) {}
  ~SketchGuard() { if (_ptr) _ptr->Release(); }
  T* Get() const { return _ptr; }
  T*& Out() { return _ptr; }
private:
  SketchGuard(const SketchGuard&);
  SketchGuard& operator=(const SketchGuard&);
  T* _ptr;
};

static bool SketchNumber(const CATVariant& value, double& output)
{
  if (value.vt == VT_R8) output = value.dblVal;
  else if (value.vt == VT_R4) output = value.fltVal;
  else if (value.vt == VT_I4) output = static_cast<double>(value.lVal);
  else return false;
  return _finite(output) != 0;
}

static bool SketchValues(CATSafeArrayVariant* array, int count, double* output)
{
  long lower = 0, upper = -1;
  if (!array || FAILED(SafeArrayGetLBound(array, 1, &lower)) ||
      FAILED(SafeArrayGetUBound(array, 1, &upper)) || upper - lower + 1 < count)
    return false;
  CATVariant* values = 0;
  if (FAILED(SafeArrayAccessData(array, reinterpret_cast<void**>(&values))) || !values)
    return false;
  bool okay = true;
  int i;
  for (i = 0; i < count; ++i) if (!SketchNumber(values[i], output[i])) okay = false;
  SafeArrayUnaccessData(array);
  return okay;
}

static bool SketchAxis(CATIASketch* sketch, double axis[9])
{
  CATSafeArrayVariant* array = SafeArrayCreateVector(VT_VARIANT, 0, 9);
  if (!array) return false;
  const bool okay = SUCCEEDED(sketch->GetAbsoluteAxisData(*array)) && SketchValues(array, 9, axis);
  SafeArrayDestroy(array);
  if (!okay) return false;
  double h = 0, v = 0, dot = 0;
  int i;
  for (i = 0; i < 3; ++i)
  { h += axis[i+3]*axis[i+3]; v += axis[i+6]*axis[i+6]; dot += axis[i+3]*axis[i+6]; }
  return fabs(h-1) < 1e-5 && fabs(v-1) < 1e-5 && fabs(dot) < 1e-5;
}

static bool CurveValues(CATIACurve2D* curve, int kind, double parameter,
                        int count, double* output)
{
  CATSafeArrayVariant* array = SafeArrayCreateVector(VT_VARIANT, 0, count);
  if (!array) return false;
  HRESULT status = E_FAIL;
  if (kind == 0) status = curve->GetEndPoints(*array);
  else if (kind == 1) status = curve->GetParamExtents(*array);
  else status = curve->GetPointAtParam(parameter, *array);
  const bool okay = SUCCEEDED(status) && SketchValues(array, count, output);
  SafeArrayDestroy(array);
  return okay;
}

static std::string Point3(double x, double y, const double axis[9])
{
  std::ostringstream out;
  out << std::setprecision(15) << "[" << axis[0]+x*axis[3]+y*axis[6] << ","
      << axis[1]+x*axis[4]+y*axis[7] << "," << axis[2]+x*axis[5]+y*axis[8] << "]";
  return out.str();
}

static bool SketchElement(CATIAGeometricElement* element, long index,
                          const double axis[9], std::string& output, bool& partial)
{
  if (!element) return false;
  CatGeometricType type = catGeoTypeUnknown;
  if (FAILED(element->get_GeometricType(type))) return false;
  SketchGuard<CATIAGeometry2D> geometry;
  if (FAILED(element->QueryInterface(IID_CATIAGeometry2D,
                                     reinterpret_cast<void**>(&geometry.Out()))) || !geometry.Get()) return false;
  CATLONG report = 0;
  const bool stable = SUCCEEDED(geometry.Get()->get_ReportName(report));
  CAT_VARIANT_BOOL construction = FALSE;
  const bool construction_ok = SUCCEEDED(geometry.Get()->get_Construction(construction));
  std::ostringstream out;
  out << "{\"element_id\":\"" << (stable ? "report_" : "index_")
      << (stable ? report : index) << "\",\"id_status\":\""
      << (stable ? "native_report_name" : "collection_index") << "\","
      << "\"construction\":" << (construction_ok ? (construction != FALSE ? "true" : "false") : "null") << ",";
  if (type == catGeoTypePoint2D)
  {
    SketchGuard<CATIAPoint2D> point;
    if (FAILED(element->QueryInterface(IID_CATIAPoint2D, reinterpret_cast<void**>(&point.Out()))) || !point.Get()) return false;
    CATSafeArrayVariant* array = SafeArrayCreateVector(VT_VARIANT, 0, 2);
    if (!array) return false;
    double xy[2];
    const bool read = SUCCEEDED(point.Get()->GetCoordinates(*array)) && SketchValues(array, 2, xy);
    SafeArrayDestroy(array);
    if (!read) return false;
    out << "\"kind\":\"point\",\"xy_mm\":[" << xy[0] << "," << xy[1]
        << "],\"display_points_3d_mm\":[" << Point3(xy[0], xy[1], axis) << "]";
  }
  else if (type == catGeoTypeLine2D || type == catGeoTypeCircle2D)
  {
    SketchGuard<CATIACurve2D> curve;
    if (FAILED(element->QueryInterface(IID_CATIACurve2D, reinterpret_cast<void**>(&curve.Out()))) || !curve.Get()) return false;
    double ends[4];
    if (!CurveValues(curve.Get(), 0, 0, 4, ends)) return false;
    out << "\"endpoints_2d_mm\":[[" << ends[0] << "," << ends[1] << "],["
        << ends[2] << "," << ends[3] << "]],";
    if (type == catGeoTypeLine2D)
      out << "\"kind\":\"line\",\"display_points_3d_mm\":["
          << Point3(ends[0], ends[1], axis) << "," << Point3(ends[2], ends[3], axis) << "]";
    else
    {
      SketchGuard<CATIACircle2D> circle;
      if (FAILED(element->QueryInterface(IID_CATIACircle2D, reinterpret_cast<void**>(&circle.Out()))) || !circle.Get()) return false;
      double radius = 0, range[2];
      CAT_VARIANT_BOOL periodic = FALSE;
      if (FAILED(circle.Get()->get_Radius(radius)) || radius <= 0 ||
          FAILED(circle.Get()->IsPeriodic(periodic)) ||
          !CurveValues(curve.Get(), 1, 0, 2, range)) return false;
      const double span = fabs(range[1]-range[0]);
      if (span <= 0 || span > 7.0) return false;
      int samples = static_cast<int>(ceil(span*sqrt(radius/0.8)));
      if (samples < 16) samples = 16;
      if (samples > 256) { samples = 256; partial = true; }
      out << "\"kind\":\"" << (periodic != FALSE ? "circle" : "arc") << "\","
          << "\"radius_mm\":" << radius << ",\"parameter_range_raw\":["
          << range[0] << "," << range[1] << "],\"display_chord_error_target_mm\":0.1,"
          << "\"display_sample_limit_reached\":" << (samples == 256 ? "true" : "false")
          << ",\"display_points_3d_mm\":[";
      int i;
      for (i = 0; i <= samples; ++i)
      {
        double xy[2];
        const double parameter = range[0]+(range[1]-range[0])*i/samples;
        if (!CurveValues(curve.Get(), 2, parameter, 2, xy)) return false;
        if (i) out << ",";
        out << Point3(xy[0], xy[1], axis);
      }
      out << "]";
    }
  }
  else
  {
    partial = true;
    out << "\"kind\":\"unsupported\",\"raw_geometric_type\":" << static_cast<int>(type)
        << ",\"read_status\":\"unsupported\"";
  }
  out << "}";
  output = out.str();
  return true;
}

static void ExtractSketches(CaptureIdRegistry& ids, CaaCapabilityBroker& broker,
                            ReconstructionPackage& package, const std::string& document_id)
{
  CaaNativeBindingIndex bindings(package);
  size_t i;
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    if ((object.startup_type != "Sketch" && object.startup_type != "PRTSketch") ||
        (!document_id.empty() && object.document_id != document_id)) continue;
    SemanticFacet* facet = 0;
    size_t j;
    for (j = 0; j < package.semantic_facets.size(); ++j)
      if (package.semantic_facets[j].subject_id == object.object_id)
      { facet = &package.semantic_facets[j]; break; }
    if (facet && facet->decoder_id == "NativeSketchDecoder") continue;
    CaaCapabilityLease lease;
    broker.Acquire<CATIASketch>(bindings.FindSpec(object.object_id), IID_CATIASketch,
                                "native_feature.CATIASketch", object.object_id, package, lease);
    CATIASketch* sketch = lease.As<CATIASketch>();
    double axis[9];
    if (!sketch || !SketchAxis(sketch, axis)) continue;
    SketchGuard<CATIAGeometricElements> elements;
    if (FAILED(sketch->get_GeometricElements(elements.Out())) || !elements.Get()) continue;
    CATLONG count = 0;
    if (FAILED(elements.Get()->get_Count(count)) || count < 0 || count > 10000) continue;
    std::ostringstream payload;
    payload << "\"native_sketch\":{\"semantic_kind\":\"sketch_geometry\","
            << "\"interface_key\":\"CATIASketch\",\"unit\":\"mm\","
            << "\"support_reference_status\":\"not_exposed_by_CATIASketch\","
            << "\"axis\":{\"origin_mm\":" << Point3(0, 0, axis) << ","
            << "\"x_axis\":[" << axis[3] << "," << axis[4] << "," << axis[5] << "],"
            << "\"y_axis\":[" << axis[6] << "," << axis[7] << "," << axis[8] << "],"
            << "\"normal\":[" << axis[4]*axis[8]-axis[5]*axis[7] << ","
            << axis[5]*axis[6]-axis[3]*axis[8] << ","
            << axis[3]*axis[7]-axis[4]*axis[6] << "],\"status\":\"verified_orthonormal\"},"
            << "\"element_count\":" << count << ",\"elements\":[";
    bool partial = false;
    bool first = true;
    CATLONG item;
    for (item = 1; item <= count; ++item)
    {
      CATVariant index;
      VariantInit(&index);
      index.vt = VT_I4;
      index.lVal = item;
      SketchGuard<CATIAGeometricElement> element;
      std::string element_json;
      if (FAILED(elements.Get()->Item(index, element.Out())) || !element.Get() ||
          !SketchElement(element.Get(), item, axis, element_json, partial))
      { partial = true; continue; }
      if (!first) payload << ",";
      first = false;
      payload << element_json;
    }
    payload << "],\"connection_status\":\"not_evaluated\","
            << "\"read_status\":\"" << (partial ? "partial" : "success") << "\"}";
    if (!facet)
    {
      SemanticFacet created;
      created.facet_id = ids.NextSemanticFacetId();
      created.subject_id = object.object_id;
      package.semantic_facets.push_back(created);
      facet = &package.semantic_facets.back();
    }
    facet->facet_kind = "native_feature_type";
    facet->canonical_family = "sketch";
    facet->decoder_id = "NativeSketchDecoder";
    facet->decode_level = "typed";
    facet->decode_status = partial ? "partial" : "success";
    facet->payload_extraction_status = "available";
    facet->payload_json_property = payload.str();
    facet->source_api = "CATIASketch";
    facet->read_status = partial ? "partial" : "available";
  }
}

void CaaSketchExtractor::Extract(CaptureIdRegistry& ids, CaaCapabilityBroker& broker,
                                 ReconstructionPackage& package)
{ ExtractSketches(ids, broker, package, ""); }

void CaaSketchExtractor::ExtractForDocument(CaptureIdRegistry& ids, CaaCapabilityBroker& broker,
                                            ReconstructionPackage& package, const std::string& document_id)
{ ExtractSketches(ids, broker, package, document_id); }

}
