/* 实现 CATIA 批处理会话的创建、错误报告和销毁。 */
#include "caa/CaaRuntime.h"

#include <CATInit.h>
#include <CATSession.h>
#include <CATSessionServices.h>
#include <CATErrorDef.h>
#include <sstream>

namespace cadcapture {

CaaRuntime::CaaRuntime() : _open(false), _session_name("CadCaptureSession") {}

CaaRuntime::~CaaRuntime()
{
  Close();
}
/* 创建命名会话并检查 HRESULT 和返回指针；调用方应避免对已打开实例重复 Open。 */
bool CaaRuntime::Open(std::string& error)
{
  CATSession* session = 0;
  const HRESULT result = Create_Session(const_cast<char*>(_session_name.c_str()), session);
  if (FAILED(result) || !session)
  {
    std::ostringstream message;
    message << "CAA session initialization failed (HRESULT=0x" << std::hex
            << static_cast<unsigned long>(result) << ")";
    error = message.str();
    return false;
  }
  _open = true;
  return true;
}

/* 只有记录为已打开的会话才删除；相关文档应先于会话释放。 */
void CaaRuntime::Close()
{
  if (_open)
  {
    Delete_Session(const_cast<char*>(_session_name.c_str()));
    _open = false;
  }
}

bool CaaRuntime::IsOpen() const
{
  return _open;
}

const std::string& CaaRuntime::SessionName() const
{
  return _session_name;
}

}

