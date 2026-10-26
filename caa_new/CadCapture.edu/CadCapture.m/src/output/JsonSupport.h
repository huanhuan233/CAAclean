/* 提供 JSON 字符串转义和加引号的公共辅助函数。 */
#ifndef CADCAPTURE_OUTPUT_JSONSUPPORT_H
#define CADCAPTURE_OUTPUT_JSONSUPPORT_H

#include <sstream>
#include <string>

namespace cadcapture {

/* 转义 JSON 特殊字符和控制字节，其他字节原样保留；调用方负责提供有效文本编码。 */
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

/* 在转义结果两侧补双引号，返回可直接写入的 JSON 字符串值。 */
static std::string JsonQuote(const std::string& value)
{
  return std::string("\"") + JsonEscape(value) + "\"";
}

}

#endif
