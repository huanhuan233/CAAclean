#include "caa/CaaParameterReader.h"
#include "caa/CaaPropertyEvidence.h"
#include <CATICkeParm.h>
#include <CATICkeInst.h>
#include <CATICkeType.h>
#include <CATICkeMKSUnit.h>
#include <float.h>

namespace cadcapture {
static std::string SiUnit(CATICkeType* type)
{
  CATICkeMKSUnit_var mks = type->MKS();
  if (mks == NULL_var) return "";
  const char* symbols[] = {"m", "kg", "s", "A", "K", "cd", "mol", "price", "rad", "sr"};
  std::ostringstream result;
  for (int i = 0; i < 10; ++i)
  {
    int exponent = mks->Get(static_cast<CATICkeMKSUnit::Basic>(i));
    if (!exponent) continue;
    if (!result.str().empty()) result << "*";
    result << symbols[i];
    if (exponent != 1) result << "^" << exponent;
  }
  return result.str().empty() ? "1" : result.str();
}

PropertyFact ReadCaaParameter(CATICkeParm* parameter)
{
  PropertyFact fact = evidence::Failure("unavailable", "CATICkeParm.Value");
  fact.value_type = "unknown";
  if (!parameter) return fact;
  try
  {
    try { fact.display_name = evidence::Utf8(parameter->Name()); } catch (...) {}
    // 可选显示/权限元数据读取失败，不应吞掉已经可读的实际参数值。
    try { fact.raw_display_text = fact.display_value = evidence::Utf8(parameter->Show()); } catch (...) {}
    try { fact.read_only = static_cast<int>(parameter->IsReadOnly()) != 0; } catch (...) {}
    try { fact.hidden_status = parameter->IsHidden() ? "true" : "false"; } catch (...) {}
    CATICkeType_var type = parameter->Type();
    if (type == NULL_var) return fact;
    // 尺寸的 Type 不一定是 Real，必须检查其底层值类型，不能仅按名称判断。
    CATICkeType_var scalar = type->GetValueType();
    if (scalar == NULL_var) scalar = type;
    if (type->IsaString() || scalar->IsaString()) fact.value_type = "string";
    else if (type->IsaBoolean() || scalar->IsaBoolean()) fact.value_type = "boolean";
    else if (type->IsaInteger() || scalar->IsaInteger()) fact.value_type = "integer";
    else if (type->IsaReal() || scalar->IsaReal()) fact.value_type = "number";
    // 值暂不可读时仍保留已取得的类型；不把缺失值默认说成字符串。
    CATICkeInst_var value = parameter->Value();
    if (value == NULL_var) return fact;
    if (type->IsaString() || scalar->IsaString())
    {
      fact.raw_value = evidence::Utf8(value->AsString());
      fact.source_api = "CATICkeParm.Value.AsString";
    }
    else if (type->IsaBoolean() || scalar->IsaBoolean())
    {
      fact.value_type = "boolean";
      fact.raw_value = value->AsBoolean() ? "true" : "false";
      fact.source_api = "CATICkeParm.Value.AsBoolean";
    }
    else if (type->IsaInteger() || scalar->IsaInteger() || type->IsaReal() || scalar->IsaReal())
    {
      const bool integer = type->IsaInteger() || scalar->IsaInteger();
      double numeric = integer ? value->AsInteger() : value->AsReal();
      fact.value_type = integer ? "integer" : "number";
      if (!_finite(numeric)) { fact.read_status = "non_finite"; return fact; }
      fact.raw_value = evidence::Number(numeric);
      fact.has_normalized_numeric_value = true;
      fact.normalized_numeric_value = numeric;
      fact.source_api = integer ? "CATICkeParm.Value.AsInteger" : "CATICkeParm.Value.AsReal";
      // AsReal 返回 SI；不能把 Show 中的 mm/deg 后缀贴到这个数值上。
      fact.raw_unit = fact.normalized_unit = integer ? "1" : SiUnit(type);
      fact.normalization_status = fact.raw_unit.empty() ? "unit_unavailable" : "already_normalized";
    }
    else
    {
      fact.value_type = "unknown";
      fact.read_status = "unsupported_type";
      return fact;
    }
    fact.read_status = "available";
    if (fact.display_value.empty())
    {
      fact.display_value = fact.raw_value;
      fact.display_unit = fact.raw_unit;
    }
  }
  catch (...) { fact.read_status = "exception"; }
  return fact;
}
}
