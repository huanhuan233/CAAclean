#include "output/ArtifactRepository.h"
#include "output/JsonSupport.h"
#include "output/LegacyArtifactProjection.h"
#include "output/NormalizedArtifactWriter.h"
#include <fstream>
#include <windows.h>

namespace cadcapture {

static std::string JoinPath(const std::string& directory, const char* name)
{
  if (directory.empty())
    return name;
  const char last = directory[directory.size() - 1];
  if (last == '\\' || last == '/')
    return directory + name;
  return directory + "\\" + name;
}

static bool RemoveTree(const std::string& path)
{
  const DWORD attributes = GetFileAttributesA(path.c_str());
  if (attributes == INVALID_FILE_ATTRIBUTES)
    return true;
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
      if (name == "." || name == "..")
        continue;
      const std::string child = JoinPath(path, name.c_str());
      if (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
        RemoveTree(child);
      else
      {
        SetFileAttributesA(child.c_str(), FILE_ATTRIBUTE_NORMAL);
        DeleteFileA(child.c_str());
      }
    } while (FindNextFileA(find, &data));
    FindClose(find);
  }
  SetFileAttributesA(path.c_str(), FILE_ATTRIBUTE_NORMAL);
  return RemoveDirectoryA(path.c_str()) != 0 || GetLastError() == ERROR_PATH_NOT_FOUND;
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
    "features.jsonl",
    "relations.jsonl",
    "parameters.jsonl",
    "native_features.jsonl"
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
  LegacyArtifactProjection legacy;
  return legacy.ValidateRelationEndpoints(package, error);
}

static bool CommitStaging(const std::string& staging,
                          const std::string& output_dir,
                          std::string& error)
{
  const std::string backup = output_dir + ".cadcapture_backup";
  RemoveTree(backup);
  const bool had_output = GetFileAttributesA(output_dir.c_str()) != INVALID_FILE_ATTRIBUTES;
  if (had_output && !MoveFileA(output_dir.c_str(), backup.c_str()))
  {
    error = "cannot move previous output to transaction backup";
    return false;
  }
  if (!MoveFileA(staging.c_str(), output_dir.c_str()))
  {
    if (had_output)
      MoveFileA(backup.c_str(), output_dir.c_str());
    error = "cannot commit transaction staging directory";
    return false;
  }
  if (had_output)
    RemoveTree(backup);
  return true;
}

bool ArtifactRepository::Commit(const ReconstructionPackage& package,
                                const CaptureReport& report,
                                const std::string& output_dir,
                                bool pretty,
                                std::string& error)
{
  const std::string staging = output_dir + ".cadcapture_stage";
  LegacyArtifactProjection legacy;
  NormalizedArtifactWriter writer;
  const std::string legacy_status = legacy.ProjectionStatus(package);
  RemoveTree(staging);
  if (!writer.Write(package, report, staging, pretty, legacy_status, error))
  {
    RemoveTree(staging);
    return false;
  }
  if (!legacy.Write(package, staging, error))
  {
    RemoveTree(staging);
    return false;
  }
  if (!VerifyStaging(package, staging, error))
  {
    RemoveTree(staging);
    return false;
  }
  if (!CommitStaging(staging, output_dir, error))
  {
    RemoveTree(staging);
    return false;
  }
  return true;
}

}
