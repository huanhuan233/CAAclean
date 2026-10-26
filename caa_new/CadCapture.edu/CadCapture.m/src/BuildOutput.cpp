/* RADE 编译桥接：将产物事务、规范写出与兼容投影实现纳入当前编译单元，避免对子目录实现重复编译。 */
#include "output/ArtifactRepository.cpp"
#include "output/NormalizedArtifactWriter.cpp"
#include "output/LegacyArtifactProjection.cpp"
