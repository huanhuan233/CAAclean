#ifndef CADCAPTURE_CAA_CAANATIVEHANDLE_H
#define CADCAPTURE_CAA_CAANATIVEHANDLE_H

#include <sstream>
#include <string>

namespace cadcapture {

static std::string CaaSessionLocalHandleKey(const void* pointer)
{
  std::ostringstream out;
  out << pointer;
  return out.str();
}

}

#endif
