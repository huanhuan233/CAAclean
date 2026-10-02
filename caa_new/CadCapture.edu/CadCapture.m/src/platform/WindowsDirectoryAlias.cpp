#include "platform/WindowsDirectoryAlias.h"
#include "platform/WindowsPathCodec.h"
#include <windows.h>
#include <winioctl.h>
#include <stddef.h>
#include <sstream>
#include <vector>

namespace cadcapture {
namespace {

// 中文：旧 SDK 的接合点数据布局固定，路径缓冲区中的偏移按字节计算。
struct JunctionData
{
  DWORD tag;
  WORD length;
  WORD reserved;
  WORD substitute_offset;
  WORD substitute_length;
  WORD print_offset;
  WORD print_length;
  WCHAR path[1];
};

// 中文：CATIA 旧接口只接受纯英文入口；否则保留显式失败，不让代码页静默改名。
bool IsAscii(const std::wstring& text)
{
  for (size_t i = 0; i < text.size(); ++i)
    if (text[i] > 127) return false;
  return true;
}

// 中文：GetTempPathW 的结果必须存在且可用英文路径表示，避免接合点本身再次触发 CATIA 限制。
bool TempRoot(std::wstring& root)
{
  const DWORD required = GetTempPathW(0, NULL);
  if (required == 0) return false;
  std::vector<wchar_t> buffer(required + 1, L'\0');
  const DWORD count = GetTempPathW(static_cast<DWORD>(buffer.size()), &buffer[0]);
  if (count == 0 || count >= buffer.size()) return false;
  root.assign(&buffer[0], count);
  const DWORD attributes = GetFileAttributesW(root.c_str());
  return IsAscii(root) && attributes != INVALID_FILE_ATTRIBUTES &&
         (attributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
}

// 中文：直接建立目录接合点，避免调用 shell 或依赖需要管理员权限的符号链接。
bool SetJunction(const std::wstring& alias, const std::wstring& target)
{
  const std::wstring substitute = L"\\??\\" + target;
  const size_t substitute_bytes = substitute.size() * sizeof(wchar_t);
  const size_t print_bytes = target.size() * sizeof(wchar_t);
  const size_t total = offsetof(JunctionData, path) + substitute_bytes + sizeof(wchar_t) + print_bytes + sizeof(wchar_t);
  if (total > 16000 || total - 8 > 65535) return false;
  std::vector<char> buffer(total, 0);
  JunctionData* data = reinterpret_cast<JunctionData*>(&buffer[0]);
  data->tag = IO_REPARSE_TAG_MOUNT_POINT;
  data->length = static_cast<WORD>(total - 8);
  data->substitute_offset = 0;
  data->substitute_length = static_cast<WORD>(substitute_bytes);
  data->print_offset = static_cast<WORD>(substitute_bytes + sizeof(wchar_t));
  data->print_length = static_cast<WORD>(print_bytes);
  memcpy(data->path, substitute.c_str(), substitute_bytes);
  memcpy(reinterpret_cast<char*>(data->path) + data->print_offset, target.c_str(), print_bytes);
  HANDLE handle = CreateFileW(alias.c_str(), GENERIC_WRITE, 0, NULL, OPEN_EXISTING,
                               FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, NULL);
  if (handle == INVALID_HANDLE_VALUE) return false;
  DWORD ignored = 0;
  const BOOL ok = DeviceIoControl(handle, FSCTL_SET_REPARSE_POINT, data,
                                  static_cast<DWORD>(total), NULL, 0, &ignored, NULL);
  CloseHandle(handle);
  return ok != 0;
}

}

WindowsDirectoryAlias::WindowsDirectoryAlias() {}

WindowsDirectoryAlias::~WindowsDirectoryAlias() { Close(); }

// 中文：别名指向原模型所在目录，CATProduct 的相对关联文件因此仍按原有目录解析。
bool WindowsDirectoryAlias::OpenForFile(const std::string& original_utf8,
                                        std::string& aliased_utf8, std::string& error)
{
  Close();
  aliased_utf8.clear();
  const std::wstring original = WindowsPathCodec::Decode(WindowsPathCodec::FullPath(original_utf8));
  const size_t separator = original.find_last_of(L"\\/");
  if (original.empty() || separator == std::wstring::npos || separator == 0)
  {
    error = "CATIA path alias requires an absolute file path";
    return false;
  }
  const std::wstring filename = original.substr(separator + 1);
  if (filename.empty() || !IsAscii(filename))
  {
    error = "CATIA path alias requires an ASCII model filename";
    return false;
  }
  std::wstring root;
  if (!TempRoot(root))
  {
    error = "CATIA path alias requires an ASCII temporary directory";
    return false;
  }
  // 中文：卷根文件的父目录必须是 C:\，不能退化为按当前目录解释的 C:。
  const std::wstring target = separator == 2 && original[1] == L':' ?
      original.substr(0, 3) : original.substr(0, separator);
  for (unsigned int attempt = 0; attempt < 32; ++attempt)
  {
    std::wostringstream name;
    name << root << L"CadCaptureAlias_" << GetCurrentProcessId() << L"_"
         << GetTickCount() << L"_" << attempt;
    const std::wstring candidate = name.str();
    if (!CreateDirectoryW(candidate.c_str(), NULL)) continue;
    if (SetJunction(candidate, target))
    {
      _alias_directory = candidate;
      aliased_utf8 = WindowsPathCodec::Encode(candidate + L"\\" + filename);
      return true;
    }
    RemoveDirectoryW(candidate.c_str());
    error = "CATIA directory alias could not be created";
    return false;
  }
  error = "CATIA directory alias has no available unique name";
  return false;
}

// 中文：RemoveDirectoryW 对接合点只删除入口；先验证重解析标记防止误删普通目录。
void WindowsDirectoryAlias::Close()
{
  if (_alias_directory.empty()) return;
  const DWORD attributes = GetFileAttributesW(_alias_directory.c_str());
  if (attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_REPARSE_POINT))
    RemoveDirectoryW(_alias_directory.c_str());
  _alias_directory.clear();
}

}
