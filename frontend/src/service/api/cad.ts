import { request } from '../request';

export function fetchCadModels(params: { page?: number; page_size?: number } = {}) {
  return request<Api.Cad.PagedResult<Api.Cad.ModelSummary>>({
    url: '/api/cad/models',
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 20
    }
  });
}

export function uploadCadModel(file: File, name?: string) {
  const data = new FormData();
  data.append('file', file);
  if (name) {
    data.append('name', name);
  }

  return request<Api.Cad.UploadResponse>({
    url: '/api/cad/models',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}

export function fetchCadRevisionStatus(revisionId: string) {
  return request<Api.Cad.ParseStatus>({
    url: `/api/cad/revisions/${revisionId}/status`
  });
}

export function fetchCadRevisionTree(revisionId: string) {
  return request<Api.Cad.TreeNode[]>({
    url: `/api/cad/revisions/${revisionId}/tree`
  });
}

export function fetchCadStructureTree(revisionId: string) {
  return request<Api.Cad.TreeNode[]>({
    url: `/api/cad/revisions/${revisionId}/structure-tree`
  });
}

export function fetchCadEntities(
  revisionId: string,
  params: {
    parent_entity_id?: string;
    entity_type?: string;
    geometry_type?: string;
    keyword?: string;
    page?: number;
    page_size?: number;
  } = {}
) {
  return request<Api.Cad.PagedResult<Api.Cad.Entity>>({
    url: `/api/cad/revisions/${revisionId}/entities`,
    params
  });
}

export function fetchCadEntity(revisionId: string, entityId: string) {
  return request<Api.Cad.Entity>({
    url: `/api/cad/revisions/${revisionId}/entities/${entityId}`
  });
}

export function fetchCadMeshes(
  revisionId: string,
  params: {
    entity_id?: string;
    parent_entity_id?: string;
    page?: number;
    page_size?: number;
  } = {}
) {
  return request<Api.Cad.PagedResult<Api.Cad.Mesh>>({
    url: `/api/cad/revisions/${revisionId}/meshes`,
    params
  });
}

export function fetchCadFaceTopology(revisionId: string, faceId: string) {
  return request<Api.Cad.FaceTopology>({
    url: `/api/cad/revisions/${revisionId}/faces/${faceId}/topology`
  });
}

export function fetchCadEdgeTopology(revisionId: string, edgeId: string) {
  return request<Api.Cad.EdgeTopology>({
    url: `/api/cad/revisions/${revisionId}/edges/${edgeId}/topology`
  });
}

export function fetchCadMeasurements(
  revisionId: string,
  params: {
    measurement_type?: string;
    scope_entity_id?: string;
    confidence_min?: number;
    page?: number;
    page_size?: number;
  } = {}
) {
  return request<Api.Cad.PagedResult<Api.Cad.Measurement>>({
    url: `/api/cad/revisions/${revisionId}/measurements`,
    params
  });
}

export function fetchCadMeasurement(revisionId: string, measurementId: string) {
  return request<Api.Cad.Measurement>({
    url: `/api/cad/revisions/${revisionId}/measurements/${measurementId}`
  });
}

export function fetchCadFeatures(
  revisionId: string,
  params: {
    feature_type?: string;
    scope_entity_id?: string;
    confidence_min?: number;
    page?: number;
    page_size?: number;
  } = {}
) {
  return request<Api.Cad.PagedResult<Api.Cad.FeatureCandidate>>({
    url: `/api/cad/revisions/${revisionId}/features`,
    params
  });
}

export function fetchCadFeature(revisionId: string, featureId: string) {
  return request<Api.Cad.FeatureCandidate>({
    url: `/api/cad/revisions/${revisionId}/features/${featureId}`
  });
}

export function recomputeCadMeasurements(revisionId: string) {
  return request<{ revision_id: string; algorithm_version: string; feature_count: number; measurement_count: number }>({
    url: `/api/cad/revisions/${revisionId}/measurements/recompute`,
    method: 'post'
  });
}
