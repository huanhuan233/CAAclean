export interface FeatureMeshEntry {
  face_ids: string[];
  mesh_primitive_ids: string[];
}

export interface FeatureMeshMap {
  schema_version: string;
  shape_hash: string;
  features: Record<string, FeatureMeshEntry>;
}

export interface CanonicalFeatureRecord {
  feature_center_id: string;
  family: string;
  subtype: string;
  review_state: string;
  geometry_refs: { face_ids: string[] };
  native_feature_ids: string[];
  typed_payload: Record<string, unknown>;
  provenance: Record<string, unknown>;
}

// 用途：解析浏览器读取的 JSONL，空行不会生成伪记录，错误由调用界面统一显示。
export function parseJsonLines<T>(text: string): T[] {
  return text
    .split(/\r?\n/u)
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => JSON.parse(line) as T);
}

// 用途：按 Canonical Feature 编号返回稳定 Face 集合，供列表点击后高亮真实 Primitive。
export function facesForFeature(mapping: FeatureMeshMap, featureId: string): string[] {
  return [...(mapping.features[featureId]?.face_ids ?? [])].sort();
}

// 用途：建立 Face 到所有引用它的 Canonical Feature 的反向索引，支持共享证据面。
export function buildFaceToFeatureIndex(mapping: FeatureMeshMap): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const [featureId, entry] of Object.entries(mapping.features)) {
    for (const faceId of entry.face_ids) {
      (result[faceId] ??= []).push(featureId);
    }
  }
  for (const featureIds of Object.values(result)) {
    featureIds.sort();
  }
  return result;
}
