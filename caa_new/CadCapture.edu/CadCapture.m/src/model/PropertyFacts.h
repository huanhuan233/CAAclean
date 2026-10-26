/* 定义保留原值、显示值、单位及来源的属性事实。 */
#ifndef CADCAPTURE_MODEL_PROPERTYFACTS_H
#define CADCAPTURE_MODEL_PROPERTYFACTS_H

#include <string>

namespace cadcapture {

/* 一项可追溯的属性事实，原始读取值、界面显示值与规范数值分别保留。 */
struct PropertyFact
{
  std::string property_id;
  std::string subject_id;
  std::string tab_id;
  std::string tab_label;
  std::string group_id;
  std::string group_label;
  std::string group;
  std::string key;
  std::string display_name;
  std::string raw_value;
  std::string raw_unit;
  std::string raw_display_text;
  std::string display_value;
  std::string display_unit;
  std::string value_type;
  /* 规范数值必须由标志和 normalization_status 判定有效，零值不能充当缺失值。 */
  bool has_normalized_numeric_value;
  double normalized_numeric_value;
  /* 单位随规范数值一并保存，消费者不能把原始单位直接套用到规范值。 */
  std::string normalized_unit;
  std::string normalization_status;
  std::string source_api;
  std::string read_status;
  std::string authority;
  long display_order;
  bool read_only;
  std::string hidden_status;

  PropertyFact()
    : value_type("string"),
      has_normalized_numeric_value(false),
      normalized_numeric_value(0.0),
      normalization_status("not_applicable"),
      read_status("unavailable"),
      display_order(0),
      read_only(true),
      hidden_status("unknown")
  {
  }
};

}

#endif
