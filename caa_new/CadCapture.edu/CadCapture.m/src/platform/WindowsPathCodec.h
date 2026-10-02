#ifndef CADCAPTURE_PLATFORM_WINDOWSPATHCODEC_H
#define CADCAPTURE_PLATFORM_WINDOWSPATHCODEC_H

#include <string>
#include <vector>

namespace cadcapture {

// 中文：系统边界统一使用 UTF-8 内部路径、UTF-16 Win32/CAA 路径。
class WindowsPathCodec
{
public:
  // 中文：严格解码 UTF-8，非法字节返回空串，不能回退系统代码页。
  static std::wstring Decode(const std::string& utf8);
  // 中文：把 Windows 命令行和目录项 UTF-16 无损编码为 UTF-8。
  static std::string Encode(const std::wstring& wide);
  // 中文：解析相对路径时使用宽字符 Win32 API，并返回规范 UTF-8 路径。
  static std::string FullPath(const std::string& utf8);
  // 中文：文件系统属性查询只走宽字符 API。
  static unsigned long Attributes(const std::string& utf8);
  // 中文：枚举目录项时编码回 UTF-8，无法无损编码则失败。
  static bool List(const std::string& directory, std::vector<std::string>& names,
                   std::vector<unsigned long>& attributes);
  // 中文：以下目录事务操作均在 UTF-16 路径上执行，保留 Win32 错误码。
  static bool CreateUtf8Directory(const std::string& utf8);
  static bool Move(const std::string& source, const std::string& target);
  static bool DeleteUtf8File(const std::string& utf8);
  static bool RemoveUtf8Directory(const std::string& utf8);
  static bool SetNormalAttributes(const std::string& utf8);
};

}

#endif
