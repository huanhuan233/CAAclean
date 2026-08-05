// 实现与 CATIA API 无关的注册、解码、通用兜底、不透明记录和 JSON 工具。
// 本文件只使用 C++03，可由核心测试程序在没有 CATIA 许可证时独立验证。
#include "CadParseContracts.h"

#include <algorithm>
#include <cerrno>
#include <cfloat>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <ctime>

namespace cadparse
{
// 用途：深复制普通字段和类型化载荷，避免多个记录共享同一可释放对象。
FeatureRecord::FeatureRecord(const FeatureRecord& other)
  : feature_id(other.feature_id), parent_id(other.parent_id),
    native_enumeration_index(other.native_enumeration_index),
    container_enumeration_index(other.container_enumeration_index),
    traversal_index(other.traversal_index), fingerprint(other.fingerprint),
    tree_path(other.tree_path), update_status(other.update_status),
    visibility(other.visibility), decoder_id(other.decoder_id),
    decoder_version(other.decoder_version), decode_level(other.decode_level),
    decode_status(other.decode_status), attributes(other.attributes),
    diagnostic_ids(other.diagnostic_ids), has_parameter(other.has_parameter),
    parameter(other.parameter),
    _typed_payload(other._typed_payload ? other._typed_payload->Clone() : 0)
{}

// 用途：释放本记录独占的类型化载荷。
FeatureRecord::~FeatureRecord()
{
  delete _typed_payload;
}

// 用途：复制全部纯数据字段，并通过 Clone 建立载荷深副本。
FeatureRecord& FeatureRecord::operator=(const FeatureRecord& other)
{
  if (this == &other) return *this;
  FeatureRecord temporary(other);
  std::swap(feature_id, temporary.feature_id);
  std::swap(parent_id, temporary.parent_id);
  std::swap(native_enumeration_index, temporary.native_enumeration_index);
  std::swap(container_enumeration_index, temporary.container_enumeration_index);
  std::swap(traversal_index, temporary.traversal_index);
  std::swap(fingerprint, temporary.fingerprint);
  std::swap(tree_path, temporary.tree_path);
  std::swap(update_status, temporary.update_status);
  std::swap(visibility, temporary.visibility);
  std::swap(decoder_id, temporary.decoder_id);
  std::swap(decoder_version, temporary.decoder_version);
  std::swap(decode_level, temporary.decode_level);
  std::swap(decode_status, temporary.decode_status);
  std::swap(attributes, temporary.attributes);
  std::swap(diagnostic_ids, temporary.diagnostic_ids);
  std::swap(has_parameter, temporary.has_parameter);
  std::swap(parameter, temporary.parameter);
  std::swap(_typed_payload, temporary._typed_payload);
  return *this;
}

// 用途：返回唯一静态地址作为原生孔能力类型令牌，不依赖 RTTI 或 CAA 指针。
const void* INativeHoleView::TypeToken()
{
  static const char token = 0;
  return &token;
}

// 用途：返回唯一静态地址作为原生 Prism 能力类型令牌，不依赖 RTTI 或 CAA 指针。
const void* INativePrismView::TypeToken()
{
  static const char token = 0;
  return &token;
}

// 用途：接管新载荷并释放旧载荷；相同指针不会重复释放。
void FeatureRecord::SetTypedPayload(ITypedPayload* payload)
{
  if (_typed_payload == payload) return;
  delete _typed_payload;
  _typed_payload = payload;
}

// 用途：清除类型化载荷，确保失败解码器的半成品不能污染通用结果。
void FeatureRecord::ClearTypedPayload()
{
  delete _typed_payload;
  _typed_payload = 0;
}

// 用途：把所有统计量初始化为零，防止未赋值数据进入覆盖率报告。
ParseStatistics::ParseStatistics()
  : enumerated_total(0), typed_count(0), generic_count(0), opaque_count(0), failed_count(0),
    container_count(0), relation_count(0), unknown_native_type_count(0),
    probe_supported_count(0), probe_unsupported_count(0), probe_exception_count(0),
    probe_not_attempted_count(0), not_up_to_date_count(0), parameter_total(0),
    parameter_value_success(0), parameter_value_partial(0), parameter_value_unavailable(0),
    parameter_failed(0), declared_business_feature_total(0), declared_boss_count(0),
    declared_hole_count(0), declared_slot_count(0), declared_unknown_count(0),
    business_feature_with_parameter_count(0), business_feature_with_all_values_count(0),
    business_feature_with_partial_values_count(0), business_feature_without_values_count(0),
    orphan_parameter_count(0), ambiguous_parameter_owner_count(0),
    native_hole_candidate_count(0), native_hole_success_count(0),
    native_hole_partial_count(0), native_hole_unsupported_count(0),
    native_hole_exception_count(0), document_open_ms(0),
    traversal_ms(0), decoder_ms(0), output_ms(0), total_ms(0)
{
}

// 用途：校验枚举对象总数等于类型化、通用、不透明和失败对象之和。
bool ParseStatistics::IsConserved() const
{
  return enumerated_total == typed_count + generic_count + opaque_count + failed_count;
}

// 用途：校验参数总数等于四种参数读取终态之和。
bool ParseStatistics::IsParameterConserved() const
{
  return parameter_total == parameter_value_success + parameter_value_partial +
    parameter_value_unavailable + parameter_failed;
}

// 用途：校验声明式业务特征总数等于各业务分类数量之和。
bool ParseStatistics::IsBusinessFeatureConserved() const
{
  return declared_business_feature_total == declared_boss_count + declared_hole_count +
    declared_slot_count + declared_unknown_count;
}

// 用途：确保每个原生孔候选恰好落入一个终态，防止接口异常被静默漏计。
bool ParseStatistics::IsNativeHoleConserved() const
{
  return native_hole_candidate_count == native_hole_success_count +
    native_hole_partial_count + native_hole_unsupported_count +
    native_hole_exception_count;
}

// 用途：按接口、原生类型、解码器和结果组成稳定键，累计探测覆盖率。
void ParseStatistics::RecordProbe(const std::string& interface_key,
                                  const std::string& native_type,
                                  const std::string& decoder_id,
                                  const std::string& result)
{
  if (result == "supported") ++probe_supported_count;
  else if (result == "unsupported") ++probe_unsupported_count;
  else if (result == "exception") ++probe_exception_count;
  else ++probe_not_attempted_count;

  const std::string key = interface_key + "\x1f" + native_type + "\x1f" +
    decoder_id + "\x1f" + result;
  ++probe_outcome_counts[key];
}

// 用途：创建诊断记录、分配稳定诊断编号并返回给特征记录引用。
// 诊断编号只依赖本轮写入顺序，不使用内存地址或进程句柄。
std::string ParseContext::AddDiagnostic(const char* severity, const char* stage, const char* code,
                                        const char* message, const std::string& feature_id)
{
  DiagnosticRecord diagnostic;
  std::ostringstream id;
  // 固定六位数字宽度，使诊断编号从 D000001 开始并保持可排序。
  id << "D" << std::setw(6) << std::setfill('0') << diagnostics.size() + 1;
  diagnostic.diagnostic_id = id.str();
  diagnostic.severity = severity ? severity : "error";
  diagnostic.stage = stage ? stage : "unknown";
  diagnostic.code = code ? code : "UNKNOWN";
  diagnostic.message = message ? message : "";
  diagnostic.feature_id = feature_id;
  diagnostics.push_back(diagnostic);
  return diagnostic.diagnostic_id;
}

// 用途：返回知识工程字符串参数解码器的稳定编号。
const char* KnowledgewareStringParameterDecoder::GetDecoderId() const
{
  return "KnowledgewareStringParameterDecoder";
}

// 用途：让字符串参数专用解码优先于通用兜底。
int KnowledgewareStringParameterDecoder::GetPriority() const
{
  return 800;
}

// 用途：根据原生类型或启动类型筛选字符串参数候选；接口确认在解码阶段完成。
bool KnowledgewareStringParameterDecoder::Match(const TypeFingerprint& fingerprint,
                                                const INativeObjectView&) const
{
  return fingerprint.native_type == "String" || fingerprint.startup_type == "String";
}

// 用途：读取字符串参数真实值；不支持或异常时记录诊断并交回通用兜底。
DecodeResult KnowledgewareStringParameterDecoder::Decode(const INativeObjectView& view,
                                                         ParseContext& context,
                                                         FeatureRecord& output)
{
  std::string basic_error;
  if (!view.ReadBasicAttributes(output, basic_error))
  {
    const std::string id = context.AddDiagnostic("warning", "parameter",
      "PARAM_BASIC_STATE_READ_FAILED", basic_error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(id);
  }
  const IStringParameterView* parameter_view = view.GetStringParameterView();
  if (!parameter_view)
  {
    context.statistics.RecordProbe("CATICkeParm", output.fingerprint.native_type,
                                   GetDecoderId(), "unsupported");
    const std::string id = context.AddDiagnostic("info", "parameter",
      "PARAM_INTERFACE_UNSUPPORTED", "object adapter has no String parameter view",
      output.feature_id);
    output.diagnostic_ids.push_back(id);
    return DecodeResult(false, "failed", "String parameter interface unsupported",
                        DecoderOutcomeUnsupported);
  }

  ParameterValueData parameter;
  std::string error;
  const StringParameterReadStatus status = parameter_view->ReadStringParameter(parameter, error);
  if (status != StringParameterReadSuccess)
  {
    const char* code = "PARAM_INTERFACE_UNSUPPORTED";
    const char* probe_result = "unsupported";
    if (status == StringParameterQueryException)
    {
      code = "PARAM_INTERFACE_QUERY_EXCEPTION";
      probe_result = "exception";
    }
    else if (status == StringParameterValueException)
    {
      code = "PARAM_VALUE_READ_EXCEPTION";
      probe_result = "supported";
    }
    context.statistics.RecordProbe("CATICkeParm", output.fingerprint.native_type,
                                   GetDecoderId(), probe_result);
    const std::string id = context.AddDiagnostic("warning", "parameter", code,
      error.empty() ? "String parameter read failed" : error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(id);
    DecoderOutcome outcome = DecoderOutcomeUnsupported;
    if (status == StringParameterQueryException) outcome = DecoderOutcomeException;
    else if (status == StringParameterValueException) outcome = DecoderOutcomePartial;
    return DecodeResult(false, "failed", error.empty() ? code : error.c_str(), outcome);
  }

  context.statistics.RecordProbe("CATICkeParm", output.fingerprint.native_type,
                                 GetDecoderId(), "supported");
  if (parameter.parameter_kind.empty()) parameter.parameter_kind = "string";
  if (parameter.parameter_name.empty())
    parameter.parameter_name = output.fingerprint.display_name;
  if (parameter.value_status.empty()) parameter.value_status = "success";
  if (parameter.value_source.empty()) parameter.value_source = "typed_caa_value";
  ParameterValueNormalizer::Normalize(parameter);
  output.has_parameter = true;
  output.parameter = parameter;
  output.decoder_id = GetDecoderId();
  output.decoder_version = "1.0.0";
  output.decode_level = "typed";
  output.decode_status = "success";
  return DecodeResult(true, "typed");
}

// 用途：返回原生孔解码器的稳定注册编号。
const char* NativeHoleDecoder::GetDecoderId() const { return "NativeHoleDecoder"; }

// 用途：让真实原生孔在通用基础解码器之前参与确定性选择。
int NativeHoleDecoder::GetPriority() const { return 900; }

// 用途：标识该解码器属于零件设计特征家族，供诊断和扩展注册使用。
const char* NativeHoleDecoder::GetFeatureFamily() const { return "part_design"; }

// 用途：仅以启动类型为 Hole 做低成本预筛选，不在此处宣称对象已经是孔。
DecoderMatchStatus NativeHoleDecoder::GetMatchStatus(const TypeFingerprint& fingerprint,
                                                      const INativeObjectView&) const
{
  return fingerprint.startup_type == "Hole" ? DecoderCandidate : DecoderNotCandidate;
}

// 用途：把注册中心的布尔匹配契约转换为显式候选状态。
bool NativeHoleDecoder::Match(const TypeFingerprint& fingerprint,
                              const INativeObjectView& view) const
{
  return GetMatchStatus(fingerprint, view) == DecoderCandidate;
}

namespace
{
// 用途：以 C++03 可用方式拒绝非数和无穷值，防止无效坐标进入 JSON。
bool IsFiniteNativeHoleNumber(double value)
{
  return value == value && value <= DBL_MAX && value >= -DBL_MAX;
}
}

// 用途：通过 API 无关原生孔视图确认专用接口并建立类型化载荷；失败交回通用兜底。
DecodeResult NativeHoleDecoder::Decode(const INativeObjectView& view,
                                       ParseContext& context,
                                       FeatureRecord& output)
{
  ++context.statistics.native_hole_candidate_count;
  std::string basic_error;
  bool basic_read = false;
  try { basic_read = view.ReadBasicAttributes(output, basic_error); }
  catch (...) { basic_error = "basic state view raised an exception"; }
  if (!basic_read)
  {
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_hole", "NATIVE_HOLE_BASIC_STATE_READ_FAILED",
      basic_error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
  }
  const INativeCapabilityView* capability = 0;
  try { capability = view.FindCapability("NativeHole"); }
  catch (...)
  {
    ++context.statistics.native_hole_exception_count;
    context.statistics.RecordProbe("CATIAHole", output.fingerprint.native_type,
                                   GetDecoderId(), "exception");
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_hole", "NATIVE_HOLE_INTERFACE_QUERY_EXCEPTION",
      "FindCapability(NativeHole) raised an exception", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_HOLE_INTERFACE_QUERY_EXCEPTION",
                        DecoderOutcomeException);
  }
  if (!capability || std::string(capability->GetCapabilityId()) != "NativeHole")
  {
    ++context.statistics.native_hole_unsupported_count;
    context.statistics.RecordProbe("CATIAHole", output.fingerprint.native_type,
                                   GetDecoderId(), "unsupported");
    return DecodeResult(false, "failed", "NATIVE_HOLE_INTERFACE_UNSUPPORTED",
                        DecoderOutcomeUnsupported);
  }
  if (capability->GetCapabilityTypeToken() != INativeHoleView::TypeToken())
  {
    ++context.statistics.native_hole_exception_count;
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_hole", "NATIVE_HOLE_CAPABILITY_TYPE_MISMATCH",
      "NativeHole capability type token mismatch", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_HOLE_CAPABILITY_TYPE_MISMATCH",
                        DecoderOutcomeException);
  }
  // 能力编号与强类型令牌均已确认，可以安全转换到原生孔视图。
  const INativeHoleView* hole_view = static_cast<const INativeHoleView*>(capability);

  NativeHoleData data;
  std::string error;
  NativeHoleReadStatus status = NativeHoleInterfaceQueryException;
  try { status = hole_view->ReadNativeHole(data, error); }
  catch (...) { error = "Native Hole view read raised an exception"; }
  if (status != NativeHoleReadSuccess)
  {
    const char* code = "NATIVE_HOLE_INTERFACE_UNSUPPORTED";
    const char* probe_result = "unsupported";
    if (status == NativeHoleInterfaceQueryException)
    {
      code = "NATIVE_HOLE_INTERFACE_QUERY_EXCEPTION";
      probe_result = "exception";
      ++context.statistics.native_hole_exception_count;
    }
    else if (status == NativeHoleRequiredValueReadException)
    {
      code = "NATIVE_HOLE_REQUIRED_VALUE_READ_EXCEPTION";
      probe_result = "supported";
      ++context.statistics.native_hole_partial_count;
    }
    else
      ++context.statistics.native_hole_unsupported_count;

    context.statistics.RecordProbe("CATIAHole", output.fingerprint.native_type,
                                   GetDecoderId(), probe_result);
    const std::string diagnostic_id = context.AddDiagnostic(
      status == NativeHoleInterfaceUnsupported ? "info" : "warning",
      "native_hole", code, error.empty() ? code : error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    DecoderOutcome outcome = DecoderOutcomeUnsupported;
    if (status == NativeHoleInterfaceQueryException) outcome = DecoderOutcomeException;
    else if (status == NativeHoleRequiredValueReadException) outcome = DecoderOutcomePartial;
    return DecodeResult(false, "failed", code, outcome);
  }

  context.statistics.RecordProbe("CATIAHole", output.fingerprint.native_type,
                                 GetDecoderId(), "supported");
  if (!IsFiniteNativeHoleNumber(data.diameter_mm) || data.diameter_mm <= 0.0)
  {
    ++context.statistics.native_hole_partial_count;
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_hole", "NATIVE_HOLE_VALUE_NONFINITE",
      "required Hole diameter is invalid", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_HOLE_VALUE_NONFINITE",
                        DecoderOutcomePartial);
  }
  int axis = 0;
  double direction_norm_squared = 0.0;
  for (axis = 0; axis < 3; ++axis)
  {
    if (!IsFiniteNativeHoleNumber(data.origin_mm[axis]) ||
        !IsFiniteNativeHoleNumber(data.direction[axis]))
    {
      ++context.statistics.native_hole_partial_count;
      const std::string diagnostic_id = context.AddDiagnostic(
        "warning", "native_hole", "NATIVE_HOLE_VALUE_NONFINITE",
        "Hole origin or direction is non-finite", output.feature_id);
      output.diagnostic_ids.push_back(diagnostic_id);
      return DecodeResult(false, "failed", "NATIVE_HOLE_VALUE_NONFINITE",
                          DecoderOutcomePartial);
    }
    direction_norm_squared += data.direction[axis] * data.direction[axis];
  }
  if (direction_norm_squared < 1.0e-16)
  {
    ++context.statistics.native_hole_partial_count;
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_hole", "NATIVE_HOLE_DIRECTION_INVALID",
      "Hole direction has zero length", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_HOLE_DIRECTION_INVALID",
                        DecoderOutcomePartial);
  }

  const OptionalNativeHoleNumber* optional_numbers[] = {
    &data.bottom_limit.depth_mm,
    &data.head.diameter_mm,
    &data.head.depth_mm,
    &data.head.angle_deg,
    &data.thread.diameter_mm,
    &data.thread.depth_mm,
    &data.thread.pitch_mm
  };
  int optional_index = 0;
  for (optional_index = 0; optional_index < 7; ++optional_index)
  {
    if (optional_numbers[optional_index]->has_value &&
        !IsFiniteNativeHoleNumber(optional_numbers[optional_index]->value))
    {
      ++context.statistics.native_hole_partial_count;
      const std::string diagnostic_id = context.AddDiagnostic(
        "warning", "native_hole", "NATIVE_HOLE_VALUE_NONFINITE",
        "optional Hole numeric value is non-finite", output.feature_id);
      output.diagnostic_ids.push_back(diagnostic_id);
      return DecodeResult(false, "failed", "NATIVE_HOLE_VALUE_NONFINITE",
                          DecoderOutcomePartial);
    }
  }

  if (data.field_status["hole_type"] == "unknown_enum" ||
      data.field_status["bottom_limit.mode"] == "unknown_enum" ||
      data.field_status["thread.mode"] == "unknown_enum")
  {
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_hole", "NATIVE_HOLE_ENUM_UNKNOWN",
      "unknown R21 Hole enum preserved as raw value", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
  }

  ++context.statistics.native_hole_success_count;
  output.SetTypedPayload(new NativeHolePayload(data));
  output.decoder_id = GetDecoderId();
  output.decoder_version = "1.0.0";
  output.decode_level = "typed";
  output.decode_status = "success";
  return DecodeResult(true, "typed");
}

namespace
{
// 用途：用同一套确认链读取 Pad/Pocket Prism 参数，具体能力由 capability_id 决定。
DecodeResult DecodeNativePrismFeature(const INativeObjectView& view,
                                      ParseContext& context,
                                      FeatureRecord& output,
                                      const char* capability_id,
                                      const char* interface_key,
                                      const char* decoder_id)
{
  std::string basic_error;
  bool basic_read = false;
  try { basic_read = view.ReadBasicAttributes(output, basic_error); }
  catch (...) { basic_error = "basic state view raised an exception"; }
  if (!basic_read)
  {
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_prism", "NATIVE_PRISM_BASIC_STATE_READ_FAILED",
      basic_error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
  }

  const INativeCapabilityView* capability = 0;
  try { capability = view.FindCapability(capability_id); }
  catch (...)
  {
    context.statistics.RecordProbe(interface_key, output.fingerprint.native_type,
                                   decoder_id, "exception");
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_prism", "NATIVE_PRISM_INTERFACE_QUERY_EXCEPTION",
      "FindCapability(NativePad/NativePocket) raised an exception", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_PRISM_INTERFACE_QUERY_EXCEPTION",
                        DecoderOutcomeException);
  }
  if (!capability || std::string(capability->GetCapabilityId()) != capability_id)
  {
    context.statistics.RecordProbe(interface_key, output.fingerprint.native_type,
                                   decoder_id, "unsupported");
    return DecodeResult(false, "failed", "NATIVE_PRISM_INTERFACE_UNSUPPORTED",
                        DecoderOutcomeUnsupported);
  }
  if (capability->GetCapabilityTypeToken() != INativePrismView::TypeToken())
  {
    context.statistics.RecordProbe(interface_key, output.fingerprint.native_type,
                                   decoder_id, "exception");
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_prism", "NATIVE_PRISM_CAPABILITY_TYPE_MISMATCH",
      "Native Prism capability type token mismatch", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_PRISM_CAPABILITY_TYPE_MISMATCH",
                        DecoderOutcomeException);
  }

  const INativePrismView* prism_view = static_cast<const INativePrismView*>(capability);
  NativePrismData data;
  std::string error;
  NativePrismReadStatus status = NativePrismInterfaceQueryException;
  try { status = prism_view->ReadNativePrism(capability_id, data, error); }
  catch (...) { error = "Native Prism view read raised an exception"; }
  if (status != NativePrismReadSuccess)
  {
    const char* code = "NATIVE_PRISM_INTERFACE_UNSUPPORTED";
    const char* probe_result = "unsupported";
    DecoderOutcome outcome = DecoderOutcomeUnsupported;
    if (status == NativePrismInterfaceQueryException)
    {
      code = "NATIVE_PRISM_INTERFACE_QUERY_EXCEPTION";
      probe_result = "exception";
      outcome = DecoderOutcomeException;
    }
    else if (status == NativePrismRequiredValueReadException)
    {
      code = "NATIVE_PRISM_REQUIRED_VALUE_READ_EXCEPTION";
      probe_result = "supported";
      outcome = DecoderOutcomePartial;
    }
    context.statistics.RecordProbe(interface_key, output.fingerprint.native_type,
                                   decoder_id, probe_result);
    const std::string diagnostic_id = context.AddDiagnostic(
      status == NativePrismInterfaceUnsupported ? "info" : "warning",
      "native_prism", code, error.empty() ? code : error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", code, outcome);
  }

  int axis = 0;
  double direction_norm_squared = 0.0;
  for (axis = 0; axis < 3; ++axis)
  {
    if (!IsFiniteNativeHoleNumber(data.direction[axis]))
    {
      const std::string diagnostic_id = context.AddDiagnostic(
        "warning", "native_prism", "NATIVE_PRISM_DIRECTION_INVALID",
        "Prism direction is non-finite", output.feature_id);
      output.diagnostic_ids.push_back(diagnostic_id);
      return DecodeResult(false, "failed", "NATIVE_PRISM_DIRECTION_INVALID",
                          DecoderOutcomePartial);
    }
    direction_norm_squared += data.direction[axis] * data.direction[axis];
  }
  if (direction_norm_squared < 1.0e-16)
  {
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_prism", "NATIVE_PRISM_DIRECTION_INVALID",
      "Prism direction vector is zero length", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_PRISM_DIRECTION_INVALID",
                        DecoderOutcomePartial);
  }
  if ((data.first_limit.dimension_mm.has_value &&
       !IsFiniteNativeHoleNumber(data.first_limit.dimension_mm.value)) ||
      (data.second_limit.dimension_mm.has_value &&
       !IsFiniteNativeHoleNumber(data.second_limit.dimension_mm.value)))
  {
    const std::string diagnostic_id = context.AddDiagnostic(
      "warning", "native_prism", "NATIVE_PRISM_VALUE_NONFINITE",
      "Prism limit dimension is non-finite", output.feature_id);
    output.diagnostic_ids.push_back(diagnostic_id);
    return DecodeResult(false, "failed", "NATIVE_PRISM_VALUE_NONFINITE",
                        DecoderOutcomePartial);
  }

  context.statistics.RecordProbe(interface_key, output.fingerprint.native_type,
                                 decoder_id, "supported");
  output.SetTypedPayload(new NativePrismPayload(data));
  output.decoder_id = decoder_id;
  output.decoder_version = "1.0.0";
  output.decode_level = "typed";
  output.decode_status = "success";
  return DecodeResult(true, "typed");
}
}

// 用途：返回原生 Pad 解码器的稳定注册编号。
const char* NativePadDecoder::GetDecoderId() const { return "NativePadDecoder"; }
// 用途：让 Pad 在通用基础解码器之前参与选择，同时低于 Hole 的专用优先级。
int NativePadDecoder::GetPriority() const { return 880; }
// 用途：标识该解码器属于零件设计特征家族。
const char* NativePadDecoder::GetFeatureFamily() const { return "part_design"; }
// 用途：仅以 StartUp 文本做候选预筛选，真正确认必须依赖 CATIAPad 接口。
DecoderMatchStatus NativePadDecoder::GetMatchStatus(const TypeFingerprint& fingerprint,
                                                     const INativeObjectView&) const
{
  return fingerprint.startup_type == "Pad" ? DecoderCandidate : DecoderNotCandidate;
}
// 用途：把显式候选状态转换为旧布尔匹配契约。
bool NativePadDecoder::Match(const TypeFingerprint& fingerprint,
                             const INativeObjectView& view) const
{
  return GetMatchStatus(fingerprint, view) == DecoderCandidate;
}
// 用途：通过 NativePad 能力读取 CATIAPad/CATIAPrism 真实参数，失败后允许通用兜底。
DecodeResult NativePadDecoder::Decode(const INativeObjectView& view, ParseContext& context,
                                      FeatureRecord& output)
{
  return DecodeNativePrismFeature(view, context, output, "NativePad", "CATIAPad",
                                  GetDecoderId());
}

// 用途：返回原生 Pocket 解码器的稳定注册编号。
const char* NativePocketDecoder::GetDecoderId() const { return "NativePocketDecoder"; }
// 用途：让 Pocket 在通用基础解码器之前参与选择，同时低于 Hole 的专用优先级。
int NativePocketDecoder::GetPriority() const { return 880; }
// 用途：标识该解码器属于零件设计特征家族。
const char* NativePocketDecoder::GetFeatureFamily() const { return "part_design"; }
// 用途：仅以 StartUp 文本做候选预筛选，真正确认必须依赖 CATIAPocket 接口。
DecoderMatchStatus NativePocketDecoder::GetMatchStatus(const TypeFingerprint& fingerprint,
                                                        const INativeObjectView&) const
{
  return fingerprint.startup_type == "Pocket" ? DecoderCandidate : DecoderNotCandidate;
}
// 用途：把显式候选状态转换为旧布尔匹配契约。
bool NativePocketDecoder::Match(const TypeFingerprint& fingerprint,
                                const INativeObjectView& view) const
{
  return GetMatchStatus(fingerprint, view) == DecoderCandidate;
}
// 用途：通过 NativePocket 能力读取 CATIAPocket/CATIAPrism 真实参数，失败后允许通用兜底。
DecodeResult NativePocketDecoder::Decode(const INativeObjectView& view, ParseContext& context,
                                         FeatureRecord& output)
{
  return DecodeNativePrismFeature(view, context, output, "NativePocket", "CATIAPocket",
                                  GetDecoderId());
}

static const char* CanonicalFromStartupType(const std::string& startup_type)
{
  if (startup_type == "EdgeFillet") return "fillet";
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

const char* StartupTypeCanonicalDecoder::GetDecoderId() const
{
  return "StartupTypeCanonicalDecoder";
}

int StartupTypeCanonicalDecoder::GetPriority() const { return 100; }

bool StartupTypeCanonicalDecoder::Match(const TypeFingerprint& fingerprint,
                                        const INativeObjectView&) const
{
  return CanonicalFromStartupType(fingerprint.startup_type)[0] != '\0';
}

DecodeResult StartupTypeCanonicalDecoder::Decode(const INativeObjectView& view,
                                                 ParseContext&,
                                                 FeatureRecord& output)
{
  std::string error;
  if (!view.ReadBasicAttributes(output, error))
    return DecodeResult(false, "opaque", error.c_str());
  const char* canonical = CanonicalFromStartupType(output.fingerprint.startup_type);
  if (!canonical[0])
    return DecodeResult(false, "typed", "startup type is not in canonical map",
                        DecoderOutcomeUnsupported);
  output.attributes["canonical_native_type"] = canonical;
  output.decoder_id = GetDecoderId();
  output.decode_level = "typed";
  output.decode_status = "success";
  return DecodeResult(true, "typed");
}

// 用途：返回通用解码器的稳定编号，供结果和统计追溯。
const char* GenericFeatureDecoder::GetDecoderId() const { return "generic"; }
// 用途：把通用解码器放在所有专用解码器之后。
int GenericFeatureDecoder::GetPriority() const { return -1000; }
// 用途：接受所有未被专用解码器接管的对象。
bool GenericFeatureDecoder::Match(const TypeFingerprint&, const INativeObjectView&) const { return true; }

// 用途：读取基础属性，并把成功对象标记为通用解码成功。
// 基础读取失败时保留 error，供注册中心转入不透明对象记录器。
DecodeResult GenericFeatureDecoder::Decode(const INativeObjectView& view, ParseContext& context,
                                           FeatureRecord& output)
{
  std::string error;
  if (!view.ReadBasicAttributes(output, error))
  {
    const std::string id = context.AddDiagnostic("warning", "generic", "GENERIC_READ_FAILED",
                                                 error.c_str(), output.feature_id);
    output.diagnostic_ids.push_back(id);
    return DecodeResult(false, "opaque", error.c_str());
  }
  output.decoder_id = GetDecoderId();
  output.decode_level = "generic";
  output.decode_status = "success";
  return DecodeResult(true, "generic");
}

// 用途：在任何属性都无法读取时，仍为对象建立最小中间表示记录。
// 失败阶段和原因写入诊断，确保单个对象问题不会终止整份文档。
DecodeResult OpaqueObjectRecorder::Record(const INativeObjectView& view, ParseContext& context,
                                          FeatureRecord& output, const std::string& stage,
                                          const std::string& reason)
{
  output.fingerprint = view.GetFingerprint();
  output.decoder_id = "opaque";
  output.decode_level = "opaque";
  output.decode_status = "recorded";
  output.attributes["failure_stage"] = stage;
  output.attributes["error_code"] = "OPAQUE_OBJECT";
  output.attributes["error_description"] = reason;
  const std::string id = context.AddDiagnostic("warning", stage.c_str(), "OPAQUE_OBJECT",
                                               reason.c_str(), output.feature_id);
  output.diagnostic_ids.push_back(id);
  return DecodeResult(true, "opaque", reason.c_str());
}

// 用途：把非空解码器加入注册表；注册表不接管其内存所有权。
void DecoderRegistry::Register(IFeatureDecoder* decoder)
{
  if (decoder)
    _decoders.push_back(decoder);
}

// 用途：把指纹字段连接成稳定目录键，用于类型统计和可复现比较。
// 使用不可见分隔字符降低普通类型文本与字段边界发生碰撞的可能。
std::string FeatureTypeFingerprintBuilder::StableKey(const TypeFingerprint& fingerprint)
{
  std::ostringstream key;
  key << fingerprint.native_type << '\x1f' << fingerprint.startup_type << '\x1f'
      << fingerprint.container_kind << '\x1f' << fingerprint.internal_name << '\x1f'
      << fingerprint.display_name;
  // C++03 不支持范围循环，因此使用常量迭代器遍历父类型和接口键。
  std::vector<std::string>::const_iterator super_type = fingerprint.super_types.begin();
  for (; super_type != fingerprint.super_types.end(); ++super_type) key << '\x1f' << *super_type;
  std::vector<std::string>::const_iterator interface_key =
    fingerprint.supported_interface_keys.begin();
  for (; interface_key != fingerprint.supported_interface_keys.end(); ++interface_key)
    key << '\x1f' << *interface_key;
  return key.str();
}

// 用途：以集合记录稳定指纹键，并自动去除重复类型。
void FeatureTypeCatalog::Observe(const TypeFingerprint& fingerprint)
{
  _keys.insert(FeatureTypeFingerprintBuilder::StableKey(fingerprint));
}

// 用途：返回当前目录中不同稳定指纹的数量。
size_t FeatureTypeCatalog::Count() const { return _keys.size(); }

// 用途：以优先级和稳定解码器编号决定哪个候选更优。
// 优先级更高者获胜；同优先级时编号字典序更小者获胜。
bool DecoderMatchEngine::IsBetter(const IFeatureDecoder* candidate,
                                  const IFeatureDecoder* current)
{
  return candidate && (!current || candidate->GetPriority() > current->GetPriority() ||
    (candidate->GetPriority() == current->GetPriority() &&
     std::string(candidate->GetDecoderId()) < current->GetDecoderId()));
}

// 用途：将已确认支持的接口键加入指纹，避免重复插入。
void UnknownTypeCollector::Observe(const TypeFingerprint& fingerprint)
{
  if (!fingerprint.native_type.empty()) return;
  const std::string key = fingerprint.startup_type.empty() ? "<unavailable>" : fingerprint.startup_type;
  _unknown_types.insert(key);
}

// 用途：记录最终未识别对象的原生类型。
size_t UnknownTypeCollector::Count() const { return _unknown_types.size(); }

// 用途：执行全部守恒校验，任一失败都使覆盖率校验失败。
bool CoverageTracker::Validate(const ParseStatistics& statistics)
{
  return statistics.IsConserved() && statistics.IsParameterConserved() &&
    statistics.IsBusinessFeatureConserved() && statistics.IsNativeHoleConserved();
}

namespace
{
// 用途：为候选解码器建立确定顺序，优先级降序且稳定编号升序。
bool DecoderOrder(const IFeatureDecoder* left, const IFeatureDecoder* right)
{
  if (left->GetPriority() != right->GetPriority())
    return left->GetPriority() > right->GetPriority();
  return std::string(left->GetDecoderId()) < right->GetDecoderId();
}

// 用途：把解码终态转换成稳定统计键文本。
const char* DecoderOutcomeName(DecoderOutcome outcome)
{
  switch (outcome)
  {
  case DecoderOutcomeNotMatched: return "not_matched";
  case DecoderOutcomeUnsupported: return "unsupported";
  case DecoderOutcomeSuccess: return "success";
  case DecoderOutcomePartial: return "partial";
  case DecoderOutcomeException: return "exception";
  case DecoderOutcomeRejected: return "rejected";
  case DecoderOutcomeConflict: return "conflict";
  }
  return "rejected";
}

// 用途：按解码器编号和终态累计通用统计，兼容任意后续专用特征。
void RecordDecoderOutcome(ParseContext& context, const IFeatureDecoder* decoder,
                          DecoderOutcome outcome)
{
  const std::string key = std::string(decoder->GetDecoderId()) + "\x1f" +
    DecoderOutcomeName(outcome);
  ++context.statistics.decoder_outcome_counts[key];
}
}

// 用途：遍历注册解码器并按确定顺序返回候选，匹配异常只影响当前解码器。
void DecoderRegistry::FindCandidates(const TypeFingerprint& fingerprint,
                                     const INativeObjectView& view,
                                     ParseContext& context,
                                     std::vector<IFeatureDecoder*>& candidates) const
{
  candidates.clear();
  std::vector<IFeatureDecoder*>::const_iterator it = _decoders.begin();
  for (; it != _decoders.end(); ++it)
  {
    IFeatureDecoder* candidate = *it;
    bool matched = false;
    try
    {
      matched = candidate->Match(fingerprint, view);
    }
    catch (...)
    {
      context.AddDiagnostic("warning", "registry", "DECODER_MATCH_EXCEPTION",
                            candidate->GetDecoderId(), "");
      RecordDecoderOutcome(context, candidate, DecoderOutcomeException);
      continue;
    }
    if (!matched)
    {
      RecordDecoderOutcome(context, candidate, DecoderOutcomeNotMatched);
      continue;
    }
    candidates.push_back(candidate);
  }
  std::sort(candidates.begin(), candidates.end(), DecoderOrder);
}

// 用途：构造特征类型注册中心并绑定通用与不透明兜底实现。
FeatureTypeRegistry::FeatureTypeRegistry() {}

// 用途：把专用解码器转交内部解码器注册表。
void FeatureTypeRegistry::Register(IFeatureDecoder* decoder)
{
  _registry.Register(decoder);
}

// 用途：为单个对象建立基础记录、选择专用解码器，并执行统一回退流程。
// 无论专用解码是否成功，最终都保证输出一条可追溯的对象记录。
DecodeResult FeatureTypeRegistry::DecodeObject(const INativeObjectView& view, ParseContext& context,
                                               FeatureRecord& output)
{
  const clock_t decode_start = clock();
  output.fingerprint = view.GetFingerprint();
  // 特征编号由爬取层预先分配；解码器不得改写编号和树位置信息。
  const FeatureRecord fallback_base = output;
  std::vector<IFeatureDecoder*> candidates;
  _registry.FindCandidates(output.fingerprint, view, context, candidates);
  IFeatureDecoder* decoder = 0;
  DecodeResult result(false, "failed", "no typed decoder");
  std::vector<std::string> failure_diagnostic_ids;
  size_t candidate_index = 0;
  for (; candidate_index < candidates.size(); ++candidate_index)
  {
    IFeatureDecoder* candidate = candidates[candidate_index];
    FeatureRecord attempt = fallback_base;
    DecodeResult attempt_result(false, "failed", "decoder not executed");
    try
    {
      attempt_result = candidate->Decode(view, context, attempt);
    }
    catch (...)
    {
      const std::string id = context.AddDiagnostic("warning", "decoder", "DECODER_EXCEPTION",
                                                   candidate->GetDecoderId(), output.feature_id);
      failure_diagnostic_ids.push_back(id);
      attempt_result = DecodeResult(false, "failed", "typed decoder exception",
                                    DecoderOutcomeException);
    }
    RecordDecoderOutcome(context, candidate, attempt_result.outcome);
    if (attempt_result.success)
    {
      decoder = candidate;
      output = attempt;
      result = attempt_result;
      // 只执行同优先级剩余候选来检测真实双成功；低优先级候选在成功后停止。
      size_t peer_index = candidate_index + 1;
      for (; peer_index < candidates.size() &&
             candidates[peer_index]->GetPriority() == candidate->GetPriority(); ++peer_index)
      {
        FeatureRecord peer_attempt = fallback_base;
        DecodeResult peer_result(false, "failed", "peer decoder not executed");
        try { peer_result = candidates[peer_index]->Decode(view, context, peer_attempt); }
        catch (...) { peer_result = DecodeResult(false, "failed", "peer decoder exception",
                                                  DecoderOutcomeException); }
        RecordDecoderOutcome(context, candidates[peer_index], peer_result.outcome);
        if (peer_result.success)
        {
          const std::string id = context.AddDiagnostic(
            "warning", "registry", "DECODER_SUCCESS_CONFLICT",
            "multiple equal-priority decoders succeeded; stable decoder id retained",
            output.feature_id);
          output.diagnostic_ids.push_back(id);
          RecordDecoderOutcome(context, candidates[peer_index], DecoderOutcomeConflict);
        }
      }
      break;
    }
    failure_diagnostic_ids.insert(failure_diagnostic_ids.end(),
                                  attempt.diagnostic_ids.begin(), attempt.diagnostic_ids.end());
    if (attempt_result.message != "typed decoder exception" &&
        attempt_result.outcome != DecoderOutcomeUnsupported)
    {
      const std::string id = context.AddDiagnostic("warning", "decoder", "DECODER_FAILED",
                                                   attempt_result.message.c_str(), output.feature_id);
      failure_diagnostic_ids.push_back(id);
    }
    // Unsupported 是正常能力缺失，Registry 必须自动续试；其他失败遵循 Decoder 策略。
    if (attempt_result.outcome != DecoderOutcomeUnsupported &&
        !candidate->ContinueTypedAfterFailure()) break;
  }

  if (!decoder)
  {
    output = fallback_base;
    output.diagnostic_ids = failure_diagnostic_ids;
    result = _generic.Decode(view, context, output);
  }

  if (!result.success)
    // 通用解码失败时由不透明记录器保留对象存在性和失败原因。
    result = _opaque.Record(view, context, output, "generic",
                            result.message.empty() ? "generic fallback unavailable" : result.message);

  // 字符串参数候选即使读取失败，也保留参数索引所需的不可用状态。
  if (!output.has_parameter &&
      (output.fingerprint.native_type == "String" || output.fingerprint.startup_type == "String"))
  {
    output.has_parameter = true;
    output.parameter.parameter_kind = "string";
    output.parameter.parameter_name = output.fingerprint.display_name;
    output.parameter.value_status = "inaccessible";
    output.parameter.value_source = "unavailable";
    output.parameter.normalization_status = "not_attempted";
    output.parameter.is_read_only = "unknown";
    output.parameter.is_hidden = "unknown";
  }

  // 根据最终解码级别只累计一次对象统计，保证对象守恒。
  ++context.statistics.enumerated_total;
  ++context.statistics.decoder_hits[output.decoder_id];
  if (result.level == "typed")
    ++context.statistics.typed_count;
  else if (result.level == "generic")
    ++context.statistics.generic_count;
  else if (result.level == "opaque")
    ++context.statistics.opaque_count;
  else
    ++context.statistics.failed_count;
  context.statistics.decoder_ms += static_cast<long>(
    (clock() - decode_start) * 1000 / CLOCKS_PER_SEC);
  return result;
}

namespace
{
// 用途：去除文本首尾的 ASCII 空白，不改动中间内容和非 ASCII 字节。
std::string TrimAscii(const std::string& value)
{
  std::string::size_type begin = 0;
  while (begin < value.size() &&
         (value[begin] == ' ' || value[begin] == '\t' || value[begin] == '\r' || value[begin] == '\n'))
    ++begin;
  std::string::size_type end = value.size();
  while (end > begin &&
         (value[end - 1] == ' ' || value[end - 1] == '\t' ||
          value[end - 1] == '\r' || value[end - 1] == '\n'))
    --end;
  return value.substr(begin, end - begin);
}

// 用途：判断单位是否属于本轮允许规范化的明确单位集合。
bool IsKnownUnit(const std::string& unit)
{
  return unit.empty() || unit == "mm" || unit == "cm" || unit == "m" ||
    unit == "deg" || unit == "rad";
}

// 用途：按特征编号查找原始记录；找不到时返回空指针。
const FeatureRecord* FindFeature(const std::vector<FeatureRecord>& features,
                                 const std::string& feature_id)
{
  std::vector<FeatureRecord>::const_iterator it = features.begin();
  for (; it != features.end(); ++it)
    if (it->feature_id == feature_id) return &*it;
  return 0;
}

// 用途：判断对象是否为可聚合的 GSMTool 声明式业务节点。
bool IsDeclaredBusinessCandidate(const FeatureRecord& feature)
{
  if (feature.fingerprint.native_type != "GSMTool" &&
      feature.fingerprint.startup_type != "GSMTool")
    return false;
  return !BusinessFeatureRuleCatalog::KindFromName(
    BusinessFeatureRuleCatalog::NormalizeInstanceName(feature.fingerprint.display_name)).empty();
}

// 用途：按聚合顺序生成稳定业务特征编号，不依赖 CAA 指针。
std::string MakeBusinessFeatureId(size_t index)
{
  std::ostringstream id;
  id << "BF" << std::setw(6) << std::setfill('0') << index;
  return id.str();
}
}

// 用途：仅在完整匹配“数字加明确单位”时填写辅助规范化结果。
void ParameterValueNormalizer::Normalize(ParameterValueData& parameter)
{
  parameter.has_normalized_numeric_value = false;
  parameter.normalized_numeric_value = 0.0;
  parameter.normalized_unit.clear();
  parameter.normalization_status = "not_numeric";

  const std::string candidate = TrimAscii(parameter.value_text);
  if (candidate.empty())
  {
    parameter.normalization_status = "empty_value";
    return;
  }

  errno = 0;
  char* number_end = 0;
  const double number = std::strtod(candidate.c_str(), &number_end);
  if (number_end == candidate.c_str() || errno == ERANGE)
    return;

  std::string unit = TrimAscii(std::string(number_end));
  if (!IsKnownUnit(unit))
    return;

  parameter.has_normalized_numeric_value = true;
  parameter.normalized_numeric_value = number;
  parameter.normalized_unit = unit;
  parameter.normalization_status = "success";
}

// 用途：沿 parent_of 关系向上查找最近的唯一业务特征归属。
std::string ParameterOwnershipResolver::Resolve(const std::string& parameter_id,
                                                const std::vector<FeatureRecord>& features,
                                                const std::vector<RelationRecord>& relations,
                                                std::string& status)
{
  std::map<std::string, std::vector<std::string> > parents;
  std::vector<RelationRecord>::const_iterator relation = relations.begin();
  for (; relation != relations.end(); ++relation)
    if (relation->kind == "parent_of") parents[relation->to_id].push_back(relation->from_id);

  std::vector<std::string> frontier;
  frontier.push_back(parameter_id);
  std::set<std::string> visited;
  visited.insert(parameter_id);
  while (!frontier.empty())
  {
    std::vector<std::string> next;
    std::set<std::string> owners;
    std::vector<std::string>::const_iterator child = frontier.begin();
    for (; child != frontier.end(); ++child)
    {
      const std::vector<std::string>& direct = parents[*child];
      std::vector<std::string>::const_iterator parent = direct.begin();
      for (; parent != direct.end(); ++parent)
      {
        if (!visited.insert(*parent).second) continue;
        const FeatureRecord* feature = FindFeature(features, *parent);
        if (feature && IsDeclaredBusinessCandidate(*feature)) owners.insert(*parent);
        else next.push_back(*parent);
      }
    }
    if (owners.size() == 1)
    {
      status = "resolved";
      return *owners.begin();
    }
    if (owners.size() > 1)
    {
      status = "ambiguous";
      return "";
    }
    frontier = next;
  }
  status = "not_found";
  return "";
}

// 用途：从原始参数特征建立消费索引、解析归属并更新参数覆盖率。
void ParameterRecordBuilder::Build(const std::vector<FeatureRecord>& features,
                                   const std::vector<RelationRecord>& relations,
                                   ParseContext& context,
                                   std::vector<ParameterRecord>& output)
{
  output.clear();
  ParseStatistics& statistics = context.statistics;
  statistics.parameter_total = 0;
  statistics.parameter_value_success = 0;
  statistics.parameter_value_partial = 0;
  statistics.parameter_value_unavailable = 0;
  statistics.parameter_failed = 0;
  statistics.orphan_parameter_count = 0;
  statistics.ambiguous_parameter_owner_count = 0;

  std::vector<FeatureRecord>::const_iterator feature = features.begin();
  for (; feature != features.end(); ++feature)
  {
    if (!feature->has_parameter) continue;
    ParameterRecord record;
    record.parameter_id = feature->feature_id;
    record.parent_id = feature->parent_id;
    record.tree_path = feature->tree_path;
    record.parameter_name = feature->parameter.parameter_name;
    record.parameter_kind = feature->parameter.parameter_kind;
    record.value_status = feature->parameter.value_status;
    record.value_source = feature->parameter.value_source;
    record.value_text = feature->parameter.value_text;
    record.raw_display_text = feature->parameter.raw_display_text;
    record.has_normalized_numeric_value = feature->parameter.has_normalized_numeric_value;
    record.normalized_numeric_value = feature->parameter.normalized_numeric_value;
    record.normalized_unit = feature->parameter.normalized_unit;
    record.normalization_status = feature->parameter.normalization_status;
    record.decoder_id = feature->decoder_id;
    record.diagnostic_ids = feature->diagnostic_ids;
    record.owner_feature_id = ParameterOwnershipResolver::Resolve(
      feature->feature_id, features, relations, record.ownership_status);

    if (record.ownership_status == "not_found")
    {
      ++statistics.orphan_parameter_count;
      record.diagnostic_ids.push_back(context.AddDiagnostic("info", "parameter_owner",
        "PARAM_OWNER_NOT_FOUND", "no declared business ancestor", record.parameter_id));
    }
    else if (record.ownership_status == "ambiguous")
    {
      ++statistics.ambiguous_parameter_owner_count;
      record.diagnostic_ids.push_back(context.AddDiagnostic("warning", "parameter_owner",
        "PARAM_OWNER_AMBIGUOUS", "multiple nearest declared business ancestors",
        record.parameter_id));
    }

    ++statistics.parameter_total;
    if (record.value_status == "success") ++statistics.parameter_value_success;
    else if (record.value_status == "partial") ++statistics.parameter_value_partial;
    else if (record.value_status == "failed") ++statistics.parameter_failed;
    else ++statistics.parameter_value_unavailable;
    output.push_back(record);
  }
}

// 用途：删除名称末尾由点号和纯数字组成的 CATIA 实例序号。
std::string BusinessFeatureRuleCatalog::NormalizeInstanceName(const std::string& name)
{
  const std::string::size_type dot = name.rfind('.');
  if (dot == std::string::npos || dot + 1 >= name.size()) return name;
  std::string::size_type index = dot + 1;
  for (; index < name.size(); ++index)
    if (name[index] < '0' || name[index] > '9') return name;
  return name.substr(0, dot);
}

// 用途：根据规范化中文基础名称返回声明式业务分类。
std::string BusinessFeatureRuleCatalog::KindFromName(const std::string& normalized_name)
{
  if (normalized_name == "\xE5\x87\xB8\xE5\x8F\xB0") return "declared_boss";
  if (normalized_name == "\xE5\xAD\x94") return "declared_hole";
  if (normalized_name == "\xE6\xA7\xBD") return "declared_slot";
  return "";
}

// 用途：聚合 GSMTool 节点和所属参数，生成声明式业务特征记录。
void DeclaredBusinessFeatureAggregator::Aggregate(
  const std::vector<FeatureRecord>& features,
  const std::vector<RelationRecord>&,
  const std::vector<ParameterRecord>& parameters,
  ParseContext& context,
  std::vector<BusinessFeatureRecord>& output)
{
  output.clear();
  ParseStatistics& statistics = context.statistics;
  statistics.declared_business_feature_total = 0;
  statistics.declared_boss_count = 0;
  statistics.declared_hole_count = 0;
  statistics.declared_slot_count = 0;
  statistics.declared_unknown_count = 0;
  statistics.business_feature_with_parameter_count = 0;
  statistics.business_feature_with_all_values_count = 0;
  statistics.business_feature_with_partial_values_count = 0;
  statistics.business_feature_without_values_count = 0;

  std::vector<FeatureRecord>::const_iterator feature = features.begin();
  for (; feature != features.end(); ++feature)
  {
    if (!IsDeclaredBusinessCandidate(*feature)) continue;
    BusinessFeatureRecord record;
    record.business_feature_id = MakeBusinessFeatureId(output.size() + 1);
    record.source_feature_id = feature->feature_id;
    record.display_name = feature->fingerprint.display_name;
    record.normalized_name = BusinessFeatureRuleCatalog::NormalizeInstanceName(record.display_name);
    record.tree_path = feature->tree_path;
    record.recognition_method = "declared_tree_parameter_aggregation";
    record.feature_kind = BusinessFeatureRuleCatalog::KindFromName(record.normalized_name);
    record.classification_status = "success";
    record.confidence = "medium";

    BusinessFeatureEvidence name_evidence;
    name_evidence.kind = "normalized_parent_name";
    name_evidence.value = record.normalized_name;
    record.evidence.push_back(name_evidence);

    std::string parameter_kind;
    long value_count = 0;
    std::vector<ParameterRecord>::const_iterator parameter = parameters.begin();
    for (; parameter != parameters.end(); ++parameter)
    {
      if (parameter->owner_feature_id != feature->feature_id) continue;
      record.parameter_ids.push_back(parameter->parameter_id);
      BusinessParameterData value;
      value.parameter_id = parameter->parameter_id;
      value.raw_value = parameter->value_text;
      value.has_normalized_numeric_value = parameter->has_normalized_numeric_value;
      value.normalized_numeric_value = parameter->normalized_numeric_value;
      value.normalized_unit = parameter->normalized_unit;
      value.value_status = parameter->value_status;
      record.parameters[parameter->parameter_name] = value;
      if (parameter->value_status == "success") ++value_count;
      if (parameter->parameter_name == "\xE7\x89\xB9\xE5\xBE\x81\xE7\xB1\xBB\xE5\x9E\x8B")
        parameter_kind = BusinessFeatureRuleCatalog::KindFromName(
          BusinessFeatureRuleCatalog::NormalizeInstanceName(TrimAscii(parameter->value_text)));
    }

    if (!record.parameter_ids.empty())
    {
      ++statistics.business_feature_with_parameter_count;
      BusinessFeatureEvidence signature;
      signature.kind = "parameter_signature";
      std::ostringstream count;
      count << record.parameter_ids.size() << " owned parameters";
      signature.value = count.str();
      record.evidence.push_back(signature);
    }

    if (!parameter_kind.empty())
    {
      BusinessFeatureEvidence declared;
      declared.kind = "declared_type_parameter";
      declared.value = parameter_kind;
      record.evidence.push_back(declared);
      if (parameter_kind == record.feature_kind) record.confidence = "high";
      else
      {
        record.feature_kind = "declared_unknown";
        record.classification_status = "ambiguous";
        record.confidence = "low";
        record.diagnostic_ids.push_back(context.AddDiagnostic("warning", "business_feature",
          "BUSINESS_FEATURE_CLASSIFICATION_AMBIGUOUS",
          "normalized name conflicts with declared type parameter", feature->feature_id));
      }
    }

    if (record.parameter_ids.empty()) ++statistics.business_feature_without_values_count;
    else if (value_count == static_cast<long>(record.parameter_ids.size()))
      ++statistics.business_feature_with_all_values_count;
    else if (value_count == 0) ++statistics.business_feature_without_values_count;
    else ++statistics.business_feature_with_partial_values_count;

    ++statistics.declared_business_feature_total;
    if (record.feature_kind == "declared_boss") ++statistics.declared_boss_count;
    else if (record.feature_kind == "declared_hole") ++statistics.declared_hole_count;
    else if (record.feature_kind == "declared_slot") ++statistics.declared_slot_count;
    else ++statistics.declared_unknown_count;
    output.push_back(record);
  }
}

// 用途：生成连续且稳定的特征编号；第一个编号为 F000001。
std::string FeatureIdGenerator::Next()
{
  std::ostringstream id;
  id << "F" << std::setw(6) << std::setfill('0') << ++_next;
  return id.str();
}

// 用途：转义 JSON 字符串中的引号、反斜杠、控制字符和换行。
// UTF-8 多字节内容原样保留，只对 JSON 语法要求的字节进行转义。
std::string JsonEscape(const std::string& value)
{
  std::ostringstream output;
  std::string::const_iterator it = value.begin();
  for (; it != value.end(); ++it)
  {
    // 转为无符号字符后再比较控制字符范围，避免有符号 char 的平台差异。
    const unsigned char c = static_cast<unsigned char>(*it);
    if (c == '"') output << "\\\"";
    else if (c == '\\') output << "\\\\";
    else if (c == '\n') output << "\\n";
    else if (c == '\r') output << "\\r";
    else if (c == '\t') output << "\\t";
    else if (c < 0x20)
      output << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c)
             << std::dec;
    else
      output << *it;
  }
  return output.str();
}

namespace
{
typedef unsigned long ShaWord;

// 用途：执行 SHA-256 所需的三十二位循环右移；Win32 的 unsigned long 为三十二位。
ShaWord RotateRight(ShaWord value, int bits)
{
  return (value >> bits) | (value << (32 - bits));
}

// 用途：把三十二位字转换为固定八位的小写十六进制文本。
std::string HexWord(ShaWord value)
{
  std::ostringstream text;
  text << std::hex << std::setw(8) << std::setfill('0') << value;
  return text.str();
}
}

// 用途：计算内存文本的 SHA-256 摘要，供清单追溯和测试使用。
std::string Sha256String(const std::string& value)
{
  static const ShaWord constants[64] = {
    0x428a2f98UL,0x71374491UL,0xb5c0fbcfUL,0xe9b5dba5UL,0x3956c25bUL,0x59f111f1UL,0x923f82a4UL,0xab1c5ed5UL,
    0xd807aa98UL,0x12835b01UL,0x243185beUL,0x550c7dc3UL,0x72be5d74UL,0x80deb1feUL,0x9bdc06a7UL,0xc19bf174UL,
    0xe49b69c1UL,0xefbe4786UL,0x0fc19dc6UL,0x240ca1ccUL,0x2de92c6fUL,0x4a7484aaUL,0x5cb0a9dcUL,0x76f988daUL,
    0x983e5152UL,0xa831c66dUL,0xb00327c8UL,0xbf597fc7UL,0xc6e00bf3UL,0xd5a79147UL,0x06ca6351UL,0x14292967UL,
    0x27b70a85UL,0x2e1b2138UL,0x4d2c6dfcUL,0x53380d13UL,0x650a7354UL,0x766a0abbUL,0x81c2c92eUL,0x92722c85UL,
    0xa2bfe8a1UL,0xa81a664bUL,0xc24b8b70UL,0xc76c51a3UL,0xd192e819UL,0xd6990624UL,0xf40e3585UL,0x106aa070UL,
    0x19a4c116UL,0x1e376c08UL,0x2748774cUL,0x34b0bcb5UL,0x391c0cb3UL,0x4ed8aa4aUL,0x5b9cca4fUL,0x682e6ff3UL,
    0x748f82eeUL,0x78a5636fUL,0x84c87814UL,0x8cc70208UL,0x90befffaUL,0xa4506cebUL,0xbef9a3f7UL,0xc67178f2UL
  };
  ShaWord hash[8] = { 0x6a09e667UL, 0xbb67ae85UL, 0x3c6ef372UL, 0xa54ff53aUL,
                      0x510e527fUL, 0x9b05688cUL, 0x1f83d9abUL, 0x5be0cd19UL };
  std::vector<unsigned char> bytes(value.begin(), value.end());
  const unsigned __int64 bit_length = static_cast<unsigned __int64>(bytes.size()) * 8;
  bytes.push_back(0x80);
  while ((bytes.size() % 64) != 56) bytes.push_back(0);
  int length_byte = 7;
  for (; length_byte >= 0; --length_byte)
    bytes.push_back(static_cast<unsigned char>((bit_length >> (length_byte * 8)) & 0xff));

  size_t offset = 0;
  for (; offset < bytes.size(); offset += 64)
  {
    ShaWord words[64];
    int index = 0;
    for (; index < 16; ++index)
    {
      const size_t pos = offset + index * 4;
      words[index] = (static_cast<ShaWord>(bytes[pos]) << 24) |
                     (static_cast<ShaWord>(bytes[pos + 1]) << 16) |
                     (static_cast<ShaWord>(bytes[pos + 2]) << 8) |
                      static_cast<ShaWord>(bytes[pos + 3]);
    }
    for (; index < 64; ++index)
    {
      const ShaWord s0 = RotateRight(words[index - 15], 7) ^
        RotateRight(words[index - 15], 18) ^ (words[index - 15] >> 3);
      const ShaWord s1 = RotateRight(words[index - 2], 17) ^
        RotateRight(words[index - 2], 19) ^ (words[index - 2] >> 10);
      words[index] = words[index - 16] + s0 + words[index - 7] + s1;
    }

    ShaWord a = hash[0], b = hash[1], c = hash[2], d = hash[3];
    ShaWord e = hash[4], f = hash[5], g = hash[6], h = hash[7];
    for (index = 0; index < 64; ++index)
    {
      const ShaWord big1 = RotateRight(e, 6) ^ RotateRight(e, 11) ^ RotateRight(e, 25);
      const ShaWord choice = (e & f) ^ ((~e) & g);
      const ShaWord first = h + big1 + choice + constants[index] + words[index];
      const ShaWord big0 = RotateRight(a, 2) ^ RotateRight(a, 13) ^ RotateRight(a, 22);
      const ShaWord majority = (a & b) ^ (a & c) ^ (b & c);
      const ShaWord second = big0 + majority;
      h = g; g = f; f = e; e = d + first;
      d = c; c = b; b = a; a = first + second;
    }
    hash[0] += a; hash[1] += b; hash[2] += c; hash[3] += d;
    hash[4] += e; hash[5] += f; hash[6] += g; hash[7] += h;
  }

  std::string result;
  int hash_index = 0;
  for (; hash_index < 8; ++hash_index) result += HexWord(hash[hash_index]);
  return result;
}

// 用途：以二进制方式读取文件并计算 SHA-256；失败时返回错误原因。
std::string Sha256File(const std::string& path, std::string& error)
{
  std::ifstream input(path.c_str(), std::ios::in | std::ios::binary);
  if (!input)
  {
    error = "cannot open file for SHA-256";
    return "";
  }
  std::ostringstream bytes;
  bytes << input.rdbuf();
  if (input.bad())
  {
    error = "cannot read file for SHA-256";
    return "";
  }
  error.clear();
  return Sha256String(bytes.str());
}

// 用途：默认只输出文件名；显式允许时才保留完整源路径。
std::string SourcePathForOutput(const std::string& path, bool include_source_path)
{
  if (include_source_path) return path;
  const std::string::size_type slash = path.find_last_of("/\\");
  return slash == std::string::npos ? path : path.substr(slash + 1);
}

// 用途：返回当前协调世界时的 ISO-8601 时间文本。
std::string UtcNowIso8601()
{
  const std::time_t now = std::time(0);
  std::tm utc;
#if defined(_MSC_VER)
  gmtime_s(&utc, &now);
#else
  utc = *std::gmtime(&now);
#endif
  char buffer[32];
  std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &utc);
  return buffer;
}

// 用途：扫描文件头中的版本提示，并明确标记为源文件提示而非运行时版本。
void ReadSourceFileHint(const std::string& path, ParseMetadata& metadata)
{
  metadata.source_hint_release = "unknown";
  metadata.source_hint_service_pack = "unknown";
  metadata.source_hint_hotfix = "unknown";
  metadata.source_hint_value_source = "CATPart binary header scan";
  metadata.source_hint_confidence = "hint";
  std::ifstream input(path.c_str(), std::ios::in | std::ios::binary);
  if (!input) return;
  const size_t limit = 1024 * 1024;
  std::vector<char> buffer(limit);
  input.read(&buffer[0], static_cast<std::streamsize>(buffer.size()));
  const std::string text(&buffer[0], static_cast<size_t>(input.gcount()));
  const std::string marker = "V5R";
  std::string::size_type position = text.find(marker);
  for (; position != std::string::npos; position = text.find(marker, position + 1))
  {
    std::string::size_type release_end = position + marker.size();
    while (release_end < text.size() && text[release_end] >= '0' && text[release_end] <= '9')
      ++release_end;
    if (release_end == position + marker.size()) continue;
    const std::string::size_type sp = text.find("SP", release_end);
    const std::string::size_type hf = sp == std::string::npos ? std::string::npos : text.find("HF", sp + 2);
    if (sp != release_end || hf == std::string::npos || hf - sp > 8) continue;
    std::string::size_type hf_end = hf + 2;
    while (hf_end < text.size() && text[hf_end] >= '0' && text[hf_end] <= '9') ++hf_end;
    metadata.source_hint_release = text.substr(position, release_end - position);
    metadata.source_hint_service_pack = text.substr(sp, hf - sp);
    metadata.source_hint_hotfix = text.substr(hf, hf_end - hf);
    return;
  }
}
}
