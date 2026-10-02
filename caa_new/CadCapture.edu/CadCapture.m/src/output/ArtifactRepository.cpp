#include "output/ArtifactRepository.h"
#include "output/JsonSupport.h"
#include "output/LegacyArtifactProjection.h"
#include "output/NormalizedArtifactWriter.h"
#include <fstream>
#include <sstream>
#include <vector>
#include <windows.h>

namespace cadcapture {

// 中文：仅拼接仓储内部的文件名，不解释用户输入的路径。
static std::string JoinPath(const std::string& directory, const char* name)
{
  if (directory.empty())
    return name;
  const char last = directory[directory.size() - 1];
  if (last == '\\' || last == '/')
    return directory + name;
  return directory + "\\" + name;
}

// 中文：识别规范化路径是否为卷根；卷根永远不能作为采集输出。
static bool IsVolumeRoot(const std::string& path)
{
  return path.size() == 3 && path[1] == ':' &&
         (path[2] == '\\' || path[2] == '/');
}

// 中文：将调用方路径转为完整路径，拒绝网络和设备路径及卷根。
static bool NormalizeOutputPath(const std::string& input, std::string& output, std::string& error)
{
  if (input.empty() ||
      (input.size() >= 2 && (input[0] == '\\' || input[0] == '/') &&
       (input[1] == '\\' || input[1] == '/')))
  {
    error = "output path is empty or uses an unsupported network/device path";
    return false;
  }
  const DWORD needed = GetFullPathNameA(input.c_str(), 0, NULL, NULL);
  if (needed == 0)
  {
    error = "cannot resolve output path";
    return false;
  }
  std::vector<char> buffer(needed + 1, 0);
  const DWORD length = GetFullPathNameA(input.c_str(), static_cast<DWORD>(buffer.size()), &buffer[0], NULL);
  if (length == 0 || length >= buffer.size())
  {
    error = "cannot resolve output path";
    return false;
  }
  output.assign(&buffer[0], length);
  while (output.size() > 3 && (output[output.size() - 1] == '\\' || output[output.size() - 1] == '/'))
    output.erase(output.size() - 1);
  if (IsVolumeRoot(output) || output.size() < 4)
  {
    error = "output path cannot be a volume root";
    return false;
  }
  return true;
}

// 中文：拒绝输出路径任何已存在的重解析点，避免清理时跨越链接边界。
static bool CheckPathComponents(const std::string& path, std::string& error)
{
  size_t i;
  for (i = 3; i <= path.size(); ++i)
  {
    if (i != path.size() && path[i] != '\\' && path[i] != '/')
      continue;
    const std::string component = path.substr(0, i);
    const DWORD attributes = GetFileAttributesA(component.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES)
      continue;
    if (attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    {
      error = "output path contains a reparse point: " + component;
      return false;
    }
    if (i != path.size() && !(attributes & FILE_ATTRIBUTE_DIRECTORY))
    {
      error = "output parent is not a directory: " + component;
      return false;
    }
  }
  return true;
}

// 中文：判断已存在输出目录是否为空；读取失败按不安全处理。
static bool IsEmptyDirectory(const std::string& path, bool& empty, std::string& error)
{
  empty = true;
  WIN32_FIND_DATAA data;
  HANDLE find = FindFirstFileA(JoinPath(path, "*").c_str(), &data);
  if (find == INVALID_HANDLE_VALUE)
  {
    error = "cannot enumerate existing output directory";
    return false;
  }
  do
  {
    const std::string name = data.cFileName;
    if (name != "." && name != "..")
    {
      empty = false;
      break;
    }
  } while (FindNextFileA(find, &data));
  FindClose(find);
  return true;
}

// 中文：只承认当前采集器和 Worker 会写入的文件名，防止混入用户文件后整目录清理。
static bool IsKnownCaptureFile(const std::string& name)
{
  const char* known[] = {
    "manifest.json", "capture_report.json", "reconstruction_plan.json", "object_entities.jsonl",
    "tree_occurrences.jsonl", "product_references.jsonl", "product_occurrences.jsonl",
    "document_links.jsonl", "property_facts.jsonl", "semantic_facets.jsonl",
    "topology_entities.jsonl", "geometry_entities.jsonl", "pmi_entities.jsonl",
    "feature_dependencies.jsonl", "topology_relations.jsonl", "pmi_associations.jsonl",
    "diagnostics.jsonl", "features.jsonl", "relations.jsonl", "parameters.jsonl",
    "native_features.jsonl", "native_topology.jsonl", "native_topology_bodies.jsonl",
    "native_topology_cells.jsonl", "native_topology_wires.jsonl", "native_topology_coedges.jsonl",
    "native_mesh_face_map.jsonl", "native_mesh_triangles.jsonl", "fta_sets.jsonl",
    "native_feature_results.jsonl", "native_feature_result_cells.jsonl",
    "native_feature_topology_links.jsonl", "fta_semantics.jsonl", "fta_topology_links.jsonl",
    "capabilities.json", "coverage.json", "caa_new_runner.log", ".cadcapture_stage_owner",
    ".cadcapture_backup_owner"
  };
  size_t i;
  for (i = 0; i < sizeof(known) / sizeof(known[0]); ++i)
  {
    if (name == known[i])
      return true;
  }
  return false;
}

// 中文：逐项确认旧目录只含已知产物，子目录与重解析文件都不视为解析器所有。
static bool ContainsOnlyCaptureFiles(const std::string& path)
{
  WIN32_FIND_DATAA data;
  HANDLE find = FindFirstFileA(JoinPath(path, "*").c_str(), &data);
  if (find == INVALID_HANDLE_VALUE)
    return false;
  bool valid = true;
  do
  {
    const std::string name = data.cFileName;
    if (name == "." || name == "..")
      continue;
    if ((data.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) ||
        !IsKnownCaptureFile(name))
    {
      valid = false;
      break;
    }
  } while (FindNextFileA(find, &data));
  FindClose(find);
  return valid;
}

// 中文：兼容旧版无所有权标记的采集包，只接受结构完整且没有未知内容的 manifest。
static bool HasCaptureManifest(const std::string& path)
{
  std::ifstream manifest(JoinPath(path, "manifest.json").c_str(), std::ios::in | std::ios::binary);
  if (!manifest)
    return false;
  std::ostringstream content;
  content << manifest.rdbuf();
  const std::string body = content.str();
  return body.find("\"schema_version\"") != std::string::npos &&
         body.find("caa_capture_") != std::string::npos &&
         GetFileAttributesA(JoinPath(path, "capture_report.json").c_str()) != INVALID_FILE_ATTRIBUTES &&
         GetFileAttributesA(JoinPath(path, "object_entities.jsonl").c_str()) != INVALID_FILE_ATTRIBUTES &&
         GetFileAttributesA(JoinPath(path, "tree_occurrences.jsonl").c_str()) != INVALID_FILE_ATTRIBUTES &&
         ContainsOnlyCaptureFiles(path);
}

// 中文：只允许写入不存在、为空或可证明是本解析器产物的目录。
static bool ValidateOutputTarget(const std::string& path, std::string& error)
{
  if (!CheckPathComponents(path, error))
    return false;
  const DWORD attributes = GetFileAttributesA(path.c_str());
  if (attributes == INVALID_FILE_ATTRIBUTES)
    return true;
  if (!(attributes & FILE_ATTRIBUTE_DIRECTORY))
  {
    error = "output target is not a directory";
    return false;
  }
  bool empty = false;
  if (!IsEmptyDirectory(path, empty, error))
    return false;
  if (!empty && !HasCaptureManifest(path))
  {
    error = "existing output is not an owned capture directory";
    return false;
  }
  return true;
}

// 中文：写入本次事务标记，供失败清理和备份回收做身份校验。
static bool WriteOwnerMarker(const std::string& path, const char* marker, const std::string& token)
{
  std::ofstream out(JoinPath(path, marker).c_str(), std::ios::out | std::ios::binary);
  out << token;
  out.close();
  return !!out;
}

// 中文：核对事务标记，拒绝清理非本次创建的目录。
static bool HasOwnerMarker(const std::string& path, const char* marker, const std::string& token)
{
  std::ifstream in(JoinPath(path, marker).c_str(), std::ios::in | std::ios::binary);
  std::string actual;
  std::getline(in, actual);
  return !!in && actual == token;
}

// 中文：递归删除本事务已核对所有权的目录，遇重解析点立即停止。
static bool RemoveOwnedContents(const std::string& path, std::string& error)
{
  const DWORD attributes = GetFileAttributesA(path.c_str());
  if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT))
  {
    error = "owned path missing or contains reparse point: " + path;
    return false;
  }
  if (!(attributes & FILE_ATTRIBUTE_DIRECTORY))
  {
    SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_NORMAL);
    if (DeleteFileA(path.c_str()))
      return true;
    error = "cannot remove owned file: " + path;
    return false;
  }
  WIN32_FIND_DATAA data;
  HANDLE find = FindFirstFileA(JoinPath(path, "*").c_str(), &data);
  if (find == INVALID_HANDLE_VALUE)
  {
    error = "cannot enumerate owned directory: " + path;
    return false;
  }
  bool success = true;
  do
  {
    const std::string name = data.cFileName;
    if (name != "." && name != ".." && !RemoveOwnedContents(JoinPath(path, name.c_str()), error))
    {
      success = false;
      break;
    }
  } while (FindNextFileA(find, &data));
  FindClose(find);
  if (!success)
    return false;
  SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_NORMAL);
  if (RemoveDirectoryA(path.c_str()))
    return true;
  error = "cannot remove owned directory: " + path;
  return false;
}

// 中文：清理前再次核对本次事务标记，不能以路径名相似代替所有权。
static bool RemoveOwnedTree(const std::string& path, const char* marker,
                            const std::string& token, std::string& error)
{
  if (!HasOwnerMarker(path, marker, token))
  {
    error = "transaction marker mismatch: " + path;
    return false;
  }
  return RemoveOwnedContents(path, error);
}

// 中文：创建不会与旧固定暂存名碰撞的独占同级目录。
static bool CreateOwnedStaging(const std::string& output_dir, std::string& staging,
                               std::string& token, std::string& error)
{
  int attempt;
  for (attempt = 0; attempt < 100; ++attempt)
  {
    std::ostringstream suffix;
    suffix << GetCurrentProcessId() << "." << GetTickCount() << "." << attempt;
    token = suffix.str();
    staging = output_dir + ".cadcapture_stage." + token;
    if (!CreateDirectoryA(staging.c_str(), NULL))
    {
      if (GetLastError() == ERROR_ALREADY_EXISTS)
        continue;
      error = "cannot create transaction staging directory: " + staging;
      return false;
    }
    if (!WriteOwnerMarker(staging, ".cadcapture_stage_owner", token))
    {
      error = "cannot mark transaction staging directory: " + staging;
      RemoveDirectoryA(staging.c_str());
      return false;
    }
    return true;
  }
  error = "cannot allocate unique transaction staging directory";
  return false;
}

static bool ReadableFileExists(const std::string& path)
{
  std::ifstream in(path.c_str(), std::ios::in | std::ios::binary);
  return !!in;
}

static long CountLines(const std::string& path)
{
  std::ifstream in(path.c_str(), std::ios::in | std::ios::binary);
  long count = 0;
  std::string line;
  while (std::getline(in, line))
    ++count;
  return count;
}

static bool VerifyStaging(const ReconstructionPackage& package,
                          const std::string& staging,
                          std::string& error)
{
  const char* required[] = {
    "manifest.json",
    "capture_report.json",
    "reconstruction_plan.json",
    "object_entities.jsonl",
    "tree_occurrences.jsonl",
    "product_references.jsonl",
    "product_occurrences.jsonl",
    "document_links.jsonl",
    "property_facts.jsonl",
    "semantic_facets.jsonl",
    "topology_entities.jsonl",
    "geometry_entities.jsonl",
    "pmi_entities.jsonl",
    "feature_dependencies.jsonl",
    "topology_relations.jsonl",
    "pmi_associations.jsonl",
    "diagnostics.jsonl",
    "features.jsonl",
    "relations.jsonl",
    "parameters.jsonl",
    "native_features.jsonl",
    "native_topology.jsonl",
    "native_topology_bodies.jsonl",
    "native_topology_cells.jsonl",
    "native_topology_wires.jsonl",
    "native_topology_coedges.jsonl",
    "native_mesh_face_map.jsonl",
    "native_mesh_triangles.jsonl",
    "fta_sets.jsonl",
    "native_feature_results.jsonl",
    "native_feature_result_cells.jsonl",
    "native_feature_topology_links.jsonl",
    "fta_semantics.jsonl",
    "fta_topology_links.jsonl",
    "capabilities.json"
  };
  int i;
  for (i = 0; i < static_cast<int>(sizeof(required) / sizeof(required[0])); ++i)
  {
    if (!ReadableFileExists(JoinPath(staging, required[i])))
    {
      error = std::string("required artifact missing or unreadable: ") + required[i];
      return false;
    }
  }
  if (CountLines(JoinPath(staging, "object_entities.jsonl")) != static_cast<long>(package.objects.size()))
  {
    error = "object_entities.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "tree_occurrences.jsonl")) !=
      static_cast<long>(package.occurrence_graph.object_occurrences.size()))
  {
    error = "tree_occurrences.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "features.jsonl")) !=
      static_cast<long>(package.occurrence_graph.object_occurrences.size() +
                        package.product_occurrences.size()))
  {
    error = "features.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "product_references.jsonl")) !=
      static_cast<long>(package.product_references.size()))
  {
    error = "product_references.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "product_occurrences.jsonl")) !=
      static_cast<long>(package.product_occurrences.size()))
  {
    error = "product_occurrences.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "document_links.jsonl")) !=
      static_cast<long>(package.document_graph.links.size()))
  {
    error = "document_links.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "property_facts.jsonl")) !=
      static_cast<long>(package.properties.size()))
  {
    error = "property_facts.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "parameters.jsonl")) !=
      static_cast<long>(package.properties.size()))
  {
    error = "parameters.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "semantic_facets.jsonl")) !=
      static_cast<long>(package.semantic_facets.size()))
  {
    error = "semantic_facets.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "native_features.jsonl")) !=
      static_cast<long>(package.semantic_facets.size()))
  {
    error = "native_features.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "topology_entities.jsonl")) !=
      static_cast<long>(package.topology.size()))
  {
    error = "topology_entities.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "geometry_entities.jsonl")) !=
      static_cast<long>(package.geometry.size()))
  {
    error = "geometry_entities.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "native_topology.jsonl")) !=
      static_cast<long>(package.topology.size()))
  {
    error = "native_topology.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "native_mesh_face_map.jsonl")) !=
      static_cast<long>(package.geometry.size()))
  {
    error = "native_mesh_face_map.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "pmi_entities.jsonl")) !=
      static_cast<long>(package.pmi.size()))
  {
    error = "pmi_entities.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "fta_sets.jsonl")) !=
      static_cast<long>(package.pmi.size()))
  {
    error = "fta_sets.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "fta_semantics.jsonl")) !=
      static_cast<long>(package.fta_semantics.size()))
  {
    error = "fta_semantics.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "feature_dependencies.jsonl")) !=
      static_cast<long>(package.feature_dependencies.size()))
  {
    error = "feature_dependencies.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "topology_relations.jsonl")) !=
      static_cast<long>(package.topology_relations.size()))
  {
    error = "topology_relations.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "pmi_associations.jsonl")) !=
      static_cast<long>(package.pmi_associations.size()))
  {
    error = "pmi_associations.jsonl line count mismatch";
    return false;
  }
  if (CountLines(JoinPath(staging, "diagnostics.jsonl")) !=
      static_cast<long>(package.diagnostics.size()))
  {
    error = "diagnostics.jsonl line count mismatch";
    return false;
  }
  long result_body_count = 0;
  size_t topology_index = 0;
  for (topology_index = 0; topology_index < package.topology.size(); ++topology_index)
  {
    if (package.topology[topology_index].source_kind == "catishapefeaturebody_resultout")
      ++result_body_count;
  }
  if (CountLines(JoinPath(staging, "native_feature_results.jsonl")) != result_body_count)
  {
    error = "native_feature_results.jsonl line count mismatch";
    return false;
  }
  LegacyArtifactProjection legacy;
  return legacy.ValidateRelationEndpoints(package, error);
}

// 中文：为旧输出选择未占用的备份名字；已有同名目录一律保留。
static bool ChooseBackupPath(const std::string& output_dir, const std::string& token,
                             std::string& backup, std::string& error)
{
  int attempt;
  for (attempt = 0; attempt < 100; ++attempt)
  {
    std::ostringstream candidate;
    candidate << output_dir << ".cadcapture_backup." << token << "." << attempt;
    backup = candidate.str();
    if (GetFileAttributesA(backup.c_str()) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND)
      return true;
  }
  error = "cannot allocate unique transaction backup path";
  return false;
}

// 中文：旧输出先备份，新输出成功落位后再清理；失败则尽力恢复并保留证据。
static bool CommitStaging(const std::string& staging, const std::string& output_dir,
                          const std::string& token, std::string& error)
{
  if (!ValidateOutputTarget(output_dir, error))
    return false;
  const bool had_output = GetFileAttributesA(output_dir.c_str()) != INVALID_FILE_ATTRIBUTES;
  std::string backup;
  if (had_output && !ChooseBackupPath(output_dir, token, backup, error))
    return false;
  if (had_output && !MoveFileA(output_dir.c_str(), backup.c_str()))
  {
    error = "cannot move previous output to transaction backup";
    return false;
  }
  if (had_output && !WriteOwnerMarker(backup, ".cadcapture_backup_owner", token))
  {
    if (!MoveFileA(backup.c_str(), output_dir.c_str()))
      error = "cannot mark backup; previous output retained at: " + backup;
    else
      error = "cannot mark transaction backup";
    return false;
  }
  if (!MoveFileA(staging.c_str(), output_dir.c_str()))
  {
    if (had_output && !MoveFileA(backup.c_str(), output_dir.c_str()))
      error = "cannot commit staging or restore previous output; backup retained at: " + backup;
    else
      error = "cannot commit transaction staging directory";
    return false;
  }
  if (!DeleteFileA(JoinPath(output_dir, ".cadcapture_stage_owner").c_str()))
    error = "capture committed, but transaction marker remains in output: " + output_dir;
  if (had_output)
  {
    std::string cleanup_error;
    if (!RemoveOwnedTree(backup, ".cadcapture_backup_owner", token, cleanup_error))
      error += " capture committed; backup retained at " + backup + ": " + cleanup_error;
  }
  return true;
}

// 中文：完整写出并核验到本次独占暂存目录后，才替换可证明属于采集器的输出。
bool ArtifactRepository::Commit(const ReconstructionPackage& package,
                                const CaptureReport& report,
                                const std::string& output_dir,
                                bool pretty,
                                std::string& error)
{
  std::string safe_output;
  if (!NormalizeOutputPath(output_dir, safe_output, error) ||
      !ValidateOutputTarget(safe_output, error))
    return false;
  std::string staging;
  std::string token;
  if (!CreateOwnedStaging(safe_output, staging, token, error))
    return false;
  LegacyArtifactProjection legacy;
  NormalizedArtifactWriter writer;
  const std::string legacy_status = legacy.ProjectionStatus(package);
  if (!writer.Write(package, report, staging, pretty, legacy_status, error))
  {
    std::string cleanup_error;
    RemoveOwnedTree(staging, ".cadcapture_stage_owner", token, cleanup_error);
    return false;
  }
  if (!legacy.Write(package, staging, error))
  {
    std::string cleanup_error;
    RemoveOwnedTree(staging, ".cadcapture_stage_owner", token, cleanup_error);
    return false;
  }
  if (!VerifyStaging(package, staging, error))
  {
    std::string cleanup_error;
    RemoveOwnedTree(staging, ".cadcapture_stage_owner", token, cleanup_error);
    return false;
  }
  if (!CommitStaging(staging, safe_output, token, error))
  {
    std::string cleanup_error;
    RemoveOwnedTree(staging, ".cadcapture_stage_owner", token, cleanup_error);
    return false;
  }
  return true;
}

}
