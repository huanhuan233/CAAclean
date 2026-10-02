#include "caa/CaaDocumentHandle.h"
#include "platform/WindowsPathCodec.h"

#include <CATDocument.h>
#include <CATDocumentServices.h>
#include <CATErrorDef.h>
#include <CATUnicodeString.h>
#include <algorithm>
#include <cctype>
#include <sys/stat.h>
#include <vector>

namespace cadcapture {

static std::string CaaUnicodeToUtf8(const CATUnicodeString& value)
{
  const size_t capacity = static_cast<size_t>(value.GetLengthInChar() + 1) * 4 + 1;
  std::vector<char> buffer(capacity, 0);
  size_t byte_count = 0;
  value.ConvertToUTF8(&buffer[0], &byte_count);
  if (byte_count >= buffer.size())
    byte_count = buffer.size() - 1;
  buffer[byte_count] = 0;
  return std::string(&buffer[0], byte_count);
}

static std::string LowerSuffix(const std::string& path, size_t count)
{
  if (path.size() < count)
    return "";
  std::string suffix = path.substr(path.size() - count);
  std::transform(suffix.begin(), suffix.end(), suffix.begin(), static_cast<int (*)(int)>(std::tolower));
  return suffix;
}

static bool IsSupportedNativeDocument(const std::string& path)
{
  return LowerSuffix(path, 8) == ".catpart" || LowerSuffix(path, 11) == ".catproduct";
}

// 中文：只在路径确有非 ASCII 字符时才尝试 CATIA 的临时英文目录别名。
static bool HasNonAsciiCharacter(const std::wstring& path)
{
  for (size_t i = 0; i < path.size(); ++i)
    if (path[i] > 127) return true;
  return false;
}

CaaDocumentHandle::CaaDocumentHandle() : _document(0) {}

CaaDocumentHandle::~CaaDocumentHandle()
{
  Close();
}

bool CaaDocumentHandle::OpenReadOnly(const std::string& path, std::string& error)
{
  Close();
  // 中文：文件检查与 CATIA 打开必须使用同一条 UTF-16 路径，不能先走 ANSI _stat。
  const std::wstring wide_path = WindowsPathCodec::Decode(path);
  if (wide_path.empty())
  {
    error = "input path is not valid UTF-8";
    return false;
  }
  struct _stat file_status;
  if (_wstat(wide_path.c_str(), &file_status) != 0)
  {
    error = "input file does not exist";
    return false;
  }
  if (!IsSupportedNativeDocument(path))
  {
    error = "input file is not a CATPart or CATProduct";
    return false;
  }

  CATDocument* document = 0;
  CATUnicodeString storage_name;
  storage_name.BuildFromUTF8(path.c_str(), path.size());
  const HRESULT result = CATDocumentServices::OpenDocument(storage_name, document, TRUE);
  if (FAILED(result) || !document)
  {
    if (!HasNonAsciiCharacter(wide_path))
    {
      error = "CATIA document open failed";
      return false;
    }
    // 中文：旧 CATIA 不能直接打开中文目录时，使用指向原目录的英文接合点重试。
    std::string aliased_path;
    if (!_path_alias.OpenForFile(path, aliased_path, error))
      return false;
    storage_name.BuildFromUTF8(aliased_path.c_str(), aliased_path.size());
    const HRESULT alias_result = CATDocumentServices::OpenDocument(storage_name, document, TRUE);
    if (FAILED(alias_result) || !document)
    {
      _path_alias.Close();
      error = "CATIA document open failed with original and ASCII directory alias";
      return false;
    }
  }

  _document = document;
  return true;
}

void CaaDocumentHandle::Close()
{
  // 中文：先卸载 CATIA 文档，再移除只属于本句柄的英文目录别名。
  if (_document)
  {
    CATDocument* document = static_cast<CATDocument*>(_document);
    CATDocumentServices::Remove(*document);
    _document = 0;
  }
  _path_alias.Close();
}

bool CaaDocumentHandle::IsOpen() const
{
  return _document != 0;
}

void* CaaDocumentHandle::NativeDocumentForCaaOnly() const
{
  return _document;
}

std::string CaaDocumentHandle::DisplayName() const
{
  if (!_document)
    return "";
  CATDocument* document = static_cast<CATDocument*>(_document);
  return CaaUnicodeToUtf8(document->DisplayName());
}

}
