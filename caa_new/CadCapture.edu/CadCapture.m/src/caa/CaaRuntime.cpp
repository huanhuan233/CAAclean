#include "caa/CaaRuntime.h"

#include <CATInit.h>
#include <CATSession.h>
#include <CATSessionServices.h>
#include <CATErrorDef.h>

namespace cadcapture {

CaaRuntime::CaaRuntime() : _open(false), _session_name("CadCaptureSession") {}

CaaRuntime::~CaaRuntime()
{
  Close();
}

bool CaaRuntime::Open(std::string& error)
{
  CATSession* session = 0;
  const HRESULT result = Create_Session(const_cast<char*>(_session_name.c_str()), session);
  if (FAILED(result) || !session)
  {
    error = "CAA session initialization failed";
    return false;
  }
  _open = true;
  return true;
}

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

}
