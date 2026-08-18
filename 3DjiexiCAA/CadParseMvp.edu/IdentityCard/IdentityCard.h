// ���ļ��� CAA Framework �� IdentityCard��������Ϊ��ͨ C++ ����ʱ����ִ�С�
// AddPrereqComponent ��;��������������� CadParseMvp ����� R21 Framework ������
// Public ��ʾ����ֻʹ�ö�Ӧ Framework ���⹫���Ľӿ���Լ��
AddPrereqComponent("System", Public);
AddPrereqComponent("ObjectModelerBase", Public);
AddPrereqComponent("ObjectSpecsModeler", Public);
AddPrereqComponent("MecModInterfaces", Public);
// Purpose: provide Public CATISketch for sketch centerline evidence on Shaft/Groove revolutions.
AddPrereqComponent("SketcherInterfaces", Public);
// ��;���ṩ Public CATMathPoint/CATMathVector ����ѧ���������������ĵ�����ǻ������ȡ��
AddPrereqComponent("Mathematics", Public);
// ��;���ṩ Public CATBody/CATTopology/CATCell�����ڶ�ȡ����ʵ�����ʵ Face/Edge/Vertex ����ժҪ��
AddPrereqComponent("GMModelInterfaces", Public);
// Purpose: provide Public CATSurface/CATCurve analytic geometry interfaces for exact final B-Rep parameters.
AddPrereqComponent("GeometricObjects", Public);
// ��;���ṩ Public CATITPSDocument/CATITPSSet�����ڶ�ȡ FTA/TPS ���ϼ�ժҪ��
AddPrereqComponent("CATTPSInterfaces", Public);
// ��;���ṩ Public CATICkeParm/CATICkeType/CATICkeInst �����ͻ� String ������ȡ��Լ��
AddPrereqComponent("KnowledgeInterfaces", Public);
// ��;���ṩ Public CATIAHole/CATIALimit����ʵö�ٺͶ�Ӧ Automation C++ �ӿڡ�
AddPrereqComponent("PartInterfaces", Public);

// Purpose: expose Public CATIProduct for CATProduct reference/instance hierarchy extraction.
AddPrereqComponent("ProductStructure", Public);
AddPrereqComponent("ProductStructureInterfaces", Public);
// Purpose: provide Public CATIInertia for CATIA Properties > Mechanical values.
AddPrereqComponent("SpaceAnalysisInterfaces", Public);

