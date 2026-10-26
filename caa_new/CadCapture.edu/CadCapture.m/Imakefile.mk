# 定义 CadCapture 可执行模块的编译选项和链接库，沿用 R21/VS2008 构建机制。
BUILT_OBJECT_TYPE=LOAD MODULE

OS = COMMON

LOCAL_CCFLAGS = /EHsc /Y- /I"src"

LINK_WITH = \
  JS0GROUP \
  CATObjectModelerBase \
  CATObjectSpecsModeler \
  CATMecModInterfaces \
  CATSketcherInterfaces \
  CATMathematics \
  CATGMModelInterfaces \
  CATGeometricObjects \
  GeometricObjectsUUID \
  CATTPSItf \
  CATTPSUUID \
  KnowledgeItf \
  CATGitInterfaces \
  CATMeasureGeometryInterfaces \
  CAACompositesItf \
  CAACompositesItfUUID \
  CATCompositesPubIDL \
  CATMatInterfaces \
  CATVisualization \
  CATGraphicProperties \
  CATPartInterfaces \
  PartInterfacesUUID \
  CATProductStructure1 \
  CATProductStructureInterfaces \
  ProductStructureUUID \
  CATSaiSpaceAnalysisItf
