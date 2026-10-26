/* 封装只读 CATIA 文档句柄及其临时目录别名的生命周期。 */
#ifndef CADCAPTURE_CAA_CAADOCUMENTHANDLE_H
#define CADCAPTURE_CAA_CAADOCUMENTHANDLE_H

#include <string>
#include "platform/WindowsDirectoryAlias.h"

namespace cadcapture {

/* 禁止复制，避免两个句柄重复移除同一 CATDocument；原生指针只在打开期间有效。 */
class CaaDocumentHandle
{
public:
  CaaDocumentHandle();
  ~CaaDocumentHandle();

  /* 输入采用 UTF-8 路径；每次打开前关闭旧文档，失败原因写入 error。 */
  bool OpenReadOnly(const std::string& path, std::string& error);
  void Close();
  bool IsOpen() const;

  /* 返回借用句柄供 CAA 层访问，调用方不得转移或延长文档所有权。 */
  void* NativeDocumentForCaaOnly() const;
  std::string DisplayName() const;

private:
  CaaDocumentHandle(const CaaDocumentHandle&);
  CaaDocumentHandle& operator=(const CaaDocumentHandle&);

  void* _document;
  WindowsDirectoryAlias _path_alias;
};

}

#endif
