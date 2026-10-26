// 声明为旧版 CATIA 管理临时 ASCII 目录接合点的对象。
#ifndef CADCAPTURE_PLATFORM_WINDOWSDIRECTORYALIAS_H
#define CADCAPTURE_PLATFORM_WINDOWSDIRECTORYALIAS_H

#include <string>

namespace cadcapture {

// 中文：为不接受中文路径的旧版 CATIA 创建临时英文目录入口；不复制模型及其关联文件。
class WindowsDirectoryAlias
{
public:
  // 初始不持有目录别名，调用 OpenForFile 后才创建入口。
  WindowsDirectoryAlias();
  // 析构时尝试移除本对象保存的接合点入口。
  ~WindowsDirectoryAlias();

  // 中文：仅给目录建立本进程拥有的 NTFS 接合点；输入文件名必须能由 CATIA 原样打开。
  bool OpenForFile(const std::string& original_utf8, std::string& aliased_utf8,
                   std::string& error);
  // 中文：只移除本对象创建的接合点，不递归触碰指向的原目录。
  void Close();

private:
  // 禁止复制，防止多个对象同时管理同一临时接合点。
  WindowsDirectoryAlias(const WindowsDirectoryAlias&);
  WindowsDirectoryAlias& operator=(const WindowsDirectoryAlias&);
  std::wstring _alias_directory;
};

}

#endif
