// 本文件实现不依赖 CATIA 许可证的核心自测，通过伪对象和伪 Decoder 验证 Registry、兜底和 IR。
// 测试沿用 C++03 与极小 TestRunner，不引入 VS2008 环境中不存在的第三方测试框架。
#include "CadParseContracts.h"
#include "CadParseIR.h"

#include <fstream>
#include <iostream>
#include <set>
#include <sstream>

using namespace std;

namespace cadparse
{
// 可控制“基础属性是否可读”的伪原生对象视图，用来驱动 Generic 和 Opaque 路径。
class FakeView : public INativeObjectView
{
public:
  // 用途：构造指定 native_type 的伪对象，并放入包含中文、引号的 UTF-8 显示名。
  FakeView(const char* type, bool readable = true) : _readable(readable)
  {
    _fingerprint.native_type = type;
    _fingerprint.display_name = "\xE4\xB8\xAD\xE6\x96\x87\"name";
  }

  // 用途：返回伪对象的稳定类型指纹。
  const TypeFingerprint& GetFingerprint() const { return _fingerprint; }

  // 用途：按 _readable 开关模拟基础属性成功或失败，供兜底测试精确控制路径。
  bool ReadBasicAttributes(FeatureRecord& record, std::string& error) const
  {
    if (!_readable)
    {
      error = "read failure";
      return false;
    }
    record.attributes["name"] = _fingerprint.display_name;
    return true;
  }

private:
  TypeFingerprint _fingerprint;
  bool _readable;
};

// 可配置 ID、优先级和抛异常行为的伪 Typed Decoder。
class TypedDecoder : public IFeatureDecoder
{
public:
  // 用途：创建测试 Decoder；id 使用字符串常量，测试期间不转移其内存所有权。
  TypedDecoder(const char* id, int priority, bool throws_on_decode = false)
    : _id(id), _priority(priority), _throws_on_decode(throws_on_decode) {}

  // 用途：返回测试指定的稳定 Decoder ID。
  const char* GetDecoderId() const { return _id; }
  // 用途：返回测试指定的匹配优先级。
  int GetPriority() const { return _priority; }

  // 用途：只匹配 native_type 为 Known 的伪对象。
  bool Match(const TypeFingerprint& fingerprint, const INativeObjectView&) const
  {
    return fingerprint.native_type == "Known";
  }

  // 用途：模拟成功 Typed Decode，或按开关抛出异常验证 Registry 的异常隔离。
  DecodeResult Decode(const INativeObjectView&, ParseContext&, FeatureRecord& record)
  {
    if (_throws_on_decode)
      throw "decoder failure";
    record.decoder_id = _id;
    record.decode_level = "typed";
    record.decode_status = "success";
    return DecodeResult(true, "typed");
  }

private:
  const char* _id;
  int _priority;
  bool _throws_on_decode;
};

// 故意先污染 output 再返回失败的 Decoder，用于验证 Generic 前会恢复干净基础记录。
class DirtyFailingDecoder : public IFeatureDecoder
{
public:
  // 用途：返回污染测试 Decoder 的稳定 ID。
  const char* GetDecoderId() const { return "dirty"; }
  // 用途：提供高于 Generic 的优先级，确保该 Decoder 先被执行。
  int GetPriority() const { return 100; }
  // 用途：只匹配 Known 对象，使测试路径确定。
  bool Match(const TypeFingerprint& fingerprint, const INativeObjectView&) const
  { return fingerprint.native_type == "Known"; }
  // 用途：写入不应泄漏的半成品属性后主动返回失败结果。
  DecodeResult Decode(const INativeObjectView&, ParseContext&, FeatureRecord& record)
  {
    record.decoder_id = "dirty";
    record.attributes["partial_typed_value"] = "must_not_leak";
    return DecodeResult(false, "failed", "intentional partial failure");
  }
};

// 最小测试运行器：累计失败数并把失败用例名称写到标准错误流。
class TestRunner
{
public:
  // 用途：创建尚无失败的测试运行器。
  TestRunner() : _failures(0) {}

  // 用途：断言 condition；失败时递增计数并输出便于定位的用例名称。
  void Check(bool condition, const char* name)
  {
    if (!condition)
    {
      ++_failures;
      cerr << "FAILED: " << name << endl;
    }
  }

  // 用途：返回累计失败数，供进程入口转换为退出码。
  int Failures() const { return _failures; }

private:
  int _failures;
};

// 用途：以二进制方式读取完整文件，避免 Windows 文本换行转换影响 Golden 比较。
static std::string ReadWholeFile(const std::string& path)
{
  std::ifstream input(path.c_str(), std::ios::in | std::ios::binary);
  std::ostringstream content;
  content << input.rdbuf();
  return content.str();
}

// 用途：快速构造确定字段和值顺序的 FeatureRecord，供 JSONL Golden Output 测试使用。
static FeatureRecord MakeFeature(const char* id, const char* parent, long index,
                                 const char* type, const char* name, const char* decoder)
{
  FeatureRecord record;
  record.feature_id = id;
  record.parent_id = parent;
  record.traversal_index = index;
  record.fingerprint.native_type = type;
  record.fingerprint.display_name = name;
  record.fingerprint.container_kind = index == 1 ? "document" : "feature";
  record.tree_path = std::string("/") + name;
  record.update_status = "unknown";
  record.visibility = "unknown";
  record.decoder_id = decoder;
  record.decode_level = "typed";
  record.decode_status = "success";
  return record;
}

// 用途：顺序执行全部 API 无关自测并返回失败数量；0 表示所有不变量均满足。
int SelfTestSuite::RunAll()
{
  TestRunner tests;

  // 验证 ID 在单次 revision 内唯一、固定宽度且从 F000001 开始。
  FeatureIdGenerator ids;
  std::set<std::string> generated_ids;
  int i = 0;
  for (i = 0; i < 1000; ++i)
    generated_ids.insert(ids.Next());
  tests.Check(generated_ids.size() == 1000 && *generated_ids.begin() == "F000001",
              "ID generation is unique and revision-local");

  // 验证 UTF-8 字节保持不变，同时正确转义引号、反斜杠和换行。
  const std::string raw = "\xE4\xB8\xAD\xE6\x96\x87\"\\\n";
  const std::string escaped = "\xE4\xB8\xAD\xE6\x96\x87\\\"\\\\\\n";
  tests.Check(JsonEscape(raw) == escaped,
              "JSON escaping preserves UTF-8 and escapes quote slash newline");

  // 验证存在专用匹配时选择 Typed Decoder，而不是 Generic。
  ParseContext typed_context;
  FeatureTypeRegistry typed_registry;
  TypedDecoder typed_decoder("known", 20);
  typed_registry.Register(&typed_decoder);
  FeatureRecord typed;
  typed.feature_id = "F000001";
  FakeView known_view("Known");
  typed_registry.DecodeObject(known_view, typed_context, typed);
  tests.Check(typed.decoder_id == "known" && typed.decode_level == "typed",
              "Registry selects specialized decoder");

  // 验证未知对象没有专用匹配时仍产生 Generic 记录。
  ParseContext generic_context;
  FeatureTypeRegistry generic_registry;
  FeatureRecord generic;
  generic.feature_id = "F000002";
  FakeView unknown_view("Unknown");
  generic_registry.DecodeObject(unknown_view, generic_context, generic);
  tests.Check(generic.decoder_id == "generic" && generic.decode_level == "generic",
              "Unknown feature uses Generic decoder");

  // 验证连基础属性都不可读时进入 Opaque，且失败阶段被保留。
  ParseContext opaque_context;
  FeatureTypeRegistry opaque_registry;
  FeatureRecord opaque;
  opaque.feature_id = "F000003";
  FakeView unreadable_view("Unknown", false);
  opaque_registry.DecodeObject(unreadable_view, opaque_context, opaque);
  tests.Check(opaque.decoder_id == "opaque" && opaque.decode_level == "opaque" &&
              opaque.attributes["failure_stage"] == "generic",
              "Unreadable feature preserves an Opaque record");

  // 验证同优先级 Decoder 无论注册顺序如何都以稳定 ID 决胜，并产生冲突诊断。
  ParseContext tie_context_a;
  FeatureTypeRegistry tie_registry_a;
  TypedDecoder z_decoder("z", 10);
  TypedDecoder a_decoder("a", 10);
  tie_registry_a.Register(&z_decoder);
  tie_registry_a.Register(&a_decoder);
  FeatureRecord tie_a;
  tie_a.feature_id = "F000004";
  tie_registry_a.DecodeObject(known_view, tie_context_a, tie_a);

  ParseContext tie_context_b;
  FeatureTypeRegistry tie_registry_b;
  tie_registry_b.Register(&a_decoder);
  tie_registry_b.Register(&z_decoder);
  FeatureRecord tie_b;
  tie_b.feature_id = "F000004";
  tie_registry_b.DecodeObject(known_view, tie_context_b, tie_b);
  tests.Check(tie_a.decoder_id == "a" && tie_b.decoder_id == "a" &&
              !tie_context_a.diagnostics.empty() && !tie_context_b.diagnostics.empty(),
              "Equal priority conflict is deterministic and diagnosed");

  // 验证 Typed Decoder 抛异常不会越过对象边界，而会自动降级到 Generic。
  ParseContext exception_context;
  FeatureTypeRegistry exception_registry;
  TypedDecoder throwing_decoder("throwing", 50, true);
  exception_registry.Register(&throwing_decoder);
  FeatureRecord isolated;
  isolated.feature_id = "F000005";
  exception_registry.DecodeObject(known_view, exception_context, isolated);
  tests.Check(isolated.decode_level == "generic" && !exception_context.diagnostics.empty(),
              "Decoder exception is isolated and falls back to Generic");

  // 验证失败 Typed Decoder 写入的半成品不会污染随后成功的 Generic 结果。
  ParseContext dirty_context;
  FeatureTypeRegistry dirty_registry;
  DirtyFailingDecoder dirty_decoder;
  dirty_registry.Register(&dirty_decoder);
  FeatureRecord clean_fallback;
  clean_fallback.feature_id = "F000006";
  dirty_registry.DecodeObject(known_view, dirty_context, clean_fallback);
  tests.Check(clean_fallback.decode_level == "generic" &&
              clean_fallback.attributes.find("partial_typed_value") == clean_fallback.attributes.end(),
              "Failed typed decoder cannot leak partial state into Generic fallback");

  // 验证四种最终分类的算术守恒，少计任何一类都必须被发现。
  ParseStatistics valid_coverage;
  valid_coverage.enumerated_total = 4;
  valid_coverage.typed_count = 1;
  valid_coverage.generic_count = 1;
  valid_coverage.opaque_count = 1;
  valid_coverage.failed_count = 1;
  ParseStatistics invalid_coverage = valid_coverage;
  invalid_coverage.failed_count = 0;
  tests.Check(valid_coverage.IsConserved() && !invalid_coverage.IsConserved(),
              "Coverage conservation detects mismatch");

  // 验证未知类型集合去重，以及 CoverageTracker 可复用同一守恒规则。
  UnknownTypeCollector unknown_types;
  TypeFingerprint unknown_a;
  unknown_a.startup_type = "Pad";
  TypeFingerprint unknown_b = unknown_a;
  unknown_types.Observe(unknown_a);
  unknown_types.Observe(unknown_b);
  tests.Check(unknown_types.Count() == 1 && CoverageTracker::Validate(valid_coverage),
              "Unknown type collection is distinct and coverage validation is reusable");

  // 构造两节点伪对象树和一条关系，连续写入两个目录以比较确定性输出。
  std::vector<FeatureRecord> features;
  features.push_back(MakeFeature("F000001", "", 1, "Document", "demo", "document"));
  features.push_back(MakeFeature("F000002", "F000001", 2, "Part", "Part1", "part"));
  std::vector<RelationRecord> relations;
  RelationRecord relation;
  relation.kind = "parent_of";
  relation.from_id = "F000001";
  relation.to_id = "F000002";
  relations.push_back(relation);
  ParseContext output_context;
  output_context.statistics.enumerated_total = 2;
  output_context.statistics.typed_count = 2;

  JsonArtifactWriter writer(false);
  std::string write_error;
  const std::string output_a = "selftest_output_a";
  const std::string output_b = "selftest_output_b";
  const bool wrote_a = writer.Write(features, relations, output_context, output_a, write_error);
  const bool wrote_b = writer.Write(features, relations, output_context, output_b, write_error);
  tests.Check(wrote_a && wrote_b,
              "Artifact writer creates the complete output set");
  tests.Check(ReadWholeFile(output_a + "\\features.jsonl") ==
              ReadWholeFile(output_b + "\\features.jsonl") &&
              ReadWholeFile(output_a + "\\relations.jsonl") ==
              ReadWholeFile(output_b + "\\relations.jsonl"),
              "Output order is deterministic across consecutive runs");

  // Golden 文本锁定字段集合、字段顺序、对象顺序以及每行一个 JSON 对象的格式。
  const std::string expected_features =
    "{\"feature_id\":\"F000001\",\"parent_id\":\"\",\"traversal_index\":1,"
    "\"native_type\":\"Document\",\"startup_type\":\"\",\"super_types\":[],"
    "\"display_name\":\"demo\",\"internal_name\":\"\",\"container_kind\":\"document\","
    "\"tree_path\":\"/demo\",\"supported_interface_keys\":[],\"update_status\":\"unknown\","
    "\"visibility\":\"unknown\",\"decoder_id\":\"document\",\"decode_level\":\"typed\","
    "\"decode_status\":\"success\",\"attributes\":{},\"diagnostic_ids\":[]}\n"
    "{\"feature_id\":\"F000002\",\"parent_id\":\"F000001\",\"traversal_index\":2,"
    "\"native_type\":\"Part\",\"startup_type\":\"\",\"super_types\":[],"
    "\"display_name\":\"Part1\",\"internal_name\":\"\",\"container_kind\":\"feature\","
    "\"tree_path\":\"/Part1\",\"supported_interface_keys\":[],\"update_status\":\"unknown\","
    "\"visibility\":\"unknown\",\"decoder_id\":\"part\",\"decode_level\":\"typed\","
    "\"decode_status\":\"success\",\"attributes\":{},\"diagnostic_ids\":[]}\n";
  tests.Check(ReadWholeFile(output_a + "\\features.jsonl") == expected_features,
              "Fake object tree matches golden JSONL");
  tests.Check(ReadWholeFile(output_a + "\\parser.log").find(
                "decoder_match feature_id=F000001 decoder=document") != std::string::npos,
              "Parser log records deterministic decoder matches");

  // 所有 Check 都执行后一次性返回失败数，便于同一次运行看到多个独立问题。
  return tests.Failures();
}
}
