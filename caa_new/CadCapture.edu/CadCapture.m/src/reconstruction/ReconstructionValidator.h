/* 声明采集包逻辑一致性校验接口，检查身份、层级和跨记录引用。 */
#ifndef CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONVALIDATOR_H
#define CADCAPTURE_RECONSTRUCTION_RECONSTRUCTIONVALIDATOR_H

#include "model/ReconstructionPackage.h"
#include <string>

namespace cadcapture {

/* 统一检查包内引用一致性，不等于已经验证所有曲面参数的物理正确性。 */
class ReconstructionValidator
{
public:
  /* 遇到首个结构错误返回 false，并给出包含相关身份的原因。 */
  bool Validate(const ReconstructionPackage& package, std::string& error) const;
};

}

#endif
