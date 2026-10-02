#include "platform/WindowsPathCodec.h"
#include <windows.h>

namespace cadcapture {
namespace {

// 中文：旧版 Windows SDK 没有 WC_ERR_INVALID_CHARS，先显式检查 UTF-16 代理对。
bool ValidUtf16(const std::wstring& wide)
{
  for (size_t i = 0; i < wide.size(); ++i)
  {
    const unsigned int value = static_cast<unsigned int>(wide[i]);
    if (value >= 0xD800 && value <= 0xDBFF)
    {
      if (++i >= wide.size()) return false;
      const unsigned int lower = static_cast<unsigned int>(wide[i]);
      if (lower < 0xDC00 || lower > 0xDFFF) return false;
    }
    else if (value >= 0xDC00 && value <= 0xDFFF)
      return false;
  }
  return true;
}

}

// 中文：Win32 严格 UTF-8 解码，任何损坏字符都视作路径错误。
std::wstring WindowsPathCodec::Decode(const std::string& utf8)
{
  if (utf8.empty()) return std::wstring();
  const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8.data(),
                                        static_cast<int>(utf8.size()), NULL, 0);
  if (count <= 0) return std::wstring();
  std::wstring wide(static_cast<size_t>(count), L'\0');
  if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, utf8.data(),
                          static_cast<int>(utf8.size()), &wide[0], count) != count)
    return std::wstring();
  return wide;
}

// 中文：转换命令行及文件名时不经过当前 ANSI 代码页。
std::string WindowsPathCodec::Encode(const std::wstring& wide)
{
  if (wide.empty() || !ValidUtf16(wide)) return std::string();
  const int count = WideCharToMultiByte(CP_UTF8, 0, wide.data(),
                                        static_cast<int>(wide.size()), NULL, 0, NULL, NULL);
  if (count <= 0) return std::string();
  std::string utf8(static_cast<size_t>(count), '\0');
  if (WideCharToMultiByte(CP_UTF8, 0, wide.data(),
                          static_cast<int>(wide.size()), &utf8[0], count, NULL, NULL) != count)
    return std::string();
  return utf8;
}

// 中文：GetFullPathNameW 避免中文路径在相对路径展开时被系统 ANSI 代码页损坏。
std::string WindowsPathCodec::FullPath(const std::string& utf8)
{
  const std::wstring path = Decode(utf8);
  if (path.empty()) return std::string();
  const DWORD needed = GetFullPathNameW(path.c_str(), 0, NULL, NULL);
  if (needed == 0) return std::string();
  std::vector<wchar_t> buffer(needed + 1, L'\0');
  const DWORD count = GetFullPathNameW(path.c_str(), static_cast<DWORD>(buffer.size()), &buffer[0], NULL);
  if (count == 0 || count >= buffer.size()) return std::string();
  return Encode(std::wstring(&buffer[0], count));
}

// 中文：属性查询直接从 UTF-8 解码到 Win32 宽路径。
unsigned long WindowsPathCodec::Attributes(const std::string& utf8)
{
  const std::wstring path = Decode(utf8);
  return path.empty() ? INVALID_FILE_ATTRIBUTES : GetFileAttributesW(path.c_str());
}

// 中文：目录项以 UTF-8 回传；未知编码不能作为“安全可删”的文件名。
bool WindowsPathCodec::List(const std::string& directory, std::vector<std::string>& names,
                            std::vector<unsigned long>& attributes)
{
  names.clear();
  attributes.clear();
  const std::wstring path = Decode(directory + "\\*");
  if (path.empty()) return false;
  WIN32_FIND_DATAW data;
  HANDLE handle = FindFirstFileW(path.c_str(), &data);
  if (handle == INVALID_HANDLE_VALUE) return false;
  bool valid = true;
  do
  {
    const std::string name = Encode(data.cFileName);
    if (name.empty()) { valid = false; break; }
    names.push_back(name);
    attributes.push_back(data.dwFileAttributes);
  } while (FindNextFileW(handle, &data));
  FindClose(handle);
  return valid;
}

// 中文：同卷事务暂存目录使用宽字符创建。
bool WindowsPathCodec::CreateUtf8Directory(const std::string& utf8)
{
  const std::wstring path = Decode(utf8);
  return !path.empty() && CreateDirectoryW(path.c_str(), NULL) != 0;
}

// 中文：备份、提交和回滚均使用同一宽字符移动原语。
bool WindowsPathCodec::Move(const std::string& source, const std::string& target)
{
  const std::wstring from = Decode(source), to = Decode(target);
  return !from.empty() && !to.empty() && MoveFileW(from.c_str(), to.c_str()) != 0;
}

// 中文：仅由仓储在完成所有权检查后调用删除原语。
bool WindowsPathCodec::DeleteUtf8File(const std::string& utf8)
{
  const std::wstring path = Decode(utf8);
  return !path.empty() && DeleteFileW(path.c_str()) != 0;
}

// 中文：仅由仓储在完成所有权检查后调用目录删除原语。
bool WindowsPathCodec::RemoveUtf8Directory(const std::string& utf8)
{
  const std::wstring path = Decode(utf8);
  return !path.empty() && RemoveDirectoryW(path.c_str()) != 0;
}

// 中文：只调整已经归属本次事务的目标属性，宽路径不会误指向其他文件。
bool WindowsPathCodec::SetNormalAttributes(const std::string& utf8)
{
  const std::wstring path = Decode(utf8);
  return !path.empty() && SetFileAttributesW(path.c_str(), FILE_ATTRIBUTE_NORMAL) != 0;
}

}
