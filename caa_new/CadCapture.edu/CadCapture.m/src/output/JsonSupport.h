#ifndef CADCAPTURE_OUTPUT_JSONSUPPORT_H
#define CADCAPTURE_OUTPUT_JSONSUPPORT_H

#include <sstream>
#include <string>

namespace cadcapture {

static std::string JsonEscape(const std::string& value)
{
  std::ostringstream out;
  size_t i;
  for (i = 0; i < value.size(); ++i)
  {
    const unsigned char c = static_cast<unsigned char>(value[i]);
    switch (c)
    {
    case '"': out << "\\\""; break;
    case '\\': out << "\\\\"; break;
    case '\b': out << "\\b"; break;
    case '\f': out << "\\f"; break;
    case '\n': out << "\\n"; break;
    case '\r': out << "\\r"; break;
    case '\t': out << "\\t"; break;
    default:
      if (c < 32)
      {
        const char* hex = "0123456789abcdef";
        out << "\\u00" << hex[(c >> 4) & 0x0f] << hex[c & 0x0f];
      }
      else
      {
        out << value[i];
      }
      break;
    }
  }
  return out.str();
}

static std::string JsonQuote(const std::string& value)
{
  return std::string("\"") + JsonEscape(value) + "\"";
}

}

#endif
