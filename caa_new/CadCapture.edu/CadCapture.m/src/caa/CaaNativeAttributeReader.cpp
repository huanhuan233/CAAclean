#include "caa/CaaNativeAttributeReader.h"
#include "caa/CaaPropertyEvidence.h"
#include "caa/CaaGuards.h"
#include <CATISpecObject.h>
#include <CATISpecAttrAccess.h>
#include <CATISpecAttrKey.h>
#include <CATLISTV_CATISpecAttrKey.h>

namespace cadcapture {
std::vector<PropertyFact> ReadCaaNativeAttributes(CATISpecObject* spec)
{
  std::vector<PropertyFact> facts;
  CaaInterfaceGuard<CATISpecAttrAccess> access;
  if (!spec || FAILED(spec->QueryInterface(IID_CATISpecAttrAccess, reinterpret_cast<void**>(&access.Out()))) || !access.Get()) return facts;
  CATListValCATISpecAttrKey_var keys;
  if (FAILED(access.Get()->ListAttrKeys(keys)))
  {
    PropertyFact failed = evidence::Failure("failed", "CATISpecAttrAccess.ListAttrKeys");
    failed.key = "native_attribute_scan_status";
    facts.push_back(failed);
    return facts;
  }
  for (int i = 1; i <= keys.Size(); ++i)
  {
    PropertyFact fact = evidence::Failure("unavailable", "CATISpecAttrAccess");
    fact.key = "native_attribute_index:" + evidence::Number(i);
    try
    {
      CATISpecAttrKey_var key = keys[i];
      if (key == NULL_var) { facts.push_back(fact); continue; }
      fact.display_name = evidence::Utf8(key->GetName());
      fact.key = "native_attribute:" + fact.display_name;
      if (!access.Get()->TestAttributeValue(key)) { fact.read_status = "unset"; facts.push_back(fact); continue; }
      const CATAttrKind kind = key->GetType();
      if (kind == tk_double || kind == tk_integer || kind == tk_octet)
      {
        double value = kind == tk_double ? access.Get()->GetDouble(key) :
                       kind == tk_integer ? access.Get()->GetInteger(key) : access.Get()->GetOctet(key);
        fact.raw_value = evidence::Number(value);
        fact.value_type = kind == tk_double ? "number" : "integer";
        // 原生存储属性不保证是 SI，未知单位必须保留未知，不能自动标准化。
        fact.normalization_status = "unit_unavailable";
        fact.source_api = "CATISpecAttrAccess.GetDouble/GetInteger/GetOctet";
      }
      else if (kind == tk_boolean)
      {
        fact.raw_value = access.Get()->GetBoolean(key) ? "true" : "false";
        fact.value_type = "boolean";
        fact.source_api = "CATISpecAttrAccess.GetBoolean";
      }
      else if (kind == tk_string)
      {
        fact.raw_value = evidence::Utf8(access.Get()->GetString(key));
        fact.source_api = "CATISpecAttrAccess.GetString";
      }
      else
      {
        // 列表和引用只保留 SDK 的原始表示，不递归解引用以免循环或加载外部文件。
        fact.raw_value = evidence::Utf8(access.Get()->DumpValue(key));
        fact.value_type = "native_dump";
        fact.source_api = "CATISpecAttrAccess.DumpValue";
      }
      fact.raw_display_text = fact.display_value = fact.raw_value;
      fact.read_status = "available";
    }
    catch (...) { fact.read_status = "exception"; }
    facts.push_back(fact);
  }
  return facts;
}
}
