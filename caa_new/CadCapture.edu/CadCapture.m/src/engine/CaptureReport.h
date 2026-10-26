/* 定义命令行采集报告，汇总退出状态、对象数量和诊断。 */
#ifndef CADCAPTURE_ENGINE_CAPTUREREPORT_H
#define CADCAPTURE_ENGINE_CAPTUREREPORT_H

#include "model/CaptureStatus.h"
#include <string>
#include <vector>

namespace cadcapture {

/* 对外报告与包内原始证据分开，数量字段只汇总已采集记录。 */
struct CaptureReport
{
  int exit_code;
  bool success;
  std::string stage;
  std::string message;
  int document_count;
  int object_count;
  int occurrence_count;
  int property_count;
  int semantic_facet_count;
  int topology_count;
  int geometry_count;
  int pmi_count;
  std::vector<Diagnostic> diagnostics;

  /* 默认按未成功状态初始化，避免尚未执行的任务被报告为成功。 */
  CaptureReport()
    : exit_code(1),
      success(false),
      document_count(0),
      object_count(0),
      occurrence_count(0),
      property_count(0),
      semantic_facet_count(0),
      topology_count(0),
      geometry_count(0),
      pmi_count(0)
  {
  }

  /* 追加带阶段与对象身份的诊断，不改变已有事实。 */
  void AddDiagnostic(const std::string& severity,
                     const std::string& code,
                     const std::string& subject_id,
                     const std::string& text,
                     const std::string& at_stage)
  {
    diagnostics.push_back(MakeDiagnostic(severity, code, subject_id, text, at_stage));
  }

  /* 仅检查 error 严重度；warning 的策略处理由采集结果汇总负责。 */
  bool HasErrors() const
  {
    size_t i;
    for (i = 0; i < diagnostics.size(); ++i)
    {
      if (diagnostics[i].severity == "error")
        return true;
    }
    return false;
  }
};

}

#endif
