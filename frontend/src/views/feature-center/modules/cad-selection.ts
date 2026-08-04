import type { Intersection, Mesh, Object3D } from 'three';

export type CadSelectionKind = 'assembly' | 'part' | 'feature' | 'face' | 'edge' | 'vertex';

export interface CadSelectionTarget {
  source: 'step' | 'catia';
  kind: CadSelectionKind;
  stableId: string;
  objectUuid?: string;
  assemblyId?: string;
  instanceId?: string;
  partId?: string;
  featureId?: string;
  faceId?: string;
  edgeId?: string;
  vertexId?: string;
  sourceRef?: string;
  displayName?: string;
  raw?: unknown;
}

export interface FaceMeshLookup {
  primitive_to_face: Record<string, string>;
}

export interface PickableRegistration {
  pickables: Object3D[];
  faceObjects: Map<string, Mesh[]>;
  primitiveObjects: Map<string, Mesh[]>;
}

// 用途：把 STEP 与 CATPart 共用的 GLB Mesh 注册到同一拾取索引，并只采信 Bundle 中的稳定 Face/Primitive 标识。
export function registerCadPickables(root: Object3D, faceMap?: FaceMeshLookup | null): PickableRegistration {
  const pickables: Object3D[] = [];
  const faceObjects = new Map<string, Mesh[]>();
  const primitiveObjects = new Map<string, Mesh[]>();

  root.traverse(object => {
    const mesh = object as Mesh;
    if (!mesh.isMesh) return;
    const primitiveId = stringValue(mesh.geometry.userData.mesh_primitive_id ?? mesh.userData.mesh_primitive_id);
    const faceId = stringValue(
      mesh.geometry.userData.face_id ??
        mesh.userData.face_id ??
        (primitiveId ? faceMap?.primitive_to_face[primitiveId] : undefined)
    );
    if (primitiveId) {
      mesh.userData.mesh_primitive_id = primitiveId;
      append(primitiveObjects, primitiveId, mesh);
    }
    if (faceId) {
      mesh.userData.face_id = faceId;
      append(faceObjects, faceId, mesh);
    }
    mesh.userData.pickable = true;
    pickables.push(mesh);
  });

  return { pickables, faceObjects, primitiveObjects };
}

// 用途：将 Raycaster 命中转换为稳定业务对象；Face 缺失时降级为真实零件，不把三角形序号冒充 Face ID。
export function resolveCadSelection(
  hit: Intersection<Object3D>,
  source: 'step' | 'catia',
  faceMap: FaceMeshLookup | null | undefined,
  part: { partId: string; displayName?: string; sourceRef?: string }
): CadSelectionTarget {
  const primitiveId = stringValue(hit.object.userData.mesh_primitive_id);
  const faceId = stringValue(
    hit.object.userData.face_id ?? (primitiveId ? faceMap?.primitive_to_face[primitiveId] : undefined)
  );
  if (faceId) {
    return {
      source,
      kind: 'face',
      stableId: faceId,
      objectUuid: hit.object.uuid,
      partId: part.partId,
      faceId,
      sourceRef: primitiveId || part.sourceRef,
      raw: hit
    };
  }
  return {
    source,
    kind: 'part',
    stableId: part.partId,
    objectUuid: hit.object.uuid,
    partId: part.partId,
    displayName: part.displayName,
    sourceRef: part.sourceRef,
    raw: hit
  };
}

function append(index: Map<string, Mesh[]>, key: string, mesh: Mesh) {
  const values = index.get(key) || [];
  values.push(mesh);
  index.set(key, values);
}

function stringValue(value: unknown) {
  return typeof value === 'string' && value ? value : '';
}
