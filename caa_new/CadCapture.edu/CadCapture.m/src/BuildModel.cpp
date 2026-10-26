/* RADE 编译桥接：将模型身份、证据汇总与 Windows 路径支持实现纳入当前编译单元，避免对子目录实现重复编译。 */
#include "model/SdkCatalog.cpp"
#include "model/CaptureIdRegistry.cpp"
#include "model/GeometryStatusProjector.cpp"
#include "engine/CaptureOutcome.cpp"
#include "model/CaptureEvidenceSummary.cpp"
#include "platform/WindowsPathCodec.cpp"
#include "platform/WindowsDirectoryAlias.cpp"
