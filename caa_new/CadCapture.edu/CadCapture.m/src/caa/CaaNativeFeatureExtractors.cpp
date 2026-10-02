#include "caa/CaaNativeFeatureExtractors.h"

#include <CATIAAngle.h>
#include <CATIAHole.h>
#include <CATIALength.h>
#include <CATIALimit.h>
#include <CATIAPad.h>
#include <CATIAPocket.h>
#include <CATIAPrism.h>
#include <CATIAStrParam.h>
#include <CATBSTR.h>
#include <CATISpecObject.h>
#include <CATLimitDefs.h>
#include <CATHoleDefs.h>
#include <CATPrismDefs.h>
#include <CATSafeArray.h>
#include <windows.h>
#include <iomanip>
#include <set>
#include <sstream>
#include <vector>

namespace cadcapture {

template <class T>
class CaaInterfaceGuard
{
public:
  CaaInterfaceGuard() : _ptr(0) {}
  explicit CaaInterfaceGuard(T* ptr) : _ptr(ptr) {}
  ~CaaInterfaceGuard() { if (_ptr) _ptr->Release(); }
  T* Get() const { return _ptr; }
  T*& Out() { return _ptr; }

private:
  CaaInterfaceGuard(const CaaInterfaceGuard&);
  CaaInterfaceGuard& operator=(const CaaInterfaceGuard&);
  T* _ptr;
};

class CaaBstrGuard
{
public:
  CaaBstrGuard() : _value(0) {}
  ~CaaBstrGuard() { if (_value) CATFreeString(_value); }
  CATBSTR& Out() { return _value; }
  CATBSTR Get() const { return _value; }

private:
  CaaBstrGuard(const CaaBstrGuard&);
  CaaBstrGuard& operator=(const CaaBstrGuard&);
  CATBSTR _value;
};

static std::string JsonEscape(const std::string& value)
{
  std::ostringstream out;
  size_t i;
  for (i = 0; i < value.size(); ++i)
  {
    const unsigned char c = static_cast<unsigned char>(value[i]);
    switch (c)
    {
    case '\\': out << "\\\\"; break;
    case '"': out << "\\\""; break;
    case '\b': out << "\\b"; break;
    case '\f': out << "\\f"; break;
    case '\n': out << "\\n"; break;
    case '\r': out << "\\r"; break;
    case '\t': out << "\\t"; break;
    default:
      if (c < 0x20)
        out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c)
            << std::dec << std::setfill(' ');
      else
        out << value[i];
      break;
    }
  }
  return out.str();
}

static std::string BstrToUtf8(const CATBSTR value)
{
  if (!value) return "";
  const int wide_length = static_cast<int>(SysStringLen(value));
  if (wide_length == 0) return "";
  const int byte_length = WideCharToMultiByte(CP_UTF8, 0, value, wide_length,
                                             0, 0, 0, 0);
  if (byte_length <= 0) return "";
  std::vector<char> buffer(static_cast<size_t>(byte_length));
  WideCharToMultiByte(CP_UTF8, 0, value, wide_length, &buffer[0], byte_length, 0, 0);
  return std::string(&buffer[0], static_cast<size_t>(byte_length));
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

static const char* CanonicalFromStartupType(const std::string& startup_type)
{
  if (startup_type == "Hole") return "hole";
  if (startup_type == "Pad") return "pad";
  if (startup_type == "Pocket") return "pocket";
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

static bool ReadLengthValue(CATIALength* length, double& value)
{
  return length && SUCCEEDED(length->get_Value(value));
}

static bool ReadAngleValue(CATIAAngle* angle, double& value)
{
  return angle && SUCCEEDED(angle->get_Value(value));
}

static bool VariantToDouble(const CATVariant& value, double& output)
{
  if (value.vt == VT_R8) { output = value.dblVal; return true; }
  if (value.vt == VT_R4) { output = static_cast<double>(value.fltVal); return true; }
  if (value.vt == VT_I4) { output = static_cast<double>(value.lVal); return true; }
  if (value.vt == VT_I2) { output = static_cast<double>(value.iVal); return true; }
  return false;
}

static bool ReadSafeArrayVector3(CATSafeArrayVariant* array, double output[3])
{
  CATVariant* values = 0;
  if (!array || FAILED(SafeArrayAccessData(array, reinterpret_cast<void**>(&values))) || !values)
    return false;
  bool valid = true;
  int index = 0;
  for (index = 0; index < 3; ++index)
  {
    if (!VariantToDouble(values[index], output[index]))
      valid = false;
  }
  SafeArrayUnaccessData(array);
  return valid;
}

static bool ReadHoleVector(CATIAHole* hole, bool origin, double output[3])
{
  if (!hole)
    return false;
  CATSafeArrayVariant* array = SafeArrayCreateVector(VT_VARIANT, 0, 3);
  if (!array)
    return false;
  HRESULT result = E_FAIL;
  try
  {
    result = origin ? hole->GetOrigin(*array) : hole->GetDirection(*array);
  }
  catch (...)
  {
    SafeArrayDestroy(array);
    return false;
  }
  const bool valid = SUCCEEDED(result) && ReadSafeArrayVector3(array, output);
  SafeArrayDestroy(array);
  return valid;
}

static bool ReadPrismDirection(CATIAPrism* prism, double output[3])
{
  if (!prism)
    return false;
  CATSafeArrayVariant* array = SafeArrayCreateVector(VT_VARIANT, 0, 3);
  if (!array)
    return false;
  HRESULT result = E_FAIL;
  try
  {
    result = prism->GetDirection(*array);
  }
  catch (...)
  {
    SafeArrayDestroy(array);
    return false;
  }
  const bool valid = SUCCEEDED(result) && ReadSafeArrayVector3(array, output);
  SafeArrayDestroy(array);
  return valid;
}

static std::string HoleTypeName(CatHoleType type, bool& known)
{
  known = true;
  if (type == catSimpleHole) return "simple";
  if (type == catTaperedHole) return "tapered";
  if (type == catCounterboredHole) return "counterbored";
  if (type == catCountersunkHole) return "countersunk";
  if (type == catCounterdrilledHole) return "counterdrilled";
  known = false;
  return "unknown";
}

static std::string LimitModeName(CatLimitMode mode, bool& known)
{
  known = true;
  if (mode == catOffsetLimit) return "offset";
  if (mode == catUpToNextLimit) return "up_to_next";
  if (mode == catUpToLastLimit) return "up_to_last";
  if (mode == catUpToPlaneLimit) return "up_to_plane";
  if (mode == catUpToSurfaceLimit) return "up_to_surface";
  if (mode == catUpThruNextLimit) return "up_thru_next";
  known = false;
  return "unknown";
}

static std::string PrismDirectionTypeName(CatPrismExtrusionDirection type, bool& known)
{
  known = true;
  if (type == catNormalToSketchDirection) return "normal_to_sketch";
  if (type == catNotNormalToSketchDirection) return "not_normal_to_sketch";
  known = false;
  return "unknown";
}

static std::string PrismOrientationName(CatPrismOrientation orientation, bool& known)
{
  known = true;
  if (orientation == catRegularOrientation) return "regular";
  if (orientation == catInverseOrientation) return "inverse";
  known = false;
  return "unknown";
}

static std::string OptionalNumberJson(bool available, double value)
{
  std::ostringstream out;
  if (available)
    out << std::setprecision(15) << value;
  else
    out << "null";
  return out.str();
}

static std::string OptionalStringJson(bool available, const std::string& value)
{
  if (!available)
    return "null";
  return "\"" + JsonEscape(value) + "\"";
}

static bool ReadLimit(CATIALimit* limit,
                      std::string& mode,
                      int& mode_raw,
                      bool& dimension_available,
                      double& dimension_mm,
                      std::string& dimension_status,
                      std::string& limiting_element_status)
{
  dimension_available = false;
  dimension_mm = 0.0;
  dimension_status = "unavailable";
  limiting_element_status = "not_attempted";
  mode = "unknown";
  mode_raw = -1;
  if (!limit)
    return false;
  CatLimitMode raw_mode = catOffsetLimit;
  if (FAILED(limit->get_LimitMode(raw_mode)))
    return false;
  bool known = false;
  mode_raw = static_cast<int>(raw_mode);
  mode = LimitModeName(raw_mode, known);
  if (!known)
    return true;
  if (raw_mode != catOffsetLimit)
  {
    dimension_status = "not_applicable";
    limiting_element_status = "supported_but_not_resolved_to_ir";
    return true;
  }
  CaaInterfaceGuard<CATIALength> dimension_guard;
  if (FAILED(limit->get_Dimension(dimension_guard.Out())) || !dimension_guard.Get())
    return false;
  if (!ReadLengthValue(dimension_guard.Get(), dimension_mm))
    return false;
  dimension_available = true;
  dimension_status = "success";
  limiting_element_status = "not_applicable";
  return true;
}

static std::string VectorJson(const double value[3])
{
  std::ostringstream out;
  out << "[" << std::setprecision(15) << value[0] << "," << value[1] << "," << value[2] << "]";
  return out.str();
}

static std::string LimitJson(const std::string& mode,
                             int mode_raw,
                             bool dimension_available,
                             double dimension_mm,
                             const std::string& dimension_status,
                             const std::string& limiting_element_status,
                             bool hole_depth_shape)
{
  std::ostringstream out;
  out << "{\"mode\":\"" << JsonEscape(mode) << "\",\"mode_raw\":" << mode_raw;
  if (hole_depth_shape)
  {
    out << ",\"depth_mm\":" << OptionalNumberJson(dimension_available, dimension_mm)
        << ",\"depth_status\":\"" << JsonEscape(dimension_status) << "\"}";
  }
  else
  {
    out << ",\"dimension_mm\":" << OptionalNumberJson(dimension_available, dimension_mm)
        << ",\"dimension_status\":\"" << JsonEscape(dimension_status)
        << "\",\"limiting_element_status\":\"" << JsonEscape(limiting_element_status) << "\"}";
  }
  return out.str();
}

static bool TryBuildHolePayload(CATISpecObject* spec,
                                CaaCapabilityBroker& broker,
                                ReconstructionPackage& package,
                                const ObjectEntity& object,
                                std::string& payload_json)
{
  payload_json.clear();
  CaaCapabilityLease lease;
  broker.Acquire<CATIAHole>(spec, IID_CATIAHole, "native_feature.CATIAHole",
                            object.object_id, package, lease);
  CATIAHole* hole = lease.As<CATIAHole>();
  if (!hole)
    return false;

  CatHoleType raw_type = catSimpleHole;
  CaaInterfaceGuard<CATIALength> diameter_guard;
  double diameter = 0.0;
  double origin[3] = { 0.0, 0.0, 0.0 };
  double direction[3] = { 0.0, 0.0, 0.0 };
  CaaInterfaceGuard<CATIALimit> bottom_limit_guard;
  if (FAILED(hole->get_Type(raw_type)) ||
      FAILED(hole->get_Diameter(diameter_guard.Out())) || !diameter_guard.Get() ||
      !ReadLengthValue(diameter_guard.Get(), diameter) ||
      !ReadHoleVector(hole, true, origin) ||
      !ReadHoleVector(hole, false, direction) ||
      FAILED(hole->get_BottomLimit(bottom_limit_guard.Out())) || !bottom_limit_guard.Get())
    return false;

  std::string limit_mode;
  int limit_mode_raw = -1;
  bool depth_available = false;
  double depth = 0.0;
  std::string depth_status;
  std::string limiting_element_status;
  if (!ReadLimit(bottom_limit_guard.Get(), limit_mode, limit_mode_raw, depth_available, depth,
                 depth_status, limiting_element_status))
    return false;

  bool known_type = false;
  const std::string hole_type = HoleTypeName(raw_type, known_type);

  std::string head_kind = "none";
  bool head_diameter_available = false;
  bool head_depth_available = false;
  bool head_angle_available = false;
  double head_diameter = 0.0;
  double head_depth = 0.0;
  double head_angle = 0.0;
  std::string head_diameter_status = "not_applicable";
  std::string head_depth_status = "not_applicable";
  std::string head_angle_status = "not_applicable";
  if (raw_type == catCounterboredHole || raw_type == catCounterdrilledHole)
  {
    CaaInterfaceGuard<CATIALength> head_diameter_guard;
    CaaInterfaceGuard<CATIALength> head_depth_guard;
    if (FAILED(hole->get_HeadDiameter(head_diameter_guard.Out())) || !head_diameter_guard.Get() ||
        !ReadLengthValue(head_diameter_guard.Get(), head_diameter) ||
        FAILED(hole->get_HeadDepth(head_depth_guard.Out())) || !head_depth_guard.Get() ||
        !ReadLengthValue(head_depth_guard.Get(), head_depth))
      return false;
    head_kind = raw_type == catCounterboredHole ? "counterbore" : "counterdrill";
    head_diameter_available = true;
    head_depth_available = true;
    head_diameter_status = "success";
    head_depth_status = "success";
  }
  if (raw_type == catTaperedHole || raw_type == catCounterdrilledHole ||
      raw_type == catCountersunkHole)
  {
    CaaInterfaceGuard<CATIAAngle> head_angle_guard;
    if (FAILED(hole->get_HeadAngle(head_angle_guard.Out())) || !head_angle_guard.Get() ||
        !ReadAngleValue(head_angle_guard.Get(), head_angle))
      return false;
    if (raw_type == catTaperedHole)
      head_kind = "taper";
    else if (raw_type == catCountersunkHole)
      head_kind = "countersink";
    head_angle_available = true;
    head_angle_status = "typed_caa_angle_value";
  }
  if (raw_type == catCountersunkHole)
  {
    CaaInterfaceGuard<CATIALength> head_depth_guard;
    if (FAILED(hole->get_HeadDepth(head_depth_guard.Out())) || !head_depth_guard.Get() ||
        !ReadLengthValue(head_depth_guard.Get(), head_depth))
      return false;
    head_depth_available = true;
    head_depth_status = "success";
  }

  CatHoleThreadingMode raw_threading_mode = catSmoothHoleThreading;
  if (FAILED(hole->get_ThreadingMode(raw_threading_mode)))
    return false;
  const bool thread_enabled = raw_threading_mode == catThreadedHoleThreading;
  const std::string thread_mode_status =
    (raw_threading_mode == catThreadedHoleThreading || raw_threading_mode == catSmoothHoleThreading) ?
    "success" : "unknown_enum";
  bool thread_description_available = false;
  bool thread_diameter_available = false;
  bool thread_depth_available = false;
  bool thread_pitch_available = false;
  std::string thread_description;
  double thread_diameter = 0.0;
  double thread_depth = 0.0;
  double thread_pitch = 0.0;
  std::string thread_description_status = thread_enabled ? "unavailable" : "not_applicable";
  std::string thread_diameter_status = thread_enabled ? "unavailable" : "not_applicable";
  std::string thread_depth_status = thread_enabled ? "unavailable" : "not_applicable";
  std::string thread_pitch_status = thread_enabled ? "unavailable" : "not_applicable";
  if (thread_enabled)
  {
    CaaInterfaceGuard<CATIALength> thread_diameter_guard;
    CaaInterfaceGuard<CATIALength> thread_depth_guard;
    CaaInterfaceGuard<CATIALength> thread_pitch_guard;
    CaaInterfaceGuard<CATIAStrParam> description_guard;
    if (FAILED(hole->get_ThreadDiameter(thread_diameter_guard.Out())) ||
        !thread_diameter_guard.Get() ||
        FAILED(hole->get_ThreadDepth(thread_depth_guard.Out())) ||
        !thread_depth_guard.Get() ||
        FAILED(hole->get_ThreadPitch(thread_pitch_guard.Out())) ||
        !thread_pitch_guard.Get() ||
        FAILED(hole->get_HoleThreadDescription(description_guard.Out())) ||
        !description_guard.Get())
      return false;
    if (!ReadLengthValue(thread_diameter_guard.Get(), thread_diameter) ||
        !ReadLengthValue(thread_depth_guard.Get(), thread_depth) ||
        !ReadLengthValue(thread_pitch_guard.Get(), thread_pitch))
      return false;
    CaaBstrGuard description;
    if (FAILED(description_guard.Get()->get_Value(description.Out())))
      return false;
    thread_description = BstrToUtf8(description.Get());
    thread_diameter_available = true;
    thread_depth_available = true;
    thread_pitch_available = true;
    thread_description_available = true;
    thread_diameter_status = "success";
    thread_depth_status = "success";
    thread_pitch_status = "success";
    thread_description_status = "success";
  }

  bool alias_available = false;
  std::string automation_alias;
  std::string automation_alias_status = "automation_alias_unavailable";
  CaaBstrGuard alias;
  if (SUCCEEDED(hole->get_Name(alias.Out())))
  {
    alias_available = true;
    automation_alias = BstrToUtf8(alias.Get());
    automation_alias_status = "success";
  }

  std::ostringstream out;
  out << "\"native_hole\":{\"semantic_kind\":\"part_design_hole\","
      << "\"value_source\":\"typed_caa_value\","
      << "\"interface_key\":\"CATIAHole\","
      << "\"hole_type\":\"" << JsonEscape(hole_type) << "\","
      << "\"hole_type_raw\":" << static_cast<int>(raw_type) << ","
      << "\"diameter_mm\":" << std::setprecision(15) << diameter << ","
      << "\"origin_mm\":" << VectorJson(origin) << ","
      << "\"direction\":" << VectorJson(direction) << ","
      << "\"bottom_limit\":" << LimitJson(limit_mode, limit_mode_raw, depth_available, depth,
                                           depth_status, limiting_element_status, true) << ","
      << "\"head\":{\"kind\":\"" << JsonEscape(head_kind)
      << "\",\"diameter_mm\":" << OptionalNumberJson(head_diameter_available, head_diameter)
      << ",\"diameter_status\":\"" << JsonEscape(head_diameter_status)
      << "\",\"depth_mm\":" << OptionalNumberJson(head_depth_available, head_depth)
      << ",\"depth_status\":\"" << JsonEscape(head_depth_status)
      << "\",\"angle_deg\":" << OptionalNumberJson(head_angle_available, head_angle)
      << ",\"angle_status\":\"" << JsonEscape(head_angle_status) << "\"},"
      << "\"thread\":{\"enabled\":" << (thread_enabled ? "true" : "false")
      << ",\"mode_raw\":" << static_cast<int>(raw_threading_mode)
      << ",\"description\":" << OptionalStringJson(thread_description_available, thread_description)
      << ",\"description_status\":\"" << JsonEscape(thread_description_status)
      << "\",\"diameter_mm\":" << OptionalNumberJson(thread_diameter_available, thread_diameter)
      << ",\"diameter_status\":\"" << JsonEscape(thread_diameter_status)
      << "\",\"depth_mm\":" << OptionalNumberJson(thread_depth_available, thread_depth)
      << ",\"depth_status\":\"" << JsonEscape(thread_depth_status)
      << "\",\"pitch_mm\":" << OptionalNumberJson(thread_pitch_available, thread_pitch)
      << ",\"pitch_status\":\"" << JsonEscape(thread_pitch_status) << "\"},"
      << "\"automation_alias\":" << OptionalStringJson(alias_available, automation_alias)
      << ",\"automation_alias_status\":\"" << JsonEscape(automation_alias_status) << "\","
      << "\"field_status\":{\"hole_type\":\"" << (known_type ? "success" : "unknown_enum")
      << "\",\"diameter_mm\":\"success\",\"origin_mm\":\"success\","
      << "\"direction\":\"success\",\"bottom_limit.mode\":\"success\","
      << "\"thread.mode\":\"" << JsonEscape(thread_mode_status) << "\"}}";
  payload_json = out.str();
  return true;
}

static bool TryBuildPrismPayload(CATISpecObject* spec,
                                 CaaCapabilityBroker& broker,
                                 ReconstructionPackage& package,
                                 const ObjectEntity& object,
                                 bool wants_pad,
                                 std::string& payload_json)
{
  payload_json.clear();
  CaaCapabilityLease feature_lease;
  if (wants_pad)
    broker.Acquire<CATIAPad>(spec, IID_CATIAPad, "native_feature.CATIAPad",
                             object.object_id, package, feature_lease);
  else
    broker.Acquire<CATIAPocket>(spec, IID_CATIAPocket, "native_feature.CATIAPocket",
                                object.object_id, package, feature_lease);
  CATBaseUnknown* feature = feature_lease.As<CATBaseUnknown>();
  if (!feature)
    return false;

  CATIAPrism* prism = 0;
  if (FAILED(feature->QueryInterface(IID_CATIAPrism, reinterpret_cast<void**>(&prism))) || !prism)
    return false;
  CaaInterfaceGuard<CATIAPrism> prism_guard(prism);

  CatPrismExtrusionDirection raw_direction_type = catNormalToSketchDirection;
  CatPrismOrientation raw_orientation = catRegularOrientation;
  double direction[3] = { 0.0, 0.0, 0.0 };
  CAT_VARIANT_BOOL value = FALSE;
  bool is_symmetric = false;
  bool is_thin = false;
  bool neutral_fiber = false;
  bool merge_end = false;
  std::string neutral_status = "success";
  std::string merge_status = "success";
  if (FAILED(prism_guard.Get()->get_DirectionType(raw_direction_type)) ||
      FAILED(prism_guard.Get()->get_DirectionOrientation(raw_orientation)) ||
      !ReadPrismDirection(prism_guard.Get(), direction) ||
      FAILED(prism_guard.Get()->get_IsSymmetric(value)))
    return false;
  is_symmetric = value != FALSE;
  if (FAILED(prism_guard.Get()->get_IsThin(value)))
    return false;
  is_thin = value != FALSE;
  if (FAILED(prism_guard.Get()->get_NeutralFiber(value)))
    neutral_status = "unavailable";
  else
    neutral_fiber = value != FALSE;
  if (FAILED(prism_guard.Get()->get_MergeEnd(value)))
    merge_status = "unavailable";
  else
    merge_end = value != FALSE;

  CaaInterfaceGuard<CATIALimit> first_limit_guard;
  CaaInterfaceGuard<CATIALimit> second_limit_guard;
  if (FAILED(prism_guard.Get()->get_FirstLimit(first_limit_guard.Out())) || !first_limit_guard.Get() ||
      FAILED(prism_guard.Get()->get_SecondLimit(second_limit_guard.Out())) || !second_limit_guard.Get())
    return false;

  std::string first_mode;
  int first_mode_raw = -1;
  bool first_dimension_available = false;
  double first_dimension = 0.0;
  std::string first_dimension_status;
  std::string first_limiting_element_status;
  std::string second_mode;
  int second_mode_raw = -1;
  bool second_dimension_available = false;
  double second_dimension = 0.0;
  std::string second_dimension_status;
  std::string second_limiting_element_status;
  if (!ReadLimit(first_limit_guard.Get(), first_mode, first_mode_raw, first_dimension_available,
                 first_dimension, first_dimension_status, first_limiting_element_status) ||
      !ReadLimit(second_limit_guard.Get(), second_mode, second_mode_raw, second_dimension_available,
                 second_dimension, second_dimension_status, second_limiting_element_status))
    return false;

  bool known_direction_type = false;
  bool known_orientation = false;
  const std::string direction_type = PrismDirectionTypeName(raw_direction_type, known_direction_type);
  const std::string orientation = PrismOrientationName(raw_orientation, known_orientation);

  std::ostringstream out;
  out << "\"native_prism\":{\"semantic_kind\":\"" << (wants_pad ? "part_design_pad" : "part_design_pocket") << "\","
      << "\"material_operation\":\"" << (wants_pad ? "add_material" : "remove_material") << "\","
      << "\"value_source\":\"typed_caa_value\","
      << "\"interface_key\":\"" << (wants_pad ? "CATIAPad" : "CATIAPocket") << "\","
      << "\"direction_type\":\"" << JsonEscape(direction_type) << "\","
      << "\"direction_type_raw\":" << static_cast<int>(raw_direction_type) << ","
      << "\"direction_orientation\":\"" << JsonEscape(orientation) << "\","
      << "\"direction_orientation_raw\":" << static_cast<int>(raw_orientation) << ","
      << "\"direction\":" << VectorJson(direction) << ","
      << "\"is_symmetric\":" << (is_symmetric ? "true" : "false") << ","
      << "\"is_thin\":" << (is_thin ? "true" : "false") << ","
      << "\"neutral_fiber\":" << (neutral_fiber ? "true" : "false") << ","
      << "\"merge_end\":" << (merge_end ? "true" : "false") << ","
      << "\"first_limit\":" << LimitJson(first_mode, first_mode_raw, first_dimension_available,
                                          first_dimension, first_dimension_status,
                                          first_limiting_element_status, false) << ","
      << "\"second_limit\":" << LimitJson(second_mode, second_mode_raw, second_dimension_available,
                                           second_dimension, second_dimension_status,
                                           second_limiting_element_status, false) << ","
      << "\"field_status\":{\"direction_type\":\"" << (known_direction_type ? "success" : "unknown_enum")
      << "\",\"direction_orientation\":\"" << (known_orientation ? "success" : "unknown_enum")
      << "\",\"direction\":\"success\",\"is_symmetric\":\"success\",\"is_thin\":\"success\","
      << "\"neutral_fiber\":\"" << neutral_status << "\",\"merge_end\":\"" << merge_status
      << "\",\"first_limit\":\"success\",\"second_limit\":\"success\"}}";
  payload_json = out.str();
  return true;
}

// 中文：以文档为采集边界生成语义特征，已完成的对象不会在根链路中重复输出。
static bool ExtractScoped(CaptureIdRegistry& ids,
                          CaaCapabilityBroker& broker,
                          ReconstructionPackage& package,
                          const std::string& document_id)
{
  size_t i;
  long type_only_count = 0;
  long generic_count = 0;
  std::set<std::string> completed_subjects;
  for (i = 0; i < package.semantic_facets.size(); ++i)
  {
    const SemanticFacet& existing = package.semantic_facets[i];
    if (existing.facet_kind == "native_feature_type" || existing.facet_kind == "opaque_native_object")
      completed_subjects.insert(existing.subject_id);
  }
  for (i = 0; i < package.objects.size(); ++i)
  {
    const ObjectEntity& object = package.objects[i];
    if ((!document_id.empty() && object.document_id != document_id) ||
        completed_subjects.find(object.object_id) != completed_subjects.end())
      continue;
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
      CATISpecObject* spec = FindNativeSpecObject(package, object.object_id);
      std::string payload_json;
      if (facet.canonical_family == "hole" &&
          TryBuildHolePayload(spec, broker, package, object, payload_json))
      {
        facet.decoder_id = "NativeHoleDecoder";
        facet.decode_level = "typed";
        facet.decode_status = "success";
        facet.payload_extraction_status = "available";
        facet.payload_json_property = payload_json;
      }
      else if ((facet.canonical_family == "pad" || facet.canonical_family == "pocket") &&
               TryBuildPrismPayload(spec, broker, package, object,
                                    facet.canonical_family == "pad", payload_json))
      {
        facet.decoder_id = facet.canonical_family == "pad" ? "NativePadDecoder" : "NativePocketDecoder";
        facet.decode_level = "typed";
        facet.decode_status = "success";
        facet.payload_extraction_status = "available";
        facet.payload_json_property = payload_json;
      }
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
                                               "Startup type canonical semantic facets emitted; Hole/Pad/Pocket typed payloads are attached when CATIA Public interfaces are available",
                                               "native_feature_extractors"));
  (void)type_only_count;
  (void)generic_count;
  return true;
}

// 中文：根链路补齐尚未采集的文档对象，保持原有公开接口兼容。
bool CaaNativeFeatureExtractors::Extract(CaptureIdRegistry& ids,
                                         CaaCapabilityBroker& broker,
                                         ReconstructionPackage& package)
{
  return ExtractScoped(ids, broker, package, "");
}

// 中文：在关联文档生命周期内完成指定文档的类型化解码。
bool CaaNativeFeatureExtractors::ExtractForDocument(CaptureIdRegistry& ids,
                                                     CaaCapabilityBroker& broker,
                                                     ReconstructionPackage& package,
                                                     const std::string& document_id)
{
  return ExtractScoped(ids, broker, package, document_id);
}

}
