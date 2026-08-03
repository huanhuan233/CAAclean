// 本文件把纯数据 IR 序列化为 JSON/JSONL 文件，不调用任何 CATIA API。
// 所有 JSON 内容都通过集中函数输出，避免各模块手工拼接时遗漏转义或产生不稳定顺序。
#include "CadParseIR.h"

#include <direct.h>
#include <errno.h>
#include <fstream>
#include <sstream>

namespace cadparse
{
// 用途：把目录和文件名连接成 Windows 路径，同时兼容调用方已经提供的末尾斜杠。
// name 只在函数调用期间借用，返回的 std::string 拥有自己的字符数据。
static std::string JoinPath(const std::string& directory, const char* name)
{
  if (directory.empty())
    return name;
  const char last = directory[directory.size() - 1];
  return directory + ((last == '\\' || last == '/') ? "" : "\\") + name;
}

// 用途：从左到右逐级创建输出目录，已存在的目录不视为错误。
// 返回 false 时 error 包含首个无法创建的路径；函数支持盘符绝对路径和相对路径。
static bool EnsureDirectory(const std::string& path, std::string& error)
{
  if (path.empty())
  {
    error = "output directory is empty";
    return false;
  }

  std::string current;
  std::string::size_type i = 0;
  if (path.size() > 1 && path[1] == ':')
  {
    current = path.substr(0, 2);
    i = 2;
  }
  for (; i <= path.size(); ++i)
  {
    if (i < path.size() && path[i] != '\\' && path[i] != '/')
    {
      current += path[i];
      continue;
    }
    if (!current.empty() && current[current.size() - 1] != ':')
    {
      // _mkdir 只创建一级目录，因此循环必须按分隔符逐级调用；EEXIST 表示目标已存在。
      if (_mkdir(current.c_str()) != 0 && errno != EEXIST)
      {
        error = std::string("cannot create output directory: ") + current;
        return false;
      }
    }
    if (i < path.size() && (current.empty() || current[current.size() - 1] != '\\'))
      current += '\\';
  }
  return true;
}

// 用途：把字符串 vector 写成 JSON 数组；每个元素统一经过 JsonEscape。
static void WriteStringArray(std::ostream& output, const std::vector<std::string>& values)
{
  output << '[';
  std::vector<std::string>::const_iterator it = values.begin();
  for (; it != values.end(); ++it)
  {
    if (it != values.begin()) output << ',';
    output << '"' << JsonEscape(*it) << '"';
  }
  output << ']';
}

// 用途：把 string→string map 写成 JSON 对象。
// std::map 按键排序，使相同输入连续执行时字段顺序保持确定。
static void WriteStringMap(std::ostream& output, const std::map<std::string, std::string>& values)
{
  output << '{';
  std::map<std::string, std::string>::const_iterator it = values.begin();
  for (; it != values.end(); ++it)
  {
    if (it != values.begin()) output << ',';
    output << '"' << JsonEscape(it->first) << "\":\"" << JsonEscape(it->second) << '"';
  }
  output << '}';
}

// 用途：把 Decoder 命中计数等 string→long 数据写成 JSON 对象，数值不加引号。
static void WriteCountMap(std::ostream& output, const std::map<std::string, long>& values)
{
  output << '{';
  std::map<std::string, long>::const_iterator it = values.begin();
  for (; it != values.end(); ++it)
  {
    if (it != values.begin()) output << ',';
    output << '"' << JsonEscape(it->first) << "\":" << it->second;
  }
  output << '}';
}

// 用途：按 cad_parse_mvp_v0 Schema 把一个 FeatureRecord 写成完整 JSON 对象。
// 函数不写换行，因此既能服务 JSONL，也方便 Golden Output 测试精确比较。
static void WriteFeature(std::ostream& output, const FeatureRecord& record)
{
  output << "{\"feature_id\":\"" << JsonEscape(record.feature_id)
         << "\",\"parent_id\":\"" << JsonEscape(record.parent_id)
         << "\",\"traversal_index\":" << record.traversal_index
         << ",\"native_type\":\"" << JsonEscape(record.fingerprint.native_type)
         << "\",\"startup_type\":\"" << JsonEscape(record.fingerprint.startup_type)
         << "\",\"super_types\":";
  WriteStringArray(output, record.fingerprint.super_types);
  output << ",\"display_name\":\"" << JsonEscape(record.fingerprint.display_name)
         << "\",\"internal_name\":\"" << JsonEscape(record.fingerprint.internal_name)
         << "\",\"container_kind\":\"" << JsonEscape(record.fingerprint.container_kind)
         << "\",\"tree_path\":\"" << JsonEscape(record.tree_path)
         << "\",\"supported_interface_keys\":";
  WriteStringArray(output, record.fingerprint.supported_interface_keys);
  output << ",\"update_status\":\"" << JsonEscape(record.update_status)
         << "\",\"visibility\":\"" << JsonEscape(record.visibility)
         << "\",\"decoder_id\":\"" << JsonEscape(record.decoder_id)
         << "\",\"decode_level\":\"" << JsonEscape(record.decode_level)
         << "\",\"decode_status\":\"" << JsonEscape(record.decode_status)
         << "\",\"attributes\":";
  WriteStringMap(output, record.attributes);
  output << ",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：以 binary+truncate 模式创建一个新产物文件，避免 Windows 文本模式改写换行。
// 成功后 output 持有文件句柄；失败时 error 返回具体目标路径。
static bool OpenOutput(std::ofstream& output, const std::string& path, std::string& error)
{
  output.open(path.c_str(), std::ios::out | std::ios::binary | std::ios::trunc);
  if (!output)
  {
    error = std::string("cannot write output file: ") + path;
    return false;
  }
  return true;
}

// 用途：刷新并关闭一个产物文件，同时检查延迟到 flush/close 才暴露的磁盘写入错误。
// 无论 flush 是否成功都会尝试 close，避免泄漏文件句柄。
static bool FinishOutput(std::ofstream& output, const char* artifact, std::string& error)
{
  output.flush();
  if (!output)
  {
    error = std::string("write failed for artifact: ") + artifact;
    output.close();
    return false;
  }
  output.close();
  if (!output)
  {
    error = std::string("close failed for artifact: ") + artifact;
    return false;
  }
  return true;
}

// 用途：创建 JSON 写入器并记住 manifest/diagnostics 是否采用易读换行格式。
JsonArtifactWriter::JsonArtifactWriter(bool pretty) : _pretty(pretty) {}

// 用途：验证 Coverage 后，按固定顺序写出解析器要求的全部六类产物。
// 任一文件失败都会立即返回 false；已经成功关闭的前序文件会保留，便于故障诊断。
bool JsonArtifactWriter::Write(const std::vector<FeatureRecord>& features,
                               const std::vector<RelationRecord>& relations,
                               const ParseContext& context,
                               const std::string& output_dir,
                               std::string& error)
{
  // 先验证守恒再创建目录，防止把内部不一致结果伪装成成功产物。
  if (!CoverageTracker::Validate(context.statistics))
  {
    error = "coverage conservation failed";
    return false;
  }
  if (!EnsureDirectory(output_dir, error))
    return false;

  std::ofstream output;
  // features.jsonl 每行是一个可独立解析的完整 JSON 对象；vector 顺序就是稳定遍历顺序。
  if (!OpenOutput(output, JoinPath(output_dir, "features.jsonl"), error)) return false;
  std::vector<FeatureRecord>::const_iterator feature = features.begin();
  for (; feature != features.end(); ++feature)
  {
    WriteFeature(output, *feature);
    output << '\n';
  }
  if (!FinishOutput(output, "features.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "relations.jsonl"), error)) return false;
  std::vector<RelationRecord>::const_iterator relation = relations.begin();
  for (; relation != relations.end(); ++relation)
    output << "{\"kind\":\"" << JsonEscape(relation->kind) << "\",\"from_id\":\""
           << JsonEscape(relation->from_id) << "\",\"to_id\":\""
           << JsonEscape(relation->to_id) << "\"}\n";
  if (!FinishOutput(output, "relations.jsonl", error)) return false;

  const char* spacing = _pretty ? "\n  " : "";
  // pretty 只影响普通 JSON 文件的可读空白，不改变 JSONL 的“一行一对象”约定。
  if (!OpenOutput(output, JoinPath(output_dir, "manifest.json"), error)) return false;
  output << '{' << spacing << "\"schema_version\":\"cad_parse_mvp_v0\","
         << spacing << "\"feature_count\":" << features.size() << ','
         << spacing << "\"relation_count\":" << relations.size() << ','
         << spacing << "\"runtime_info\":";
  WriteStringMap(output, context.runtime_info);
  if (_pretty) output << '\n';
  output << "}\n";
  if (!FinishOutput(output, "manifest.json", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "diagnostics.json"), error)) return false;
  output << "[";
  std::vector<DiagnosticRecord>::const_iterator diagnostic = context.diagnostics.begin();
  for (; diagnostic != context.diagnostics.end(); ++diagnostic)
  {
    if (diagnostic != context.diagnostics.begin()) output << ',';
    output << "{\"diagnostic_id\":\"" << JsonEscape(diagnostic->diagnostic_id)
           << "\",\"severity\":\"" << JsonEscape(diagnostic->severity)
           << "\",\"stage\":\"" << JsonEscape(diagnostic->stage)
           << "\",\"code\":\"" << JsonEscape(diagnostic->code)
           << "\",\"message\":\"" << JsonEscape(diagnostic->message)
           << "\",\"feature_id\":\"" << JsonEscape(diagnostic->feature_id) << "\"}";
  }
  output << "]\n";
  if (!FinishOutput(output, "diagnostics.json", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "coverage.json"), error)) return false;
  // Coverage 字段显式逐项写出，避免依赖结构体内存布局或 CAA 进程状态。
  output << "{\"enumerated_total\":" << context.statistics.enumerated_total
         << ",\"typed_count\":" << context.statistics.typed_count
         << ",\"generic_count\":" << context.statistics.generic_count
         << ",\"opaque_count\":" << context.statistics.opaque_count
         << ",\"failed_count\":" << context.statistics.failed_count
         << ",\"container_count\":" << context.statistics.container_count
         << ",\"relation_count\":" << context.statistics.relation_count
         << ",\"unknown_native_type_count\":" << context.statistics.unknown_native_type_count
         << ",\"interface_probe_success_count\":" << context.statistics.interface_probe_success_count
         << ",\"interface_probe_failure_count\":" << context.statistics.interface_probe_failure_count
         << ",\"document_open_ms\":" << context.statistics.document_open_ms
         << ",\"traversal_ms\":" << context.statistics.traversal_ms
         << ",\"decoder_ms\":" << context.statistics.decoder_ms
         << ",\"output_ms\":" << context.statistics.output_ms
         << ",\"total_ms\":" << context.statistics.total_ms
         << ",\"decoder_hits\":";
  WriteCountMap(output, context.statistics.decoder_hits);
  output << "}\n";
  if (!FinishOutput(output, "coverage.json", error)) return false;

  if (!OpenOutput(output, JoinPath(output_dir, "parser.log"), error)) return false;
  // parser.log 是面向人的阶段摘要；JSON 产物才是稳定机器接口。
  output << "schema=cad_parse_mvp_v0\nfeatures=" << features.size()
         << "\nrelations=" << relations.size() << "\ncoverage_conserved=true\n";
  feature = features.begin();
  for (; feature != features.end(); ++feature)
    output << "decoder_match feature_id=" << feature->feature_id
           << " decoder=" << feature->decoder_id
           << " level=" << feature->decode_level
           << " status=" << feature->decode_status << '\n';
  diagnostic = context.diagnostics.begin();
  for (; diagnostic != context.diagnostics.end(); ++diagnostic)
    output << "diagnostic id=" << diagnostic->diagnostic_id
           << " stage=" << diagnostic->stage
           << " code=" << diagnostic->code
           << " feature_id=" << diagnostic->feature_id
           << " message=" << JsonEscape(diagnostic->message) << '\n';
  if (!FinishOutput(output, "parser.log", error)) return false;
  return true;
}
}
