// 本文件实现 API 无关的解析核心：统计、诊断、Decoder 匹配、Generic/Opaque 兜底和 JSON 转义。
// 它只依赖标准 C++03，因此既能被 CAA Batch 使用，也能在没有 CATIA 许可证时单独测试。
#include "CadParseContracts.h"

#include <iomanip>
#include <sstream>
#include <ctime>

namespace cadparse
{
// 用途：把解析统计的全部数值字段初始化为 0，避免未初始化整数造成随机 Coverage 结果。
ParseStatistics::ParseStatistics()
  : enumerated_total(0), typed_count(0), generic_count(0), opaque_count(0), failed_count(0),
    container_count(0), relation_count(0), unknown_native_type_count(0),
    interface_probe_success_count(0), interface_probe_failure_count(0), document_open_ms(0),
    traversal_ms(0), decoder_ms(0), output_ms(0), total_ms(0)
{
}

// 用途：验证每个已枚举对象最终恰好落入 typed、generic、opaque、failed 四类之一。
bool ParseStatistics::IsConserved() const
{
  return enumerated_total == typed_count + generic_count + opaque_count + failed_count;
}

// 用途：创建一条诊断记录并追加到上下文，返回可写入 FeatureRecord 的稳定诊断 ID。
// ID 取决于插入顺序而不是内存地址，因此同一遍历顺序下可以重复得到相同输出。
std::string ParseContext::AddDiagnostic(const char* severity, const char* stage, const char* code,
                                        const char* message, const std::string& feature_id)
{
  DiagnosticRecord diagnostic;
  std::ostringstream id;
  // setw(6) 与 setfill('0') 把序号格式化成六位；size()+1 让第一条记录从 D000001 开始。
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

// 用途：返回 Generic Decoder 的稳定 ID，供 IR、统计和冲突决胜使用。
const char* GenericFeatureDecoder::GetDecoderId() const { return "generic"; }
// 用途：返回很低的优先级；Generic 是兜底，不应压过任何已验证专用 Decoder。
int GenericFeatureDecoder::GetPriority() const { return -1000; }
// 用途：始终返回 true，使 Generic 理论上能接住任意对象；实际由 FeatureTypeRegistry 显式调用。
bool GenericFeatureDecoder::Match(const TypeFingerprint&, const INativeObjectView&) const { return true; }

// 用途：通过通用对象视图读取基础属性，并把本次结果标记为 generic success。
// 读取失败时保留 error 文本并返回不成功结果，让调用方继续进入 Opaque Recorder。
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

// 用途：在任何属性读取都失败时，仍保存指纹、失败阶段和诊断，避免对象从 IR 中消失。
// view 只在调用期间被借用；写入 output 的全部内容都是独立值，不保留原生指针。
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

// 用途：把非空 Decoder 指针加入候选列表；本容器不拥有指针，也不会负责 delete。
void DecoderRegistry::Register(IFeatureDecoder* decoder)
{
  if (decoder)
    _decoders.push_back(decoder);
}

// 用途：把类型指纹的全部可用字段按固定顺序拼成稳定键，供 Catalog 去重。
// 0x1f 是字段分隔控制字符，可避免普通名称拼接产生边界歧义，但不会输出到用户 JSON。
std::string FeatureTypeFingerprintBuilder::StableKey(const TypeFingerprint& fingerprint)
{
  std::ostringstream key;
  key << fingerprint.native_type << '\x1f' << fingerprint.startup_type << '\x1f'
      << fingerprint.container_kind << '\x1f' << fingerprint.internal_name << '\x1f'
      << fingerprint.display_name;
  // C++03 没有范围 for，这里使用 const_iterator 只读遍历 vector。
  std::vector<std::string>::const_iterator super_type = fingerprint.super_types.begin();
  for (; super_type != fingerprint.super_types.end(); ++super_type) key << '\x1f' << *super_type;
  std::vector<std::string>::const_iterator interface_key =
    fingerprint.supported_interface_keys.begin();
  for (; interface_key != fingerprint.supported_interface_keys.end(); ++interface_key)
    key << '\x1f' << *interface_key;
  return key.str();
}

// 用途：记录一个已观察类型指纹；std::set 自动去重并提供稳定排序。
void FeatureTypeCatalog::Observe(const TypeFingerprint& fingerprint)
{
  _keys.insert(FeatureTypeFingerprintBuilder::StableKey(fingerprint));
}

// 用途：返回 Catalog 中不同稳定指纹的数量。
size_t FeatureTypeCatalog::Count() const { return _keys.size(); }

// 用途：判断候选 Decoder 是否优于当前最佳项。
// 先比较显式 priority；相同时选择字典序更小的稳定 ID，结果与注册顺序无关。
bool DecoderMatchEngine::IsBetter(const IFeatureDecoder* candidate,
                                  const IFeatureDecoder* current)
{
  return candidate && (!current || candidate->GetPriority() > current->GetPriority() ||
    (candidate->GetPriority() == current->GetPriority() &&
     std::string(candidate->GetDecoderId()) < current->GetDecoderId()));
}

// 用途：记录缺少 native_type 的对象类型，用 startup_type 或占位符进行去重统计。
void UnknownTypeCollector::Observe(const TypeFingerprint& fingerprint)
{
  if (!fingerprint.native_type.empty()) return;
  const std::string key = fingerprint.startup_type.empty() ? "<unavailable>" : fingerprint.startup_type;
  _unknown_types.insert(key);
}

// 用途：返回不同未知类型键的数量。
size_t UnknownTypeCollector::Count() const { return _unknown_types.size(); }

// 用途：为调用方提供命名清晰的 Coverage 校验入口，当前规则委托给 IsConserved。
bool CoverageTracker::Validate(const ParseStatistics& statistics)
{
  return statistics.IsConserved();
}

// 用途：遍历所有已注册 Decoder，隔离 Match 异常，并按确定性规则返回最佳匹配。
// 返回的是借用指针；Registry 和调用方都不能在这里释放它。
IFeatureDecoder* DecoderRegistry::Find(const TypeFingerprint& fingerprint,
                                       const INativeObjectView& view,
                                       ParseContext& context) const
{
  IFeatureDecoder* best = 0;
  int equal_best_count = 0;
  std::vector<IFeatureDecoder*>::const_iterator it = _decoders.begin();
  // 每个候选独立 try/catch：一个第三方 Decoder 的 Match 异常不能中止其他候选匹配。
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
      continue;
    }
    if (!matched)
      continue;

    if (!best || candidate->GetPriority() > best->GetPriority())
    {
      best = candidate;
      equal_best_count = 1;
    }
    else if (candidate->GetPriority() == best->GetPriority())
    {
      ++equal_best_count;
      // 同优先级时用稳定 ID 决胜；equal_best_count 另外用于向用户暴露配置冲突。
      if (DecoderMatchEngine::IsBetter(candidate, best))
        best = candidate;
    }
  }
  if (best && equal_best_count > 1)
    context.AddDiagnostic("warning", "registry", "DECODER_PRIORITY_TIE",
                          "stable decoder id tie break", "");
  return best;
}

// 用途：创建带内置 Generic/Opaque 兜底对象的 FeatureTypeRegistry。
FeatureTypeRegistry::FeatureTypeRegistry() {}

// 用途：把一个专用 Decoder 转交内部 DecoderRegistry 登记，不转移所有权。
void FeatureTypeRegistry::Register(IFeatureDecoder* decoder)
{
  _registry.Register(decoder);
}

// 用途：完成单对象解析闭环：专用 Decoder → Generic → Opaque，并更新守恒统计和耗时。
// 无论专用解析是否失败，调用结束时 output 都应代表一个可写入 IR 的对象记录。
DecodeResult FeatureTypeRegistry::DecodeObject(const INativeObjectView& view, ParseContext& context,
                                               FeatureRecord& output)
{
  const clock_t decode_start = clock();
  output.fingerprint = view.GetFingerprint();
  // 保存遍历层已经建立的 ID、父节点和树路径。专用 Decoder 可能写入一半后失败，兜底前要恢复它们。
  const FeatureRecord fallback_base = output;
  IFeatureDecoder* decoder = _registry.Find(output.fingerprint, view, context);
  DecodeResult result(false, "failed", "no typed decoder");

  if (decoder)
  {
    // Decoder 是扩展边界，必须捕获所有 C++ 异常，防止一个对象拖垮整份 CATPart。
    try
    {
      result = decoder->Decode(view, context, output);
    }
    catch (...)
    {
      const std::string id = context.AddDiagnostic("warning", "decoder", "DECODER_EXCEPTION",
                                                   decoder->GetDecoderId(), output.feature_id);
      output.diagnostic_ids.push_back(id);
      result = DecodeResult(false, "failed", "typed decoder exception");
    }
  }

  if (!decoder || !result.success)
  {
    if (decoder && result.message != "typed decoder exception")
    {
      const std::string id = context.AddDiagnostic("warning", "decoder", "DECODER_FAILED",
                                                   result.message.c_str(), output.feature_id);
      output.diagnostic_ids.push_back(id);
    }
    const std::vector<std::string> failure_diagnostic_ids = output.diagnostic_ids;
    // 恢复干净基础记录，但保留已经产生的诊断 ID，随后由 Generic 重新填充通用字段。
    output = fallback_base;
    output.diagnostic_ids = failure_diagnostic_ids;
    result = _generic.Decode(view, context, output);
  }

  if (!result.success)
    // Generic 也失败时仍生成 Opaque 记录，这条路径保证“枚举到的对象一定有 IR”。
    result = _opaque.Record(view, context, output, "generic",
                            result.message.empty() ? "generic fallback unavailable" : result.message);

  // 分类计数只在最终结果确定后增加一次，从结构上维护 Coverage 守恒。
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

// 用途：生成下一个固定宽度 Feature ID；前置自增使首个 ID 为 F000001。
std::string FeatureIdGenerator::Next()
{
  std::ostringstream id;
  id << "F" << std::setw(6) << std::setfill('0') << ++_next;
  return id.str();
}

// 用途：转义 JSON 字符串内容，包括引号、反斜杠、换行和 U+0020 以下控制字符。
// UTF-8 多字节内容按原字节保留，只有 JSON 语法要求处理的 ASCII 字节会被替换。
std::string JsonEscape(const std::string& value)
{
  std::ostringstream output;
  std::string::const_iterator it = value.begin();
  for (; it != value.end(); ++it)
  {
    // 转为 unsigned char 后再与 0x20 比较，避免 char 在不同编译器上有符号性不同。
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
}
