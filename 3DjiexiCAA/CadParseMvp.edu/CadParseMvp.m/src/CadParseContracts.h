// 本文件定义解析器各层共享的“契约”：纯数据 IR、运行上下文、抽象接口和注册中心。
// 这里刻意不包含任何 CATIA 头文件，使 Registry、IR 和自测可以在没有 CAA 许可证时编译。
#ifndef CAD_PARSE_CONTRACTS_H
#define CAD_PARSE_CONTRACTS_H

#include <map>
#include <set>
#include <string>
#include <vector>

namespace cadparse
{
// 一个对象的类型指纹。Registry 只依据这些稳定文本选择 Decoder，不使用进程内指针地址。
struct TypeFingerprint
{
  // CAA 对象报告的原生类型；其余字段按“能够可靠取得时填写”的原则保存。
  std::string native_type;
  std::string startup_type;
  std::vector<std::string> super_types;
  std::vector<std::string> supported_interface_keys;
  std::string container_kind;
  std::string internal_name;
  std::string display_name;
};

// features.jsonl 中一行对应一个 FeatureRecord。
// 该结构只保存值类型和字符串，因此离开 CATIA Session 后仍然安全有效。
struct FeatureRecord
{
  // 用途：创建一条尚未遍历的 Feature 记录，并把序号初始化为 0。
  // C++03 没有类内成员初始值，这里使用构造函数初始化列表。
  FeatureRecord() : traversal_index(0) {}

  std::string feature_id;
  std::string parent_id;
  long traversal_index;
  TypeFingerprint fingerprint;
  std::string tree_path;
  std::string update_status;
  std::string visibility;
  std::string decoder_id;
  std::string decode_level;
  std::string decode_status;
  std::map<std::string, std::string> attributes;
  std::vector<std::string> diagnostic_ids;
};

// 两个已存在 IR 对象之间的有向关系。
struct RelationRecord
{
  std::string kind;
  std::string from_id;
  std::string to_id;
};

// 可独立追踪的一条诊断；对象级错误通过 feature_id 关联到 FeatureRecord。
struct DiagnosticRecord
{
  std::string diagnostic_id;
  std::string severity;
  std::string stage;
  std::string code;
  std::string message;
  std::string feature_id;
};

// Decoder 的单次执行结果，用于决定 typed、generic 或 opaque 后续路径。
struct DecodeResult
{
  // 用途：构造 Decoder 结果，并为常见的 typed 成功场景提供默认值。
  // const char* 会被复制进 std::string，结果不借用调用者字符串的内存。
  DecodeResult(bool ok = true, const char* result_level = "typed", const char* detail = "")
    : success(ok), level(result_level), message(detail) {}

  bool success;
  std::string level;
  std::string message;
};

// 一次解析的计数和耗时汇总；所有计数都是 revision-local 的运行结果。
struct ParseStatistics
{
  // 用途：把所有计数器和耗时字段初始化为 0。
  ParseStatistics();
  // 用途：检查枚举总数是否等于 typed、generic、opaque、failed 四类结果之和。
  // 返回 false 代表记录有遗漏，Batch 必须把它视为校验失败。
  bool IsConserved() const;

  long enumerated_total;
  long typed_count;
  long generic_count;
  long opaque_count;
  long failed_count;
  long container_count;
  long relation_count;
  long unknown_native_type_count;
  long interface_probe_success_count;
  long interface_probe_failure_count;
  long document_open_ms;
  long traversal_ms;
  long decoder_ms;
  long output_ms;
  long total_ms;
  std::map<std::string, long> decoder_hits;
};

// 一次解析任务的共享上下文，集中保存统计、诊断和运行环境信息。
class ParseContext
{
public:
  // 用途：生成稳定递增的诊断 ID，将诊断加入上下文，并把新 ID 返回给调用者。
  // 参数中的 const char* 允许传入空指针，实现在这种情况下会使用安全默认值。
  std::string AddDiagnostic(const char* severity, const char* stage, const char* code,
                            const char* message, const std::string& feature_id);

  ParseStatistics statistics;
  std::vector<DiagnosticRecord> diagnostics;
  std::map<std::string, std::string> runtime_info;
};

// 对原生 CAA 对象的最小只读视图。
// Decoder 只依赖此接口，从而不会把 CAA 裸指针写入 IR 或扩散到 API 无关模块。
class INativeObjectView
{
public:
  // 用途：通过基类指针销毁实现类时调用正确的派生类析构函数。
  virtual ~INativeObjectView() {}
  // 用途：返回适配器持有的类型指纹只读引用；调用者不得修改或长期保存该引用。
  virtual const TypeFingerprint& GetFingerprint() const = 0;
  // 用途：尽力把对象的通用属性复制到纯数据记录中。
  // 返回 false 时在 error 中说明原因，Registry 随后可以转入 Opaque 兜底。
  virtual bool ReadBasicAttributes(FeatureRecord& output, std::string& error) const = 0;
};

// 解析产物写入器的抽象接口，使核心解析流程不依赖具体 JSON 实现。
class IArtifactWriter
{
public:
  // 用途：确保通过 IArtifactWriter 指针销毁具体 Writer 时析构完整。
  virtual ~IArtifactWriter() {}
  // 用途：把完整的 Feature、关系和上下文写入 output_dir。
  // 返回 false 表示文档级输出失败，error 提供可显示的原因。
  virtual bool Write(const std::vector<FeatureRecord>& features,
                     const std::vector<RelationRecord>& relations,
                     const ParseContext& context,
                     const std::string& output_dir,
                     std::string& error) = 0;
};

// 单个对象 Decoder 的统一契约。
// Decoder 负责解释一个对象，不负责遍历整棵规格树，也不拥有传入的 object_view。
class IFeatureDecoder
{
public:
  // 用途：允许通过接口指针安全销毁具体 Decoder。
  virtual ~IFeatureDecoder() {}
  // 用途：返回稳定 Decoder ID，用于冲突决胜、统计和输出；返回字符串由实现类持有。
  virtual const char* GetDecoderId() const = 0;
  // 用途：返回显式匹配优先级；数值越高，匹配胜出概率越高。
  virtual int GetPriority() const = 0;
  // 用途：只读判断当前 Decoder 是否支持给定类型指纹和对象视图。
  virtual bool Match(const TypeFingerprint& fingerprint,
                     const INativeObjectView& object_view) const = 0;
  // 用途：把对象解释结果写入 output，并通过 context 记录诊断和统计。
  // Decoder 失败不会终止文档解析，Registry 会继续执行 Generic/Opaque 兜底。
  virtual DecodeResult Decode(const INativeObjectView& object_view,
                              ParseContext& context,
                              FeatureRecord& output) = 0;
};

// 所有未知类型的第一层兜底 Decoder，只读取 INativeObjectView 暴露的基础属性。
class GenericFeatureDecoder : public IFeatureDecoder
{
public:
  // 用途：返回 Generic Decoder 的稳定 ID。
  const char* GetDecoderId() const;
  // 用途：返回最低优先级，保证专用 Decoder 优先被选择。
  int GetPriority() const;
  // 用途：始终声明可匹配，作为没有专用匹配时的通用后备。
  bool Match(const TypeFingerprint&, const INativeObjectView&) const;
  // 用途：读取基础属性；读取失败时返回 opaque 级别，交由 Opaque Recorder 保底。
  DecodeResult Decode(const INativeObjectView&, ParseContext&, FeatureRecord&);
};

// 最后一层保底记录器；即使对象属性不可读，也保留对象存在性、树位置和失败信息。
class OpaqueObjectRecorder
{
public:
  // 用途：把现有指纹和失败上下文写入 output，并生成一条对象级 warning。
  DecodeResult Record(const INativeObjectView&, ParseContext&, FeatureRecord&,
                      const std::string& stage, const std::string& reason);
};

// 保存可参与匹配的 Decoder，并按确定性规则选择最佳项。
// Registry 只借用传入指针，不负责 delete；所有权由创建 Decoder 的运行时层持有。
class DecoderRegistry
{
public:
  // 用途：注册一个非空 Decoder 借用指针。
  void Register(IFeatureDecoder* decoder);
  // 用途：寻找最佳匹配 Decoder；发生同优先级冲突时写入诊断。
  // 返回值仍由外部所有者管理，调用者不得 delete。
  IFeatureDecoder* Find(const TypeFingerprint&, const INativeObjectView&, ParseContext&) const;

private:
  std::vector<IFeatureDecoder*> _decoders;
};

// 把多字段类型指纹编码成可比较、可去重的稳定字符串键。
class FeatureTypeFingerprintBuilder
{
public:
  // 用途：按固定字段顺序生成稳定键，不包含对象地址或运行期句柄。
  static std::string StableKey(const TypeFingerprint& fingerprint);
};

// 收集本次遍历实际观察到的不同类型指纹。
class FeatureTypeCatalog
{
public:
  // 用途：把一个类型指纹加入去重集合。
  void Observe(const TypeFingerprint& fingerprint);
  // 用途：返回已经观察到的不同指纹数量。
  size_t Count() const;

private:
  std::set<std::string> _keys;
};

// 封装两个候选 Decoder 的稳定比较规则。
class DecoderMatchEngine
{
public:
  // 用途：判断 candidate 是否应替换 current；先比较 priority，再比较稳定 ID。
  static bool IsBetter(const IFeatureDecoder* candidate, const IFeatureDecoder* current);
};

// 受控接口探测服务的扩展点；实现只能探测已在 R21 资料中确认并注册的接口键。
class InterfaceProbeService
{
public:
  // 用途：允许通过接口指针正确析构具体探测服务。
  virtual ~InterfaceProbeService() {}
  // 用途：探测指定接口键，成功时扩充 fingerprint，并同步更新成功/失败统计。
  virtual bool Probe(const char* interface_key, TypeFingerprint& fingerprint,
                     ParseStatistics& statistics) = 0;
};

// 对 Generic/Opaque 类型进行去重统计，不承诺识别其业务语义。
class UnknownTypeCollector
{
public:
  // 用途：记录一个未知对象的原生类型；空类型使用稳定占位值处理。
  void Observe(const TypeFingerprint& fingerprint);
  // 用途：返回不同未知原生类型的数量。
  size_t Count() const;

private:
  std::set<std::string> _unknown_types;
};

// 解析统计守恒规则的命名入口。
class CoverageTracker
{
public:
  // 用途：验证统计中的四类结果之和等于枚举总数。
  static bool Validate(const ParseStatistics& statistics);
};

// 面向调用方的完整 Decoder 门面：专用匹配、Generic 和 Opaque 都从这里串联。
class FeatureTypeRegistry
{
public:
  // 用途：创建 Registry；内置 Generic 和 Opaque 兜底对象随 Registry 共同生存。
  FeatureTypeRegistry();
  // 用途：把专用 Decoder 注册到内部匹配表；不转移指针所有权。
  void Register(IFeatureDecoder* decoder);
  // 用途：为单个对象选择并执行 Decoder；专用失败后仍会尝试 Generic/Opaque。
  DecodeResult DecodeObject(const INativeObjectView&, ParseContext&, FeatureRecord&);

private:
  DecoderRegistry _registry;
  GenericFeatureDecoder _generic;
  OpaqueObjectRecorder _opaque;
};

// 生成 revision-local、与指针地址无关的稳定递增 Feature ID。
class FeatureIdGenerator
{
public:
  // 用途：创建 ID 生成器，下一个生成序号从 1 开始。
  FeatureIdGenerator() : _next(0) {}
  // 用途：返回形如 F000001 的新 ID，并推进内部计数器。
  std::string Next();

private:
  long _next;
};

// 用途：把任意 UTF-8 字符串转义成可安全放入 JSON 双引号中的内容。
std::string JsonEscape(const std::string& value);

// API 无关的自测集合，由普通测试程序或 CAA Batch 的 --self-test 调用。
class SelfTestSuite
{
public:
  // 用途：顺序执行全部核心测试；全部通过返回 0，否则返回非零值。
  int RunAll();
};
}

#endif
