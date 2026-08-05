// 本文件把纯数据 IR 事务式序列化为 JSON/JSONL；请求目录只会出现完整的一套结果。
#include "CadParseIR.h"

#include <direct.h>
#include <errno.h>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <windows.h>

namespace cadparse
{
namespace
{
// 用途：连接 Windows 目录与产物文件名，并兼容末尾已有分隔符的目录。
std::string JoinPath(const std::string& directory, const char* name)
{
  if (directory.empty()) return name;
  const char last = directory[directory.size() - 1];
  return directory + ((last == '\\' || last == '/') ? "" : "\\") + name;
}

// 用途：从左到右逐级创建目录；已存在目录不视为错误。
bool EnsureDirectory(const std::string& path, std::string& error)
{
  if (path.empty()) { error = "output directory is empty"; return false; }
  std::string current;
  std::string::size_type i = 0;
  if (path.size() > 1 && path[1] == ':') { current = path.substr(0, 2); i = 2; }
  for (; i <= path.size(); ++i)
  {
    if (i < path.size() && path[i] != '\\' && path[i] != '/') { current += path[i]; continue; }
    if (!current.empty() && current[current.size() - 1] != ':' &&
        _mkdir(current.c_str()) != 0 && errno != EEXIST)
    { error = std::string("cannot create output directory: ") + current; return false; }
    if (i < path.size() && (current.empty() || current[current.size() - 1] != '\\')) current += '\\';
  }
  return true;
}

// 用途：递归删除仅由本 Writer 生成的 staging/backup 目录，支持事务清理和回滚。
bool RemoveTree(const std::string& path)
{
  const DWORD attributes = GetFileAttributesA(path.c_str());
  if (attributes == INVALID_FILE_ATTRIBUTES) return true;
  if (!(attributes & FILE_ATTRIBUTE_DIRECTORY))
  {
    SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_NORMAL);
    return DeleteFileA(path.c_str()) != 0 || GetLastError() == ERROR_FILE_NOT_FOUND;
  }
  WIN32_FIND_DATAA data;
  HANDLE find = FindFirstFileA(JoinPath(path, "*").c_str(), &data);
  if (find != INVALID_HANDLE_VALUE)
  {
    do
    {
      const std::string name = data.cFileName;
      if (name == "." || name == "..") continue;
      const std::string child = JoinPath(path, name.c_str());
      if (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) RemoveTree(child);
      else { SetFileAttributesA(child.c_str(), FILE_ATTRIBUTE_NORMAL); DeleteFileA(child.c_str()); }
    } while (FindNextFileA(find, &data));
    FindClose(find);
  }
  SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_NORMAL);
  return RemoveDirectoryA(path.c_str()) != 0 || GetLastError() == ERROR_PATH_NOT_FOUND;
}

// 用途：原子切换 staging 和正式目录；旧结果先改名为 backup，失败时可恢复。
bool CommitStaging(const std::string& staging, const std::string& output_dir, std::string& error)
{
  const std::string backup = output_dir + ".cadparse_backup";
  RemoveTree(backup);
  const bool had_output = GetFileAttributesA(output_dir.c_str()) != INVALID_FILE_ATTRIBUTES;
  if (had_output && !MoveFileA(output_dir.c_str(), backup.c_str()))
  { error = "cannot move previous output to transaction backup"; return false; }
  if (!MoveFileA(staging.c_str(), output_dir.c_str()))
  {
    if (had_output) MoveFileA(backup.c_str(), output_dir.c_str());
    error = "cannot commit transaction staging directory";
    return false;
  }
  if (had_output) RemoveTree(backup);
  return true;
}

// 用途：把字符串数组按现有顺序写成 JSON，所有元素统一转义。
void WriteStringArray(std::ostream& output, const std::vector<std::string>& values)
{
  output << '[';
  std::vector<std::string>::const_iterator it = values.begin();
  for (; it != values.end(); ++it) { if (it != values.begin()) output << ','; output << '"' << JsonEscape(*it) << '"'; }
  output << ']';
}

// 用途：把稳定排序的 string→string map 写成 JSON 对象。
void WriteStringMap(std::ostream& output, const std::map<std::string, std::string>& values)
{
  output << '{';
  std::map<std::string, std::string>::const_iterator it = values.begin();
  for (; it != values.end(); ++it) { if (it != values.begin()) output << ','; output << '"' << JsonEscape(it->first) << "\":\"" << JsonEscape(it->second) << '"'; }
  output << '}';
}

// 用途：把稳定排序的 string→long map 写成 JSON 对象。
void WriteCountMap(std::ostream& output, const std::map<std::string, long>& values)
{
  output << '{';
  std::map<std::string, long>::const_iterator it = values.begin();
  for (; it != values.end(); ++it) { if (it != values.begin()) output << ','; output << '"' << JsonEscape(it->first) << "\":" << it->second; }
  output << '}';
}

// 用途：写出可空数值，避免用 0 冒充没有规范化结果。
void WriteOptionalNumber(std::ostream& output, bool present, double value)
{
  if (present) output << std::setprecision(15) << value; else output << "null";
}

// 用途：写出可空字符串；合法空字符串仍输出 ""，未取得字段才输出 null。
void WriteOptionalString(std::ostream& output, const OptionalNativeHoleString& value)
{
  if (value.has_value) output << '"' << JsonEscape(value.value) << '"';
  else output << "null";
}

// 用途：写出 Native Hole 的纯数据载荷，保持 number/boolean/array/null 的 JSON 类型。
void WriteNativeHole(std::ostream& output, const NativeHoleData& hole)
{
  output << "{\"semantic_kind\":\"" << JsonEscape(hole.semantic_kind)
         << "\",\"value_source\":\"" << JsonEscape(hole.value_source)
         << "\",\"interface_key\":\"" << JsonEscape(hole.interface_key)
         << "\",\"hole_type\":\"" << JsonEscape(hole.hole_type)
         << "\",\"hole_type_raw\":" << hole.hole_type_raw
         << ",\"diameter_mm\":" << std::setprecision(15) << hole.diameter_mm
         << ",\"origin_mm\":[" << hole.origin_mm[0] << ',' << hole.origin_mm[1]
         << ',' << hole.origin_mm[2] << "]"
         << ",\"direction\":[" << hole.direction[0] << ',' << hole.direction[1]
         << ',' << hole.direction[2] << "]"
         << ",\"bottom_limit\":{\"mode\":\"" << JsonEscape(hole.bottom_limit.mode)
         << "\",\"mode_raw\":" << hole.bottom_limit.mode_raw << ",\"depth_mm\":";
  WriteOptionalNumber(output, hole.bottom_limit.depth_mm.has_value,
                      hole.bottom_limit.depth_mm.value);
  output << ",\"depth_status\":\"" << JsonEscape(hole.bottom_limit.depth_mm.status)
         << "\"},\"head\":{\"kind\":\"" << JsonEscape(hole.head.kind)
         << "\",\"diameter_mm\":";
  WriteOptionalNumber(output, hole.head.diameter_mm.has_value, hole.head.diameter_mm.value);
  output << ",\"diameter_status\":\"" << JsonEscape(hole.head.diameter_mm.status)
         << "\",\"depth_mm\":";
  WriteOptionalNumber(output, hole.head.depth_mm.has_value, hole.head.depth_mm.value);
  output << ",\"depth_status\":\"" << JsonEscape(hole.head.depth_mm.status)
         << "\",\"angle_deg\":";
  WriteOptionalNumber(output, hole.head.angle_deg.has_value, hole.head.angle_deg.value);
  output << ",\"angle_status\":\"" << JsonEscape(hole.head.angle_deg.status)
         << "\"},\"thread\":{\"enabled\":" << (hole.thread.enabled ? "true" : "false")
         << ",\"mode_raw\":" << hole.thread.mode_raw << ",\"description\":";
  WriteOptionalString(output, hole.thread.description);
  output << ",\"description_status\":\"" << JsonEscape(hole.thread.description.status)
         << "\",\"diameter_mm\":";
  WriteOptionalNumber(output, hole.thread.diameter_mm.has_value, hole.thread.diameter_mm.value);
  output << ",\"diameter_status\":\"" << JsonEscape(hole.thread.diameter_mm.status)
         << "\",\"depth_mm\":";
  WriteOptionalNumber(output, hole.thread.depth_mm.has_value, hole.thread.depth_mm.value);
  output << ",\"depth_status\":\"" << JsonEscape(hole.thread.depth_mm.status)
         << "\",\"pitch_mm\":";
  WriteOptionalNumber(output, hole.thread.pitch_mm.has_value, hole.thread.pitch_mm.value);
  output << ",\"pitch_status\":\"" << JsonEscape(hole.thread.pitch_mm.status)
         << "\"},\"automation_alias\":";
  if (hole.has_automation_alias)
    output << '"' << JsonEscape(hole.automation_alias) << '"';
  else
    output << "null";
  output << ",\"automation_alias_status\":\"" << JsonEscape(hole.automation_alias_status)
         << "\",\"field_status\":";
  WriteStringMap(output, hole.field_status);
  output << '}';
}

// 用途：写出 Prism 终止边界，区分真实尺寸值、不适用和不可访问状态。
void WriteNativePrismLimit(std::ostream& output, const NativePrismLimitData& limit)
{
  output << "{\"mode\":\"" << JsonEscape(limit.mode)
         << "\",\"mode_raw\":" << limit.mode_raw
         << ",\"dimension_mm\":";
  WriteOptionalNumber(output, limit.dimension_mm.has_value, limit.dimension_mm.value);
  output << ",\"dimension_status\":\"" << JsonEscape(limit.dimension_mm.status)
         << "\",\"limiting_element_status\":\""
         << JsonEscape(limit.limiting_element_status) << "\"}";
}

// 用途：写出 Native Pad/Pocket 的 Prism 载荷，所有数值保持 JSON number/null 类型。
void WriteNativePrism(std::ostream& output, const NativePrismData& prism)
{
  output << "{\"semantic_kind\":\"" << JsonEscape(prism.semantic_kind)
         << "\",\"material_operation\":\"" << JsonEscape(prism.material_operation)
         << "\",\"value_source\":\"" << JsonEscape(prism.value_source)
         << "\",\"interface_key\":\"" << JsonEscape(prism.interface_key)
         << "\",\"direction_type\":\"" << JsonEscape(prism.direction_type)
         << "\",\"direction_type_raw\":" << prism.direction_type_raw
         << ",\"direction_orientation\":\"" << JsonEscape(prism.direction_orientation)
         << "\",\"direction_orientation_raw\":" << prism.direction_orientation_raw
         << ",\"direction\":[" << std::setprecision(15) << prism.direction[0] << ','
         << prism.direction[1] << ',' << prism.direction[2] << "]"
         << ",\"is_symmetric\":" << (prism.is_symmetric ? "true" : "false")
         << ",\"is_thin\":" << (prism.is_thin ? "true" : "false")
         << ",\"neutral_fiber\":" << (prism.neutral_fiber ? "true" : "false")
         << ",\"merge_end\":" << (prism.merge_end ? "true" : "false")
         << ",\"first_limit\":";
  WriteNativePrismLimit(output, prism.first_limit);
  output << ",\"second_limit\":";
  WriteNativePrismLimit(output, prism.second_limit);
  output << ",\"field_status\":";
  WriteStringMap(output, prism.field_status);
  output << '}';
}

// 用途：写出 Feature 内嵌的 String 参数结果；该字段仍属于原始 CAA 对象。
void WriteParameterValue(std::ostream& output, const ParameterValueData& parameter)
{
  output << "{\"parameter_kind\":\"" << JsonEscape(parameter.parameter_kind)
         << "\",\"parameter_name\":\"" << JsonEscape(parameter.parameter_name)
         << "\",\"value_status\":\"" << JsonEscape(parameter.value_status)
         << "\",\"value_source\":\"" << JsonEscape(parameter.value_source)
         << "\",\"value_text\":\"" << JsonEscape(parameter.value_text)
         << "\",\"raw_display_text\":\"" << JsonEscape(parameter.raw_display_text)
         << "\",\"normalized_numeric_value\":";
  WriteOptionalNumber(output, parameter.has_normalized_numeric_value, parameter.normalized_numeric_value);
  output << ",\"normalized_unit\":\"" << JsonEscape(parameter.normalized_unit)
         << "\",\"normalization_status\":\"" << JsonEscape(parameter.normalization_status)
         << "\",\"is_read_only\":\"" << JsonEscape(parameter.is_read_only)
         << "\",\"is_hidden\":\"" << JsonEscape(parameter.is_hidden) << "\"}";
}

// 用途：按 cad_parse_mvp_v2 Schema 写一个 Feature，不包含任何原生指针或句柄。
void WriteFeature(std::ostream& output, const FeatureRecord& record)
{
  output << "{\"feature_id\":\"" << JsonEscape(record.feature_id)
         << "\",\"parent_id\":\"" << JsonEscape(record.parent_id)
         << "\",\"native_enumeration_index\":" << record.native_enumeration_index
         << ",\"container_enumeration_index\":" << record.container_enumeration_index
         << ",\"traversal_index\":" << record.traversal_index
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
         << "\",\"decoder_version\":\"" << JsonEscape(record.decoder_version)
         << "\",\"decode_level\":\"" << JsonEscape(record.decode_level)
         << "\",\"decode_status\":\"" << JsonEscape(record.decode_status)
         << "\",\"attributes\":";
  WriteStringMap(output, record.attributes);
  if (record.has_parameter) { output << ",\"parameter\":"; WriteParameterValue(output, record.parameter); }
  // 类型化载荷自行写出完整属性，中央 Writer 无需知道 Synthetic、Hole 或后续特征类型。
  if (record.GetTypedPayload())
  {
    output << ',';
    record.GetTypedPayload()->WriteJsonProperty(output);
  }
  output << ",\"diagnostic_ids\":"; WriteStringArray(output, record.diagnostic_ids); output << '}';
}

// 用途：把每个实际遍历到的 CAA 规格对象投影为原生特征出口记录；未有专用 Decoder 的对象如实标记 generic，绝不伪造拓扑结果。
void WriteNativeFeature(std::ostream& output, const FeatureRecord& record)
{
  const ITypedPayload* payload = record.GetTypedPayload();
  const bool is_native_hole = payload && std::string(payload->GetPayloadTypeId()) == "native_hole";
  const bool is_native_prism = payload && std::string(payload->GetPayloadTypeId()) == "native_prism";
  std::string canonical_native_type;
  if (is_native_hole) canonical_native_type = "hole";
  else if (is_native_prism && record.decoder_id == "NativePadDecoder") canonical_native_type = "pad";
  else if (is_native_prism && record.decoder_id == "NativePocketDecoder") canonical_native_type = "pocket";
  const char* decoder_status = record.decode_level == "typed" ? "decoded" :
    (record.decode_level == "generic" ? "generic" :
     (record.decode_level == "opaque" ? "unsupported" : "failed"));
  output << "{\"native_feature_id\":\"" << JsonEscape(record.feature_id)
         << "\",\"source_object_id\":\"" << JsonEscape(record.feature_id)
         << "\",\"part_id\":\"\",\"instance_id\":null,\"body_id\":\"\""
         << ",\"parent_feature_id\":";
  if (record.parent_id.empty()) output << "null";
  else output << '"' << JsonEscape(record.parent_id) << '"';
  output << ",\"name\":\"" << JsonEscape(record.fingerprint.display_name)
         << "\",\"startup_type\":\"" << JsonEscape(record.fingerprint.startup_type)
         << "\",\"canonical_native_type\":\"" << JsonEscape(canonical_native_type)
         << "\",\"decoder\":\"" << JsonEscape(record.decoder_id)
         << "\",\"decoder_status\":\"" << decoder_status
         << "\",\"suppressed\":false,\"active\":true,\"parameters\":{}"
         << ",\"references\":[],\"result_topology_refs\":[]"
         << ",\"update_status\":\"" << JsonEscape(record.update_status)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  if (is_native_hole || is_native_prism)
  {
    output << ',';
    payload->WriteJsonProperty(output);
  }
  output << '}';
}

// 用途：写出一个 CAA 原生结果体摘要；它不是规格树 Feature，不参与对象守恒计数。
void WriteNativeTopologyBody(std::ostream& output, const NativeTopologyBodyRecord& record)
{
  output << "{\"body_id\":\"" << JsonEscape(record.body_id)
         << "\",\"source_feature_id\":\"" << JsonEscape(record.source_feature_id)
         << "\",\"source_kind\":\"" << JsonEscape(record.source_kind)
         << "\",\"read_status\":\"" << JsonEscape(record.read_status)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"vertex_count\":" << record.vertex_count
         << ",\"edge_count\":" << record.edge_count
         << ",\"face_count\":" << record.face_count
         << ",\"volume_count\":" << record.volume_count
         << ",\"stability_scope\":\"" << JsonEscape(record.stability_scope)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出一个 CAA 原生拓扑单元摘要；cell_id 是本次解析内稳定编号，不是 CATIA 指针。
void WriteNativeTopologyCell(std::ostream& output, const NativeTopologyCellRecord& record)
{
  output << "{\"cell_id\":\"" << JsonEscape(record.cell_id)
         << "\",\"body_id\":\"" << JsonEscape(record.body_id)
         << "\",\"cell_kind\":\"" << JsonEscape(record.cell_kind)
         << "\",\"topology_index\":" << record.topology_index
         << ",\"dimension\":" << record.dimension
         << ",\"domain_count\":" << record.domain_count
         << ",\"internal_domain_count\":" << record.internal_domain_count
         << ",\"center_mm\":";
  if (record.has_center)
    output << '[' << std::setprecision(15) << record.center_mm[0] << ','
           << record.center_mm[1] << ',' << record.center_mm[2] << ']';
  else
    output << "null";
  output << ",\"area_mm2\":";
  WriteOptionalNumber(output, record.area_mm2_available, record.area_mm2);
  output << ",\"length_mm\":";
  WriteOptionalNumber(output, record.length_mm_available, record.length_mm);
  output << ",\"geometry_status\":\"" << JsonEscape(record.geometry_status)
         << "\",\"measure_status\":\"" << JsonEscape(record.measure_status)
         << "\",\"boundary_cell_ids\":";
  WriteStringArray(output, record.boundary_cell_ids);
  output << ",\"adjacent_cell_ids\":";
  WriteStringArray(output, record.adjacent_cell_ids);
  output
         << ",\"stable_id_method\":\"" << JsonEscape(record.stable_id_method)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出 Face 边界 Loop/Wire 摘要，保留其所属 Face 和边集合。
void WriteNativeTopologyWire(std::ostream& output, const NativeTopologyWireRecord& record)
{
  output << "{\"wire_id\":\"" << JsonEscape(record.wire_id)
         << "\",\"body_id\":\"" << JsonEscape(record.body_id)
         << "\",\"wire_index\":" << record.wire_index
         << ",\"wire_kind\":\"" << JsonEscape(record.wire_kind)
         << "\",\"owning_face_id\":\"" << JsonEscape(record.owning_face_id)
         << "\",\"owning_face_topology_index\":" << record.owning_face_topology_index
         << ",\"edge_count\":" << record.edge_count
         << ",\"closed_status\":\"" << JsonEscape(record.closed_status)
         << "\",\"edge_cell_ids\":";
  WriteStringArray(output, record.edge_cell_ids);
  output << ",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出 CAA Face 到轻量化三角范围的映射摘要，供后续 GLB Writer 或 Sidecar 对齐使用。
void WriteNativeMeshFaceMap(std::ostream& output, const NativeMeshFaceMapRecord& record)
{
  output << "{\"mesh_map_id\":\"" << JsonEscape(record.mesh_map_id)
         << "\",\"body_id\":\"" << JsonEscape(record.body_id)
         << "\",\"face_cell_id\":\"" << JsonEscape(record.face_cell_id)
         << "\",\"primitive_index\":" << record.primitive_index
         << ",\"triangle_start\":" << record.triangle_start
         << ",\"triangle_count\":" << record.triangle_count
         << ",\"point_count\":" << record.point_count
         << ",\"isolated_triangle_count\":" << record.isolated_triangle_count
         << ",\"strip_count\":" << record.strip_count
         << ",\"fan_count\":" << record.fan_count
         << ",\"polygon_count\":" << record.polygon_count
         << ",\"estimated_triangle_count\":" << record.estimated_triangle_count
         << ",\"face_orientation_side\":" << record.face_orientation_side
         << ",\"planar\":" << (record.planar ? "true" : "false")
         << ",\"tessellation_status\":\"" << JsonEscape(record.tessellation_status)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出一个 FTA/TPS Set 摘要；它只表示原生标注集合事实，不表示已完成语义解析或拓扑映射。
void WriteFtaSet(std::ostream& output, const FtaSetRecord& record)
{
  output << "{\"fta_set_id\":\"" << JsonEscape(record.fta_set_id)
         << "\",\"set_index\":" << record.set_index
         << ",\"read_status\":\"" << JsonEscape(record.read_status)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"tps_count\":" << record.tps_count
         << ",\"geometry_count\":" << record.geometry_count
         << ",\"semantic_detail_status\":\"" << JsonEscape(record.semantic_detail_status)
         << "\",\"topology_mapping_status\":\"" << JsonEscape(record.topology_mapping_status)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出一个 TPS 组件级语义观测；该记录不包含未验证的逐类 GD&T 参数。
void WriteFtaSemantic(std::ostream& output, const FtaSemanticRecord& record)
{
  output << "{\"fta_semantic_id\":\"" << JsonEscape(record.fta_semantic_id)
         << "\",\"fta_set_id\":\"" << JsonEscape(record.fta_set_id)
         << "\",\"component_index\":" << record.component_index
         << ",\"read_status\":\"" << JsonEscape(record.read_status)
         << "\",\"component_kind\":\"" << JsonEscape(record.component_kind)
         << "\",\"supported_interface_keys\":";
  WriteStringArray(output, record.supported_interface_keys);
  output << ",\"semantic_interface_count\":" << record.semantic_interface_count
         << ",\"all_semantic_interface_count\":" << record.all_semantic_interface_count
         << ",\"validation_text\":\"" << JsonEscape(record.validation_text)
         << "\",\"validation_text_status\":\"" << JsonEscape(record.validation_text_status)
         << "\",\"semantic_check_status_raw\":" << record.semantic_check_status_raw
         << ",\"semantic_check_diagnostic\":\"" << JsonEscape(record.semantic_check_diagnostic)
         << "\",\"topology_mapping_status\":\"" << JsonEscape(record.topology_mapping_status)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出一个原生设计特征 ResultOUT 拓扑摘要；它不等同于最终主实体 Face 映射。
void WriteNativeFeatureResult(std::ostream& output, const NativeFeatureResultRecord& record)
{
  output << "{\"result_id\":\"" << JsonEscape(record.result_id)
         << "\",\"source_feature_id\":\"" << JsonEscape(record.source_feature_id)
         << "\",\"source_kind\":\"" << JsonEscape(record.source_kind)
         << "\",\"read_status\":\"" << JsonEscape(record.read_status)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"vertex_count\":" << record.vertex_count
         << ",\"edge_count\":" << record.edge_count
         << ",\"face_count\":" << record.face_count
         << ",\"volume_count\":" << record.volume_count
         << ",\"final_body_mapping_status\":\"" << JsonEscape(record.final_body_mapping_status)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出一个 ResultOUT cell 明细；它是原生特征结果体拓扑，不是最终主实体 Face 的替代品。
void WriteNativeFeatureResultCell(std::ostream& output, const NativeFeatureResultCellRecord& record)
{
  output << "{\"result_cell_id\":\"" << JsonEscape(record.result_cell_id)
         << "\",\"result_id\":\"" << JsonEscape(record.result_id)
         << "\",\"source_feature_id\":\"" << JsonEscape(record.source_feature_id)
         << "\",\"source_kind\":\"" << JsonEscape(record.source_kind)
         << "\",\"result_cell_index\":" << record.result_cell_index
         << ",\"dimension\":" << record.dimension
         << ",\"cell_kind\":\"" << JsonEscape(record.cell_kind)
         << "\",\"center_mm\":";
  if (record.has_center)
    output << '[' << std::setprecision(15) << record.center_mm[0] << ','
           << record.center_mm[1] << ',' << record.center_mm[2] << ']';
  else
    output << "null";
  output << ",\"area_mm2\":";
  WriteOptionalNumber(output, record.area_mm2_available, record.area_mm2);
  output << ",\"length_mm\":";
  WriteOptionalNumber(output, record.length_mm_available, record.length_mm);
  output << ",\"boundary_result_cell_ids\":";
  WriteStringArray(output, record.boundary_result_cell_ids);
  output << ",\"read_status\":\"" << JsonEscape(record.read_status)
         << "\",\"stable_id_method\":\"" << JsonEscape(record.stable_id_method)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写出 ResultOUT cell 到最终 Face 的候选映射尝试；candidate 不等于已完成权威映射。
void WriteNativeFeatureTopologyLink(std::ostream& output, const NativeFeatureTopologyLinkRecord& record)
{
  output << "{\"link_id\":\"" << JsonEscape(record.link_id)
         << "\",\"source_feature_id\":\"" << JsonEscape(record.source_feature_id)
         << "\",\"result_id\":\"" << JsonEscape(record.result_id)
         << "\",\"result_cell_id\":\"" << JsonEscape(record.result_cell_id)
         << "\",\"final_cell_id\":\"" << JsonEscape(record.final_cell_id)
         << "\",\"final_body_id\":\"" << JsonEscape(record.final_body_id)
         << "\",\"mapping_direction\":\"" << JsonEscape(record.mapping_direction)
         << "\",\"mapping_status\":\"" << JsonEscape(record.mapping_status)
         << "\",\"mapping_method\":\"" << JsonEscape(record.mapping_method)
         << "\",\"confidence\":" << std::setprecision(15) << record.confidence
         << ",\"center_residual_mm\":" << record.center_residual_mm
         << ",\"measure_residual\":" << record.measure_residual
         << ",\"candidate_count\":" << record.candidate_count
         << ",\"candidate_final_cell_ids\":";
  WriteStringArray(output, record.candidate_final_cell_ids);
  output << ",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids);
  output << '}';
}

// 用途：写一条参数消费索引，parameter_id 始终复用原 Feature ID。
void WriteParameter(std::ostream& output, const ParameterRecord& record)
{
  output << "{\"parameter_id\":\"" << JsonEscape(record.parameter_id)
         << "\",\"owner_feature_id\":\"" << JsonEscape(record.owner_feature_id)
         << "\",\"parent_id\":\"" << JsonEscape(record.parent_id)
         << "\",\"tree_path\":\"" << JsonEscape(record.tree_path)
         << "\",\"parameter_name\":\"" << JsonEscape(record.parameter_name)
         << "\",\"parameter_kind\":\"" << JsonEscape(record.parameter_kind)
         << "\",\"value_status\":\"" << JsonEscape(record.value_status)
         << "\",\"value_source\":\"" << JsonEscape(record.value_source)
         << "\",\"value_text\":\"" << JsonEscape(record.value_text)
         << "\",\"raw_display_text\":\"" << JsonEscape(record.raw_display_text)
         << "\",\"normalized_numeric_value\":";
  WriteOptionalNumber(output, record.has_normalized_numeric_value, record.normalized_numeric_value);
  output << ",\"normalized_unit\":\"" << JsonEscape(record.normalized_unit)
         << "\",\"normalization_status\":\"" << JsonEscape(record.normalization_status)
         << "\",\"decoder_id\":\"" << JsonEscape(record.decoder_id)
         << "\",\"ownership_status\":\"" << JsonEscape(record.ownership_status)
         << "\",\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids); output << '}';
}

// 用途：写一条声明式业务特征及其来源证据，明确没有执行几何识别。
void WriteBusinessFeature(std::ostream& output, const BusinessFeatureRecord& record)
{
  output << "{\"business_feature_id\":\"" << JsonEscape(record.business_feature_id)
         << "\",\"source_feature_id\":\"" << JsonEscape(record.source_feature_id)
         << "\",\"feature_kind\":\"" << JsonEscape(record.feature_kind)
         << "\",\"display_name\":\"" << JsonEscape(record.display_name)
         << "\",\"normalized_name\":\"" << JsonEscape(record.normalized_name)
         << "\",\"recognition_method\":\"" << JsonEscape(record.recognition_method)
         << "\",\"classification_status\":\"" << JsonEscape(record.classification_status)
         << "\",\"confidence\":\"" << JsonEscape(record.confidence)
         << "\",\"container_id\":\"" << JsonEscape(record.container_id)
         << "\",\"tree_path\":\"" << JsonEscape(record.tree_path)
         << "\",\"parameter_ids\":";
  WriteStringArray(output, record.parameter_ids);
  output << ",\"parameters\":{";
  std::map<std::string, BusinessParameterData>::const_iterator parameter = record.parameters.begin();
  for (; parameter != record.parameters.end(); ++parameter)
  {
    if (parameter != record.parameters.begin()) output << ',';
    output << '"' << JsonEscape(parameter->first) << "\":{\"parameter_id\":\""
           << JsonEscape(parameter->second.parameter_id) << "\",\"raw_value\":\""
           << JsonEscape(parameter->second.raw_value) << "\",\"normalized_numeric_value\":";
    WriteOptionalNumber(output, parameter->second.has_normalized_numeric_value,
                        parameter->second.normalized_numeric_value);
    output << ",\"normalized_unit\":\"" << JsonEscape(parameter->second.normalized_unit)
           << "\",\"value_status\":\"" << JsonEscape(parameter->second.value_status) << "\"}";
  }
  output << "},\"evidence\":[";
  std::vector<BusinessFeatureEvidence>::const_iterator evidence = record.evidence.begin();
  for (; evidence != record.evidence.end(); ++evidence)
  {
    if (evidence != record.evidence.begin()) output << ',';
    output << "{\"kind\":\"" << JsonEscape(evidence->kind) << "\",\"value\":\""
           << JsonEscape(evidence->value) << "\"}";
  }
  output << "],\"geometry_recognition_performed\":false,"
         << "\"native_part_design_feature_confirmed\":false,\"diagnostic_ids\":";
  WriteStringArray(output, record.diagnostic_ids); output << '}';
}

// 用途：以 binary+truncate 打开 staging 产物，失败时返回明确文件路径。
bool OpenOutput(std::ofstream& output, const std::string& path, std::string& error)
{
  output.open(path.c_str(), std::ios::out | std::ios::binary | std::ios::trunc);
  if (!output) { error = std::string("cannot write output file: ") + path; return false; }
  return true;
}

// 用途：刷新并关闭产物，同时检查延迟到 flush/close 才暴露的磁盘错误。
bool FinishOutput(std::ofstream& output, const char* artifact, std::string& error)
{
  output.flush();
  if (!output) { error = std::string("write failed for artifact: ") + artifact; output.close(); return false; }
  output.close();
  if (!output) { error = std::string("close failed for artifact: ") + artifact; return false; }
  return true;
}

// 用途：返回文件字节数；Manifest 产物统计使用磁盘实际值而不是内存估算。
unsigned long FileSize(const std::string& path)
{
  WIN32_FILE_ATTRIBUTE_DATA data;
  if (!GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &data)) return 0;
  return data.nFileSizeLow;
}

// 用途：在写盘前验证所有关系和派生索引都能反查原始 Feature，禁止悬空引用进入正式结果。
bool ValidateReferences(const std::vector<FeatureRecord>& features,
                        const std::vector<RelationRecord>& relations,
                        const std::vector<ParameterRecord>& parameters,
                        const std::vector<BusinessFeatureRecord>& business_features,
                        std::string& error)
{
  std::set<std::string> feature_ids;
  std::vector<FeatureRecord>::const_iterator feature = features.begin();
  for (; feature != features.end(); ++feature) feature_ids.insert(feature->feature_id);
  std::vector<RelationRecord>::const_iterator relation = relations.begin();
  for (; relation != relations.end(); ++relation)
    if (feature_ids.find(relation->from_id) == feature_ids.end() ||
        feature_ids.find(relation->to_id) == feature_ids.end())
    { error = "relation endpoint does not exist in features"; return false; }
  std::vector<ParameterRecord>::const_iterator parameter = parameters.begin();
  for (; parameter != parameters.end(); ++parameter)
  {
    if (feature_ids.find(parameter->parameter_id) == feature_ids.end())
    { error = "parameter_id does not exist in features"; return false; }
    if (!parameter->owner_feature_id.empty() &&
        feature_ids.find(parameter->owner_feature_id) == feature_ids.end())
    { error = "parameter owner_feature_id does not exist in features"; return false; }
  }
  std::vector<BusinessFeatureRecord>::const_iterator business = business_features.begin();
  for (; business != business_features.end(); ++business)
  {
    if (feature_ids.find(business->source_feature_id) == feature_ids.end())
    { error = "business source_feature_id does not exist in features"; return false; }
    std::vector<std::string>::const_iterator id = business->parameter_ids.begin();
    for (; id != business->parameter_ids.end(); ++id)
      if (feature_ids.find(*id) == feature_ids.end())
      { error = "business parameter_id does not exist in features"; return false; }
  }
  return true;
}
}

// 用途：让原生孔载荷自行写出兼容的 native_hole 属性，中央 Writer 不包含类型判断。
void NativeHolePayload::WriteJsonProperty(std::ostream& output) const
{
  output << "\"native_hole\":";
  WriteNativeHole(output, _data);
}

// 用途：让 Pad/Pocket 的 Prism 载荷自行写出 native_prism 属性，中央 Writer 不包含类型分支。
void NativePrismPayload::WriteJsonProperty(std::ostream& output) const
{
  output << "\"native_prism\":";
  WriteNativePrism(output, _data);
}

// 用途：创建 JSON Writer 并保存普通 JSON 是否采用易读空白。
JsonArtifactWriter::JsonArtifactWriter(bool pretty) : _pretty(pretty) {}

// 用途：为简单调用方建立参数/业务派生索引，再调用完整事务写出入口。
bool JsonArtifactWriter::Write(const std::vector<FeatureRecord>& features,
                               const std::vector<RelationRecord>& relations,
                               ParseContext& context,
                               const std::string& output_dir,
                               std::string& error)
{
  std::vector<ParameterRecord> parameters;
  std::vector<BusinessFeatureRecord> business_features;
  ParameterRecordBuilder::Build(features, relations, context, parameters);
  DeclaredBusinessFeatureAggregator::Aggregate(features, relations, parameters, context, business_features);
  return Write(features, relations, parameters, business_features, context, output_dir, error);
}

// 用途：一次写完 staging、计算统计与哈希、最后生成 Coverage/Manifest，再原子提交目录。
bool JsonArtifactWriter::Write(const std::vector<FeatureRecord>& features,
                               const std::vector<RelationRecord>& relations,
                               const std::vector<ParameterRecord>& parameters,
                               const std::vector<BusinessFeatureRecord>& business_features,
                               ParseContext& context,
                               const std::string& output_dir,
                               std::string& error)
{
  if (!CoverageTracker::Validate(context.statistics)) { error = "coverage conservation failed"; return false; }
  if (!ValidateReferences(features, relations, parameters, business_features, error)) return false;
  const DWORD output_start = GetTickCount();
  const std::string staging = output_dir + ".cadparse_stage";
  const DWORD existing_output = GetFileAttributesA(output_dir.c_str());
  if (existing_output != INVALID_FILE_ATTRIBUTES && !(existing_output & FILE_ATTRIBUTE_DIRECTORY))
  { error = "output path exists and is not a directory"; return false; }
  RemoveTree(staging);
  if (!EnsureDirectory(staging, error)) return false;

  std::ofstream output;
  if (!OpenOutput(output, JoinPath(staging, "features.jsonl"), error)) return false;
  std::vector<FeatureRecord>::const_iterator feature = features.begin();
  for (; feature != features.end(); ++feature) { WriteFeature(output, *feature); output << '\n'; }
  if (!FinishOutput(output, "features.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_features.jsonl"), error)) return false;
  for (feature = features.begin(); feature != features.end(); ++feature)
  { WriteNativeFeature(output, *feature); output << '\n'; }
  if (!FinishOutput(output, "native_features.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_topology_bodies.jsonl"), error)) return false;
  std::vector<NativeTopologyBodyRecord>::const_iterator topology_body =
    context.topology_bodies.begin();
  for (; topology_body != context.topology_bodies.end(); ++topology_body)
  { WriteNativeTopologyBody(output, *topology_body); output << '\n'; }
  if (!FinishOutput(output, "native_topology_bodies.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_topology_cells.jsonl"), error)) return false;
  std::vector<NativeTopologyCellRecord>::const_iterator topology_cell =
    context.topology_cells.begin();
  for (; topology_cell != context.topology_cells.end(); ++topology_cell)
  { WriteNativeTopologyCell(output, *topology_cell); output << '\n'; }
  if (!FinishOutput(output, "native_topology_cells.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_topology_wires.jsonl"), error)) return false;
  std::vector<NativeTopologyWireRecord>::const_iterator topology_wire =
    context.topology_wires.begin();
  for (; topology_wire != context.topology_wires.end(); ++topology_wire)
  { WriteNativeTopologyWire(output, *topology_wire); output << '\n'; }
  if (!FinishOutput(output, "native_topology_wires.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_mesh_face_map.jsonl"), error)) return false;
  std::vector<NativeMeshFaceMapRecord>::const_iterator mesh_face =
    context.mesh_face_maps.begin();
  for (; mesh_face != context.mesh_face_maps.end(); ++mesh_face)
  { WriteNativeMeshFaceMap(output, *mesh_face); output << '\n'; }
  if (!FinishOutput(output, "native_mesh_face_map.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "fta_sets.jsonl"), error)) return false;
  std::vector<FtaSetRecord>::const_iterator fta_set = context.fta_sets.begin();
  for (; fta_set != context.fta_sets.end(); ++fta_set)
  { WriteFtaSet(output, *fta_set); output << '\n'; }
  if (!FinishOutput(output, "fta_sets.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "fta_semantics.jsonl"), error)) return false;
  std::vector<FtaSemanticRecord>::const_iterator fta_semantic = context.fta_semantics.begin();
  for (; fta_semantic != context.fta_semantics.end(); ++fta_semantic)
  { WriteFtaSemantic(output, *fta_semantic); output << '\n'; }
  if (!FinishOutput(output, "fta_semantics.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_feature_results.jsonl"), error)) return false;
  std::vector<NativeFeatureResultRecord>::const_iterator feature_result =
    context.native_feature_results.begin();
  for (; feature_result != context.native_feature_results.end(); ++feature_result)
  { WriteNativeFeatureResult(output, *feature_result); output << '\n'; }
  if (!FinishOutput(output, "native_feature_results.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_feature_result_cells.jsonl"), error)) return false;
  std::vector<NativeFeatureResultCellRecord>::const_iterator result_cell =
    context.native_feature_result_cells.begin();
  for (; result_cell != context.native_feature_result_cells.end(); ++result_cell)
  { WriteNativeFeatureResultCell(output, *result_cell); output << '\n'; }
  if (!FinishOutput(output, "native_feature_result_cells.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "native_feature_topology_links.jsonl"), error)) return false;
  std::vector<NativeFeatureTopologyLinkRecord>::const_iterator topology_link =
    context.native_feature_topology_links.begin();
  for (; topology_link != context.native_feature_topology_links.end(); ++topology_link)
  { WriteNativeFeatureTopologyLink(output, *topology_link); output << '\n'; }
  if (!FinishOutput(output, "native_feature_topology_links.jsonl", error)) return false;

  // 用途：能力状态从本轮真实 CAA 出口推导；未实现或未验证的拓扑、FTA、映射绝不标记为完成。
  if (!OpenOutput(output, JoinPath(staging, "capabilities.json"), error)) return false;
  long native_hole_decoded = 0;
  long native_prism_decoded = 0;
  long native_generic = 0;
  for (feature = features.begin(); feature != features.end(); ++feature)
  {
    const ITypedPayload* payload = feature->GetTypedPayload();
    if (payload && std::string(payload->GetPayloadTypeId()) == "native_hole") ++native_hole_decoded;
    if (payload && std::string(payload->GetPayloadTypeId()) == "native_prism") ++native_prism_decoded;
    if (feature->decode_level == "generic") ++native_generic;
  }
  const bool has_native_topology = !context.topology_bodies.empty();
  const std::map<std::string, std::string>::const_iterator fta_status_it =
    context.runtime_info.find("fta_extraction_status");
  const std::string fta_status = fta_status_it == context.runtime_info.end() ?
    "not_available" : fta_status_it->second;
  long feature_topology_candidate_links = 0;
  std::vector<NativeFeatureTopologyLinkRecord>::const_iterator link =
    context.native_feature_topology_links.begin();
  for (; link != context.native_feature_topology_links.end(); ++link)
  {
    if (link->mapping_status == "candidate" || link->mapping_status == "ambiguous")
      ++feature_topology_candidate_links;
  }
  output << "{\"spec_tree_extraction\":\"partial\""
         << ",\"native_feature_extraction\":\"partial\""
         << ",\"topology_extraction\":\"" << (has_native_topology ? "partial" : "not_available") << "\""
         << ",\"native_feature_topology_mapping\":\""
         << (feature_topology_candidate_links > 0 ? "partial" : "not_available") << "\""
         << ",\"fta_extraction\":\"" << JsonEscape(fta_status) << "\""
         << ",\"fta_topology_mapping\":\"not_available\""
         << ",\"mesh_face_mapping\":\"" << (context.mesh_face_maps.empty() ? "not_available" : "partial") << "\""
         << ",\"manufacturing_feature_recognition\":\"not_performed\""
         << ",\"native_feature_record_count\":" << features.size()
         << ",\"native_hole_decoded_count\":" << native_hole_decoded
         << ",\"native_prism_decoded_count\":" << native_prism_decoded
         << ",\"native_generic_count\":" << native_generic
         << ",\"native_topology_body_count\":" << context.topology_bodies.size()
         << ",\"native_topology_cell_count\":" << context.topology_cells.size()
         << ",\"native_topology_wire_count\":" << context.topology_wires.size()
         << ",\"native_mesh_face_map_count\":" << context.mesh_face_maps.size()
         << ",\"fta_set_count\":" << context.fta_sets.size()
         << ",\"fta_semantic_count\":" << context.fta_semantics.size()
         << ",\"native_feature_result_count\":" << context.native_feature_results.size()
         << ",\"native_feature_result_cell_count\":" << context.native_feature_result_cells.size()
         << ",\"native_feature_topology_link_count\":" << context.native_feature_topology_links.size()
         << ",\"native_feature_topology_candidate_link_count\":" << feature_topology_candidate_links
         << ",\"notes\":[\"R21 Public CATIAHole, CATIAPad and CATIAPocket decoders are registered when their StartUp candidates expose the matching Public interface\",\"R21 Public CATIPrtPart::GetSolid and CATTopology cell enumeration emit revision-local body/cell topology when available\",\"R21 Public CATICGMBodyTessellator emits Face to triangle range evidence when tessellation succeeds\",\"R21 Public CATIShapeFeatureBody ResultOUT now emits per-cell topology evidence; final-face links are geometry-fingerprint candidates, not authoritative Generic Naming mapping\",\"R21 Public CATITPSDocument/CATITPSSet can emit FTA set-level counts when the document exposes TPS data\",\"FTA-to-topology mapping is still not emitted by this CAA revision\"]}\n";
  if (!FinishOutput(output, "capabilities.json", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "relations.jsonl"), error)) return false;
  std::vector<RelationRecord>::const_iterator relation = relations.begin();
  for (; relation != relations.end(); ++relation)
    output << "{\"kind\":\"" << JsonEscape(relation->kind) << "\",\"from_id\":\""
           << JsonEscape(relation->from_id) << "\",\"to_id\":\"" << JsonEscape(relation->to_id) << "\"}\n";
  if (!FinishOutput(output, "relations.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "parameters.jsonl"), error)) return false;
  std::vector<ParameterRecord>::const_iterator parameter = parameters.begin();
  for (; parameter != parameters.end(); ++parameter) { WriteParameter(output, *parameter); output << '\n'; }
  if (!FinishOutput(output, "parameters.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "business_features.jsonl"), error)) return false;
  std::vector<BusinessFeatureRecord>::const_iterator business = business_features.begin();
  for (; business != business_features.end(); ++business) { WriteBusinessFeature(output, *business); output << '\n'; }
  if (!FinishOutput(output, "business_features.jsonl", error)) return false;

  if (!OpenOutput(output, JoinPath(staging, "diagnostics.json"), error)) return false;
  output << '[';
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

  if (!OpenOutput(output, JoinPath(staging, "parser.log"), error)) return false;
  output << "schema=" << CAD_PARSE_SCHEMA_VERSION << "\ninput=" << JsonEscape(context.metadata.input_file_name)
         << "\nfeatures=" << features.size() << "\nparameters=" << parameters.size()
         << "\nbusiness_features=" << business_features.size() << "\ncoverage_conserved=true\n";
  feature = features.begin();
  for (; feature != features.end(); ++feature)
    output << "decoder_match feature_id=" << feature->feature_id
           << " decoder=" << feature->decoder_id << " level=" << feature->decode_level
           << " status=" << feature->decode_status << '\n';
  diagnostic = context.diagnostics.begin();
  for (; diagnostic != context.diagnostics.end(); ++diagnostic)
    output << "diagnostic id=" << diagnostic->diagnostic_id << " stage=" << diagnostic->stage
           << " code=" << diagnostic->code << " feature_id=" << diagnostic->feature_id
           << " message=" << JsonEscape(diagnostic->message) << '\n';
  if (!FinishOutput(output, "parser.log", error)) return false;

  context.statistics.output_ms = static_cast<long>(GetTickCount() - output_start);
  context.statistics.total_ms += context.statistics.output_ms;
  if (!OpenOutput(output, JoinPath(staging, "coverage.json"), error)) return false;
  output << "{\"enumerated_total\":" << context.statistics.enumerated_total
         << ",\"typed_count\":" << context.statistics.typed_count
         << ",\"generic_count\":" << context.statistics.generic_count
         << ",\"opaque_count\":" << context.statistics.opaque_count
         << ",\"failed_count\":" << context.statistics.failed_count
         << ",\"container_count\":" << context.statistics.container_count
         << ",\"relation_count\":" << context.statistics.relation_count
         << ",\"unknown_native_type_count\":" << context.statistics.unknown_native_type_count
         << ",\"probe_supported_count\":" << context.statistics.probe_supported_count
         << ",\"probe_unsupported_count\":" << context.statistics.probe_unsupported_count
         << ",\"probe_exception_count\":" << context.statistics.probe_exception_count
         << ",\"probe_not_attempted_count\":" << context.statistics.probe_not_attempted_count
         << ",\"probe_outcomes\":"; WriteCountMap(output, context.statistics.probe_outcome_counts);
  output << ",\"not_up_to_date_count\":" << context.statistics.not_up_to_date_count
         << ",\"not_up_to_date_by_native_type\":"; WriteCountMap(output, context.statistics.not_up_to_date_by_native_type);
  output << ",\"not_up_to_date_by_decoder\":"; WriteCountMap(output, context.statistics.not_up_to_date_by_decoder);
  output << ",\"not_up_to_date_feature_ids\":"; WriteStringArray(output, context.statistics.not_up_to_date_feature_ids);
  output << ",\"model_contains_stale_objects\":" << (context.statistics.not_up_to_date_count ? "true" : "false")
         << ",\"parameter_total\":" << context.statistics.parameter_total
         << ",\"parameter_value_success\":" << context.statistics.parameter_value_success
         << ",\"parameter_value_partial\":" << context.statistics.parameter_value_partial
         << ",\"parameter_value_unavailable\":" << context.statistics.parameter_value_unavailable
         << ",\"parameter_failed\":" << context.statistics.parameter_failed
         << ",\"declared_business_feature_total\":" << context.statistics.declared_business_feature_total
         << ",\"declared_boss_count\":" << context.statistics.declared_boss_count
         << ",\"declared_hole_count\":" << context.statistics.declared_hole_count
         << ",\"declared_slot_count\":" << context.statistics.declared_slot_count
         << ",\"declared_unknown_count\":" << context.statistics.declared_unknown_count
         << ",\"business_feature_with_parameter_count\":" << context.statistics.business_feature_with_parameter_count
         << ",\"business_feature_with_all_values_count\":" << context.statistics.business_feature_with_all_values_count
         << ",\"business_feature_with_partial_values_count\":" << context.statistics.business_feature_with_partial_values_count
         << ",\"business_feature_without_values_count\":" << context.statistics.business_feature_without_values_count
         << ",\"orphan_parameter_count\":" << context.statistics.orphan_parameter_count
         << ",\"ambiguous_parameter_owner_count\":" << context.statistics.ambiguous_parameter_owner_count
         << ",\"native_hole_candidate_count\":" << context.statistics.native_hole_candidate_count
         << ",\"native_hole_success_count\":" << context.statistics.native_hole_success_count
         << ",\"native_hole_partial_count\":" << context.statistics.native_hole_partial_count
         << ",\"native_hole_unsupported_count\":" << context.statistics.native_hole_unsupported_count
         << ",\"native_hole_exception_count\":" << context.statistics.native_hole_exception_count
         << ",\"document_open_ms\":" << context.statistics.document_open_ms
         << ",\"traversal_ms\":" << context.statistics.traversal_ms
         << ",\"decoder_ms\":" << context.statistics.decoder_ms
         << ",\"output_ms\":" << context.statistics.output_ms
         << ",\"total_ms\":" << context.statistics.total_ms
         << ",\"decoder_hits\":"; WriteCountMap(output, context.statistics.decoder_hits); output << "}\n";
  if (!FinishOutput(output, "coverage.json", error)) return false;

  context.metadata.execution_finished_utc = UtcNowIso8601();
  const char* names[] = { "features.jsonl", "native_features.jsonl", "native_feature_results.jsonl", "native_feature_result_cells.jsonl", "native_feature_topology_links.jsonl", "native_topology_bodies.jsonl", "native_topology_cells.jsonl", "native_topology_wires.jsonl", "native_mesh_face_map.jsonl", "fta_sets.jsonl", "fta_semantics.jsonl", "relations.jsonl", "parameters.jsonl", "business_features.jsonl", "capabilities.json", "diagnostics.json", "coverage.json", "parser.log" };
  std::map<std::string, std::string> artifact_hashes;
  std::map<std::string, unsigned long> artifact_sizes;
  int artifact = 0;
  for (; artifact < 14; ++artifact)
  {
    const std::string path = JoinPath(staging, names[artifact]);
    std::string hash_error;
    const std::string hash = Sha256File(path, hash_error);
    if (hash.empty()) { error = hash_error; return false; }
    artifact_hashes[names[artifact]] = hash;
    artifact_sizes[names[artifact]] = FileSize(path);
  }
  const char* spacing = _pretty ? "\n  " : "";
  if (!OpenOutput(output, JoinPath(staging, "manifest.json"), error)) return false;
  output << '{' << spacing << "\"schema_version\":\"" << JsonEscape(context.metadata.schema_version)
         << "\"," << spacing << "\"parser_version\":\"" << JsonEscape(context.metadata.parser_version)
         << "\"," << spacing << "\"registry_version\":\"" << JsonEscape(context.metadata.registry_version)
         << "\"," << spacing << "\"decoder_bundle_version\":\"" << JsonEscape(context.metadata.decoder_bundle_version)
         << "\"," << spacing << "\"parser_git_commit\":\"" << JsonEscape(context.metadata.parser_git_commit)
         << "\"," << spacing << "\"parser_git_commit_source\":\"" << JsonEscape(context.metadata.parser_git_commit_source)
         << "\"," << spacing << "\"build_timestamp_utc\":\"" << JsonEscape(context.metadata.build_timestamp_utc)
         << "\"," << spacing << "\"build_timestamp_source\":\"" << JsonEscape(context.metadata.build_timestamp_source)
         << "\"," << spacing << "\"execution_started_utc\":\"" << JsonEscape(context.metadata.execution_started_utc)
         << "\"," << spacing << "\"execution_finished_utc\":\"" << JsonEscape(context.metadata.execution_finished_utc)
         << "\"," << spacing << "\"input\":{\"file_name\":\"" << JsonEscape(context.metadata.input_file_name)
         << "\",\"size_bytes\":" << context.metadata.input_size_bytes
         << ",\"sha256\":\"" << JsonEscape(context.metadata.input_sha256)
         << "\",\"absolute_path_included\":" << (context.metadata.include_source_path ? "true" : "false");
  if (context.metadata.include_source_path) output << ",\"source_path\":\"" << JsonEscape(context.metadata.input_source_path) << '"';
  output << "}," << spacing << "\"runtime\":{\"catia_release\":\"" << JsonEscape(context.metadata.runtime_catia_release)
         << "\",\"service_pack\":\"" << JsonEscape(context.metadata.runtime_service_pack)
         << "\",\"hotfix\":\"" << JsonEscape(context.metadata.runtime_hotfix)
         << "\",\"value_source\":\"" << JsonEscape(context.metadata.runtime_value_source) << "\"},"
         << spacing << "\"source_file_hint\":{\"release\":\"" << JsonEscape(context.metadata.source_hint_release)
         << "\",\"service_pack\":\"" << JsonEscape(context.metadata.source_hint_service_pack)
         << "\",\"hotfix\":\"" << JsonEscape(context.metadata.source_hint_hotfix)
         << "\",\"value_source\":\"" << JsonEscape(context.metadata.source_hint_value_source)
         << "\",\"confidence\":\"" << JsonEscape(context.metadata.source_hint_confidence) << "\"},"
         << spacing << "\"discovery\":{\"entrypoints\":";
  WriteStringArray(output, context.metadata.discovery_entrypoints);
  output << ",\"coverage_scope\":\"" << JsonEscape(context.metadata.discovery_coverage_scope) << "\"},"
         << spacing << "\"model_contains_stale_objects\":" << (context.statistics.not_up_to_date_count ? "true" : "false")
         << ',' << spacing << "\"artifacts\":{";
  artifact = 0;
  for (; artifact < 11; ++artifact)
  {
    if (artifact) output << ',';
    output << '"' << names[artifact] << "\":{\"size_bytes\":" << artifact_sizes[names[artifact]]
           << ",\"sha256\":\"" << artifact_hashes[names[artifact]] << "\"}";
  }
  output << "}}\n";
  if (!FinishOutput(output, "manifest.json", error)) return false;
  if (!CommitStaging(staging, output_dir, error)) return false;
  return true;
}
}
