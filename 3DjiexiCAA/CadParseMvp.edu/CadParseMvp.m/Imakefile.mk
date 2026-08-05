# CATIA V5R21 CAA batch executable.
BUILT_OBJECT_TYPE=LOAD MODULE

OS = COMMON

LOCAL_CCFLAGS = /EHsc

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
  CATPartInterfaces \
  PartInterfacesUUID \
  CATProductStructure1 \
  CATProductStructureInterfaces \
  ProductStructureUUID
