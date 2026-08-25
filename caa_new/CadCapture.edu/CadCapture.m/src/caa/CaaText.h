#ifndef CADCAPTURE_CAA_CAATEXT_H
#define CADCAPTURE_CAA_CAATEXT_H

#include <CATUnicodeString.h>
#include <string>
#include <vector>

namespace cadcapture {

static std::string CaaUnicodeToUtf8Text(const CATUnicodeString& value)
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

}

#endif
