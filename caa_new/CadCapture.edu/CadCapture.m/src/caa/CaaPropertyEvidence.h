#ifndef CADCAPTURE_CAA_PROPERTY_EVIDENCE_H
#define CADCAPTURE_CAA_PROPERTY_EVIDENCE_H

#include "model/CaptureIdRegistry.h"
#include "model/ReconstructionPackage.h"
#include <CATUnicodeString.h>
#include <sstream>
#include <locale>
#include <vector>

namespace cadcapture {
namespace evidence {
inline std::string Utf8(const CATUnicodeString& value)
{
  std::vector<char> buffer((value.GetLengthInChar() + 1) * 4 + 1, 0);
  size_t count = 0;
  value.ConvertToUTF8(&buffer[0], &count);
  return std::string(&buffer[0], count < buffer.size() ? count : buffer.size() - 1);
}
inline std::string Number(double value)
{
  std::ostringstream out;
  out.imbue(std::locale::classic());
  out.precision(17);
  out << value;
  return out.str();
}
inline PropertyFact Text(const std::string& value, const std::string& api)
{
  PropertyFact fact;
  fact.raw_value = fact.raw_display_text = fact.display_value = value;
  fact.read_status = "available";
  fact.source_api = api;
  return fact;
}
inline PropertyFact Failure(const std::string& status, const std::string& api)
{
  PropertyFact fact;
  fact.read_status = status;
  fact.source_api = api;
  return fact;
}
inline void Append(CaptureIdRegistry& ids, ReconstructionPackage& package,
                   const std::string& subject, const std::string& group,
                   const std::string& key, const std::string& label, PropertyFact fact)
{
  // 空字符串是有效值；失败用 read_status 表达，不能伪造为 0 或空的成功值。
  fact.property_id = ids.NextPropertyFactId();
  fact.subject_id = subject;
  fact.tab_id = fact.tab_label = group;
  fact.group_id = fact.group_label = fact.group = group;
  fact.key = key;
  fact.display_name = label;
  fact.authority = "captured_native_tree";
  fact.display_order = 2000;
  package.properties.push_back(fact);
}
}
}
#endif
