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
