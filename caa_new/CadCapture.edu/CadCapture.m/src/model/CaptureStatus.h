/* 定义采集诊断记录及统一构造诊断的辅助函数。 */
#ifndef CADCAPTURE_MODEL_CAPTURESTATUS_H
#define CADCAPTURE_MODEL_CAPTURESTATUS_H

#include <string>

namespace cadcapture {

/* 诊断记录包含严重性、机器可读代码、关联主体及产生阶段。 */
struct Diagnostic
{
  std::string severity;
  std::string code;
  std::string subject_id;
  std::string message;
  std::string stage;

  Diagnostic() : severity("info") {}
};

/* 按调用方提供的严重性和阶段生成诊断，不自动推断或覆盖主体身份。 */
static Diagnostic MakeDiagnostic(const std::string& severity,
                                 const std::string& code,
                                 const std::string& subject_id,
                                 const std::string& message,
                                 const std::string& stage)
{
  Diagnostic diagnostic;
  diagnostic.severity = severity;
  diagnostic.code = code;
  diagnostic.subject_id = subject_id;
  diagnostic.message = message;
  diagnostic.stage = stage;
  return diagnostic;
}

}

#endif
