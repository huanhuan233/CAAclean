/* RADE 编译桥接：将重建规划和完整性校验实现纳入当前编译单元，避免对子目录实现重复编译。 */
#include "reconstruction/ReconstructionPlanner.cpp"
#include "reconstruction/ReconstructionValidator.cpp"
#include "reconstruction/BrepCompleteness.cpp"
