// 定义是否允许部分采集及提交前是否执行逻辑校验的策略开关。
#ifndef CADCAPTURE_ENGINE_CAPTUREPOLICY_H
#define CADCAPTURE_ENGINE_CAPTUREPOLICY_H

namespace cadcapture {

// 采集容错策略与发布前检查策略分别控制，不等同于几何支持能力。
struct CapturePolicy
{
  // 中文：严格模式拒绝必需采集阶段的部分结果；默认保留带诊断的包。
  bool allow_partial_capture;
  // 中文：可跳过提交前逻辑校验，但输出事务的文件完整性校验始终执行。
  bool validate_before_commit;

  // 中文：默认保持既有部分采集兼容性，同时启用逻辑校验。
  CapturePolicy()
    : allow_partial_capture(true),
      validate_before_commit(true)
  {
  }
};

}

#endif
