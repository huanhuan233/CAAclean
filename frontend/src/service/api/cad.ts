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

export function createCadSpecTask(params: {
  revision_id: string;
  drawing_file: File;
  target_code?: string;
  target_dn?: string | number;
}) {
  const data = new FormData();
  data.append('revision_id', params.revision_id);
  data.append('drawing_file', params.drawing_file);
  if (params.target_code) data.append('target_code', params.target_code);
  if (params.target_dn !== undefined && params.target_dn !== null && params.target_dn !== '') {
    data.append('target_dn', String(params.target_dn));
  }

  return request<Api.CadSpec.Task>({
    url: '/api/cad/spec/tasks',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}

export function fetchCadSpecTasks(params: { revision_id?: string } = {}) {
  return request<Api.Cad.PagedResult<Api.CadSpec.TaskSummary>>({
    url: '/api/cad/spec/tasks',
    params
  });
}

export function startCadSpecLayout(taskId: string) {
  return request<Api.CadSpec.LayoutStartResponse>({
    url: `/api/cad/spec/tasks/${taskId}/layout`,
    method: 'post'
  });
}

export function fetchCadSpecLayoutStatus(taskId: string) {
  return request<Api.CadSpec.LayoutStatus>({
    url: `/api/cad/spec/tasks/${taskId}/layout/status`
  });
}

export function fetchCadSpecRegions(taskId: string) {
  return request<Api.Cad.PagedResult<Api.CadSpec.Region>>({
    url: `/api/cad/spec/tasks/${taskId}/regions`
  });
}

export function extractCadSpecTask(taskId: string, payload: { force?: boolean }) {
  return request<Api.CadSpec.ExtractResponse>({
    url: `/api/cad/spec/tasks/${taskId}/extract`,
    method: 'post',
    data: payload
  });
}

export function fetchCadSpecExtractionStatus(taskId: string) {
  return request<Api.CadSpec.ExtractionStatus>({
    url: `/api/cad/spec/tasks/${taskId}/extraction/status`
  });
}

export function fetchCadSpecExtraction(taskId: string) {
  return request<Api.CadSpec.ExtractionResult>({
    url: `/api/cad/spec/tasks/${taskId}/extraction`
  });
}

export function fetchCadSpecFacts(
  taskId: string,
  params: {
    fact_type?: string;
    symbol?: string;
    needs_review?: boolean;
    keyword?: string;
    target_code?: string;
    target_dn?: number | null;
    page?: number;
    page_size?: number;
  } = {}
) {
  return request<Api.Cad.PagedResult<Api.CadSpec.Fact>>({
    url: `/api/cad/spec/tasks/${taskId}/facts`,
    params
  });
}

export function retryCadSpecExtraction(taskId: string) {
  return request<Api.CadSpec.ExtractResponse>({
    url: `/api/cad/spec/tasks/${taskId}/extract/retry`,
    method: 'post'
  });
}

export function fetchComponentBuildTree() {
  return request<Api.ComponentBuild.TreeNode[]>({
    url: '/api/component-builds/tree'
  });
}

export function fetchComponentBuild(buildId: string) {
  return request<Api.ComponentBuild.BuildDetail>({
    url: `/api/component-builds/${buildId}`
  });
}

export function fetchComponentBuildStatus(buildId: string) {
  return request<Api.ComponentBuild.BuildStatus>({
    url: `/api/component-builds/${buildId}/status`
  });
}

export function createComponentBuild(params: Api.ComponentBuild.CreatePayload) {
  const data = new FormData();
  data.append('component_id', params.component_id);
  data.append('component_name', params.component_name);
  data.append('component_type', params.component_type);
  data.append('version', params.version || '1.0.0');
  data.append('step_file', params.step_file);
  data.append('drawing_file', params.drawing_file);
  if (params.component_subtype) data.append('component_subtype', params.component_subtype);
  if (params.family) data.append('family', params.family);
  if (params.standard_number) data.append('standard_number', params.standard_number);
  if (params.default_dn !== undefined) data.append('default_dn', String(params.default_dn));
  if (params.default_pn !== undefined) data.append('default_pn', String(params.default_pn));

  return request<Api.ComponentBuild.BuildDetail>({
    url: '/api/component-builds',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}

export function retryComponentBuild(buildId: string, role: Api.ComponentBuild.RetryRole) {
  return request<Api.ComponentBuild.BuildDetail>({
    url: `/api/component-builds/${buildId}/retry`,
    method: 'post',
    data: { role }
  });
}

export function getCadSpecDrawingImageUrl(taskId: string, variant: 'original' | 'inference' = 'inference') {
  return `${getCadSpecApiBase()}/api/cad/spec/tasks/${taskId}/drawing/image?variant=${variant}`;
}

export function getCadSpecRegionImageUrl(taskId: string, regionId: string) {
  return `${getCadSpecApiBase()}/api/cad/spec/tasks/${taskId}/regions/${regionId}/image`;
}

function getCadSpecApiBase() {
  if (import.meta.env.DEV && import.meta.env.VITE_HTTP_PROXY === 'Y') return '/proxy-default';
  return import.meta.env.VITE_SERVICE_BASE_URL.replace(/\/$/, '');
}
