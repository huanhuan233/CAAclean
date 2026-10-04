#include "caa/CaaFtaTypedReader.h"
#include "caa/CaaGuards.h"

#include <CATITPSComponent.h>
#include <CATITPS.h>
#include <CATITPSDimension.h>
#include <CATITPSLinearDimension.h>
#include <CATITPSAngularDimension.h>
#include <CATITPSDimensionLimits.h>
#include <CATITPSSemanticGDTTolerance.h>
#include <CATITPSToleranceZone.h>
#include <CATITPSCompositeTolerance.h>
#include <CATITPSAssociatedRefFrame.h>
#include <CATITPSReferenceFrame.h>
#include <CATITPSList.h>
#include <CATITPSNonSemanticGDT.h>
#include <CATITPSRoughness.h>
#include <CATITPSDatum.h>
#include <CATITPSDatumSimple.h>
#include <CATITPSDatumSystem.h>
#include <CATITPSFlagNote.h>
#include <CATITPSNoa.h>
#include <CATITPSText.h>
#include <CATITTRSList.h>
#include <CATITTRS.h>
#include <CATUnicodeString.h>
#include <sstream>
#include <vector>

namespace cadcapture {

static std::string Utf8(const wchar_t* value)
{
  if (!value) return "";
  CATUnicodeString unicode;
  unicode.BuildFromWChar(value);
  std::vector<char> buffer(static_cast<size_t>(unicode.GetLengthInChar() + 1) * 4 + 1, 0);
  size_t count = 0;
  unicode.ConvertToUTF8(&buffer[0], &count);
  if (count >= buffer.size()) count = buffer.size() - 1;
  return std::string(&buffer[0], count);
}

static std::string Number(double value)
{
  std::ostringstream out;
  out.precision(17);
  out << value;
  return out.str();
}

static void Field(FtaSemanticEntity& entity, const std::string& key,
                  const std::string& value, const std::string& unit,
                  const std::string& status, const std::string& api)
{
  FtaRawField field;
  field.key = key;
  field.raw_value = value;
  field.unit = unit;
  field.read_status = status;
  field.source_api = api;
  entity.raw_fields.push_back(field);
}

static void AssignKind(FtaSemanticEntity& entity, const char* kind)
{
  const std::string previous = entity.component_kind;
  if (previous.empty() || previous == "unknown" || previous == "unknown_tps_component" || previous == "tps" || previous == "text")
    entity.component_kind = kind;
  else if ((previous == "datum" && (std::string(kind) == "datum_simple" || std::string(kind) == "datum_system")) ||
           (previous == "gdt_nonsemantic" && std::string(kind) == "gdt"))
    entity.component_kind = kind;
  else if (previous != kind && previous != "multiple_tps_types")
  {
    Field(entity, "component_kind_conflict", previous + "," + kind, "", "needs_review", "QueryInterface");
    entity.component_kind = "multiple_tps_types";
  }
}

static void TextField(FtaSemanticEntity& entity, const std::string& key,
                      wchar_t* value, HRESULT result, const std::string& api)
{
  const std::string raw = value ? Utf8(value) : "";
  Field(entity, key, raw, "", FAILED(result) ? "failed" : raw.empty() ? "empty" : "available", api);
  delete [] value;
}

template<class T> static bool Probe(CATITPSComponent* component, const IID& iid,
                                    const char* name, FtaSemanticEntity& entity,
                                    CaaInterfaceGuard<T>& guard)
{
  try
  {
    if (FAILED(component->QueryInterface(iid, reinterpret_cast<void**>(&guard.Out()))) || !guard.Get())
      return false;
    entity.supported_interface_keys.push_back(name);
    return true;
  }
  catch (...) { return false; }
}

void ReadFtaTypedFields(CATITPSComponent* component, FtaSemanticEntity& entity)
{
  if (!component) return;
  CaaInterfaceGuard<CATITPSDimension> dimension;
  if (Probe(component, IID_CATITPSDimension, "CATITPSDimension", entity, dimension))
  {
    AssignKind(entity, "dimension");
    CaaInterfaceGuard<CATITPSAngularDimension> angular;
    const bool angular_dimension = Probe(component, IID_CATITPSAngularDimension,
                                         "CATITPSAngularDimension", entity, angular);
    CaaInterfaceGuard<CATITPSLinearDimension> linear;
    const bool linear_dimension = Probe(component, IID_CATITPSLinearDimension,
                                        "CATITPSLinearDimension", entity, linear);
    // R21 documents limits in millimetres, but angular and unclassified
    // dimensions need subtype-specific evidence before unit normalization.
    const std::string value_unit = linear_dimension && !angular_dimension ? "mm" : "unknown";
    if (linear_dimension)
    {
      CATTPSLinearDimensionSubType subtype;
      const HRESULT result = linear.Get()->GetLinearDimSubType(&subtype);
      Field(entity, "linear_subtype_raw", SUCCEEDED(result) ? Number(static_cast<long>(subtype)) : "",
            "", SUCCEEDED(result) ? "available" : "failed", "CATITPSLinearDimension.GetLinearDimSubType");
    }
    CaaInterfaceGuard<CATITPSDimensionLimits> limits;
    if (Probe(component, IID_CATITPSDimensionLimits, "CATITPSDimensionLimits", entity, limits))
    {
      CATTPSDimLimType kind;
      HRESULT result = limits.Get()->GetDimensionLimitType(&kind);
      Field(entity, "limit_type_raw", SUCCEEDED(result) ? Number(static_cast<long>(kind)) : "", "",
            SUCCEEDED(result) ? "available" : "failed", "CATITPSDimensionLimits.GetDimensionLimitType");
      double nominal = 0;
      result = limits.Get()->GetNominalValue(&nominal);
      Field(entity, "nominal_value", SUCCEEDED(result) ? Number(nominal) : "", value_unit,
            SUCCEEDED(result) ? "available" : "failed", "CATITPSDimensionLimits.GetNominalValue");
      double bottom = 0, upper = 0;
      result = limits.Get()->GetLimits(&bottom, &upper);
      Field(entity, "lower_limit", SUCCEEDED(result) ? Number(bottom) : "", value_unit,
            SUCCEEDED(result) ? "available" : "failed", "CATITPSDimensionLimits.GetLimits");
      Field(entity, "upper_limit", SUCCEEDED(result) ? Number(upper) : "", value_unit,
            SUCCEEDED(result) ? "available" : "failed", "CATITPSDimensionLimits.GetLimits");
    }
    else Field(entity, "dimension_values", "", "", "unsupported", "CATITPSDimensionLimits");
  }

  CaaInterfaceGuard<CATITPSSemanticGDTTolerance> gdt;
  if (Probe(component, IID_CATITPSSemanticGDTTolerance, "CATITPSSemanticGDTTolerance", entity, gdt))
  {
    AssignKind(entity, "gdt");
    int precision = 0;
    const HRESULT result = gdt.Get()->GetPrecision(&precision);
    Field(entity, "precision_raw", SUCCEEDED(result) ? Number(precision) : "", "",
          SUCCEEDED(result) ? "available" : "failed", "CATITPSSemanticGDTTolerance.GetPrecision");
    CaaInterfaceGuard<CATITPSToleranceZone> zone;
    if (Probe(component, IID_CATITPSToleranceZone, "CATITPSToleranceZone", entity, zone))
    {
      double tolerance = 0;
      HRESULT value_result = zone.Get()->GetValue(&tolerance);
      Field(entity, "tolerance_zone_value", SUCCEEDED(value_result) ? Number(tolerance) : "", "mm",
            SUCCEEDED(value_result) ? "available" : "failed", "CATITPSToleranceZone.GetValue");
      CATTPSToleranceZoneForm form;
      HRESULT form_result = zone.Get()->GetForm(&form);
      Field(entity, "tolerance_zone_form_raw", SUCCEEDED(form_result) ? Number(static_cast<long>(form)) : "", "",
            SUCCEEDED(form_result) ? "available" : "failed", "CATITPSToleranceZone.GetForm");
    }
    else Field(entity, "tolerance_zone_value", "", "", "not_verified", "CATITPSToleranceZone");
    CaaInterfaceGuard<CATITPSCompositeTolerance> composite;
    if (Probe(component, IID_CATITPSCompositeTolerance, "CATITPSCompositeTolerance", entity, composite))
    {
      double value = 0;
      HRESULT value_result = composite.Get()->GetCompositeValue(&value);
      Field(entity, "composite_tolerance_value", SUCCEEDED(value_result) ? Number(value) : "", "mm",
            SUCCEEDED(value_result) ? "available" : "failed", "CATITPSCompositeTolerance.GetCompositeValue");
      unsigned int box_count = 0;
      HRESULT count_result = composite.Get()->GetBoxCount(&box_count);
      Field(entity, "composite_box_count", SUCCEEDED(count_result) ? Number(box_count) : "", "",
            SUCCEEDED(count_result) ? "available" : "failed", "CATITPSCompositeTolerance.GetBoxCount");
    }
    CaaInterfaceGuard<CATITPSAssociatedRefFrame> associated_frame;
    if (Probe(component, IID_CATITPSAssociatedRefFrame, "CATITPSAssociatedRefFrame", entity, associated_frame))
    {
      CATITPSReferenceFrame* frame = 0;
      HRESULT frame_result = associated_frame.Get()->GetReferenceFrame(&frame);
      if (SUCCEEDED(frame_result) && frame)
      {
        CaaInterfaceGuard<CATITPSReferenceFrame> frame_guard(frame);
        wchar_t *first = 0, *second = 0, *third = 0;
        HRESULT boxes_result = frame->GetFrame(&first, &second, &third);
        Field(entity, "datum_reference_frame_boxes", SUCCEEDED(boxes_result) ?
              (Utf8(first) + "|" + Utf8(second) + "|" + Utf8(third)) : "", "",
              SUCCEEDED(boxes_result) ? "available" : "failed", "CATITPSReferenceFrame.GetFrame");
        delete [] first; delete [] second; delete [] third;
        CATITPSList* datums = 0;
        HRESULT datums_result = frame->GetAllDatumsSimple(&datums);
        if (SUCCEEDED(datums_result) && datums)
        {
          CaaInterfaceGuard<CATITPSList> datums_guard(datums);
          unsigned int datum_count = 0;
          HRESULT count_result = datums->Count(&datum_count);
          Field(entity, "datum_reference_count", SUCCEEDED(count_result) ? Number(datum_count) : "", "",
                SUCCEEDED(count_result) ? "available" : "failed", "CATITPSReferenceFrame.GetAllDatumsSimple.Count");
        }
      }
      else Field(entity, "datum_reference_frame_boxes", "", "", "failed", "CATITPSAssociatedRefFrame.GetReferenceFrame");
    }
  }
  CaaInterfaceGuard<CATITPSNonSemanticGDT> nonsemantic_gdt;
  if (Probe(component, IID_CATITPSNonSemanticGDT, "CATITPSNonSemanticGDT", entity, nonsemantic_gdt))
  {
    if (entity.component_kind != "gdt")
    {
      AssignKind(entity, "gdt_nonsemantic");
      Field(entity, "tolerance_value", "", "", "unsupported", "CATITPSNonSemanticGDT");
    }
  }

  CaaInterfaceGuard<CATITPSRoughness> roughness;
  if (Probe(component, IID_CATITPSRoughness, "CATITPSRoughness", entity, roughness))
  {
    AssignKind(entity, "roughness");
    for (int index = 1; index <= 9; ++index)
    {
      std::ostringstream key;
      key << "field_" << index;
      wchar_t* raw = 0;
      HRESULT result = E_FAIL;
      try { result = roughness.Get()->GetField(index, &raw); } catch (...) {}
      TextField(entity, key.str(), raw, result, "CATITPSRoughness.GetField");
    }
  }

  CaaInterfaceGuard<CATITPSDatum> datum;
  if (Probe(component, IID_CATITPSDatum, "CATITPSDatum", entity, datum))
    AssignKind(entity, "datum");
  CaaInterfaceGuard<CATITPSDatumSimple> simple_datum;
  if (Probe(component, IID_CATITPSDatumSimple, "CATITPSDatumSimple", entity, simple_datum))
  {
    AssignKind(entity, "datum_simple");
    wchar_t* label = 0;
    HRESULT result = E_FAIL;
    try { result = simple_datum.Get()->GetLabel(&label); } catch (...) {}
    TextField(entity, "datum_label", label, result, "CATITPSDatumSimple.GetLabel");
  }
  CaaInterfaceGuard<CATITPSDatumSystem> system_datum;
  if (Probe(component, IID_CATITPSDatumSystem, "CATITPSDatumSystem", entity, system_datum))
  {
    AssignKind(entity, "datum_system");
    wchar_t* label = 0;
    HRESULT result = E_FAIL;
    try { result = system_datum.Get()->GetLabel(&label); } catch (...) {}
    TextField(entity, "datum_label", label, result, "CATITPSDatumSystem.GetLabel");
  }

  CaaInterfaceGuard<CATITPSFlagNote> flag;
  if (Probe(component, IID_CATITPSFlagNote, "CATITPSFlagNote", entity, flag))
  {
    AssignKind(entity, "flag_note");
    wchar_t* flag_text = 0;
    HRESULT result = E_FAIL;
    try { result = flag.Get()->GetFlagText(&flag_text); } catch (...) {}
    TextField(entity, "flag_text", flag_text, result, "CATITPSFlagNote.GetFlagText");
    int count = 0;
    result = flag.Get()->GetUrlListSize(&count);
    if (SUCCEEDED(result) && count >= 0 && count <= 1000)
      for (int index = 0; index < count; ++index)
      {
        wchar_t* url = 0;
        result = flag.Get()->GetURL(index, &url);
        std::ostringstream key; key << "external_url_" << index;
        TextField(entity, key.str(), url, result, "CATITPSFlagNote.GetURL");
      }
    else Field(entity, "external_urls", "", "", "failed", "CATITPSFlagNote.GetUrlListSize");
  }

  CaaInterfaceGuard<CATITPSNoa> noa;
  if (Probe(component, IID_CATITPSNoa, "CATITPSNoa", entity, noa))
  {
    AssignKind(entity, "noa");
    wchar_t* type = 0;
    HRESULT result = E_FAIL;
    try { result = noa.Get()->GetNoaType(&type); } catch (...) {}
    TextField(entity, "noa_type", type, result, "CATITPSNoa.GetNoaType");
    wchar_t* flag_text = 0;
    result = E_FAIL;
    try { result = noa.Get()->GetFlagText(&flag_text); } catch (...) {}
    TextField(entity, "flag_text", flag_text, result, "CATITPSNoa.GetFlagText");
    int count = 0;
    result = noa.Get()->GetUrlListSize(&count);
    if (SUCCEEDED(result) && count >= 0 && count <= 1000)
      for (int index = 0; index < count; ++index)
      {
        wchar_t* url = 0;
        result = noa.Get()->GetURL(index, &url);
        std::ostringstream key; key << "external_url_" << index;
        TextField(entity, key.str(), url, result, "CATITPSNoa.GetURL");
      }
    else Field(entity, "external_urls", "", "", "failed", "CATITPSNoa.GetUrlListSize");
  }

  CaaInterfaceGuard<CATITPSText> text;
  if (Probe(component, IID_CATITPSText, "CATITPSText", entity, text))
  {
    // Several specific TPS types also expose text; keep their more precise kind.
    AssignKind(entity, "text");
  }

  CaaInterfaceGuard<CATITPS> tps;
  if (Probe(component, IID_CATITPS, "CATITPS", entity, tps))
  {
    CATITTRSList* list = 0;
    try
    {
      if (SUCCEEDED(tps.Get()->GetTTRS(&list)) && list)
      {
        CaaInterfaceGuard<CATITTRSList> guard(list);
        unsigned int count = 0;
        if (SUCCEEDED(list->Count(&count)))
        {
          entity.annotation_ttrs_count = count;
          entity.annotation_ttrs_status = "available";
          entity.native_geometry_link_status = count ? "native_ttrs_unmapped" : "no_ttrs_returned";
          for (unsigned int index = 0; index < count && index < 1000; ++index)
          {
            CATITTRS* ttrs = 0;
            if (SUCCEEDED(list->Item(index, &ttrs)) && ttrs)
            {
              CaaInterfaceGuard<CATITTRS> ttrs_guard(ttrs);
              std::ostringstream key; key << "ttrs_" << index << "_nature_raw";
              Field(entity, key.str(), Number(static_cast<long>(ttrs->GetNature())), "",
                    "available", "CATITTRS.GetNature");
              CATMmrTTRSClass ttrs_class;
              key.str(""); key.clear(); key << "ttrs_" << index << "_class_raw";
              HRESULT class_result = ttrs->GetTTRSClass(ttrs_class);
              Field(entity, key.str(), SUCCEEDED(class_result) ? Number(static_cast<long>(ttrs_class)) : "", "",
                    SUCCEEDED(class_result) ? "available" : "failed", "CATITTRS.GetTTRSClass");
              CATLISTV(CATBaseUnknown_var) components;
              key.str(""); key.clear(); key << "ttrs_" << index << "_component_count";
              HRESULT component_result = ttrs->GetComponents(components);
              Field(entity, key.str(), SUCCEEDED(component_result) ? Number(components.Size()) : "", "",
                    SUCCEEDED(component_result) ? "available" : "failed", "CATITTRS.GetComponents");
              key.str(""); key.clear(); key << "ttrs_" << index << "_reference_status";
              Field(entity, key.str(), "unresolved_native_components", "", "not_verified",
                    "CATITTRS.GetComponents");
            }
          }
        }
        else entity.annotation_ttrs_status = "failed";
      }
      else entity.annotation_ttrs_status = "failed";
    }
    catch (...) { entity.annotation_ttrs_status = "exception"; }
  }
}

}
