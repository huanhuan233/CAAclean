/* 把原生指针格式化为仅在当前会话内使用的标识键。 */
#ifndef CADCAPTURE_CAA_CAANATIVEHANDLE_H
#define CADCAPTURE_CAA_CAANATIVEHANDLE_H

#include <sstream>
#include <string>

namespace cadcapture {

/* 地址文本仅用于当前进程内关联，不能充当跨运行或跨版本稳定身份。 */
static std::string CaaSessionLocalHandleKey(const void* pointer)
{
  std::ostringstream out;
  out << pointer;
  return out.str();
}

}

#endif
