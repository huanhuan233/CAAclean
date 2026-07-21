declare namespace Api {
  namespace Cad {
    type ParseStatusValue = 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed' | 'deleted';

    interface UploadResponse {
      model_id: string;
      revision_id: string;
      status: ParseStatusValue;
    }

    interface ParseStatus {
      status: ParseStatusValue;
      progress: number;
      status_message: string | null;
      error_code: string | null;
      error_message: string | null;
    }

    interface ModelSummary {
      id: string;
      name: string;
      current_revision_id: string | null;
      status: ParseStatusValue | null;
      progress: number | null;
      face_count?: number;
      edge_count?: number;
      vertex_count?: number;
      created_at?: string;
    }

    interface PagedResult<T> {
      items: T[];
      total: number;
      page: number;
      page_size: number;
    }

    interface TreeNode {
      id: string;
      parent_entity_id: string | null;
      entity_type: string;
      label: string;
      source_ref: string | null;
      geometry_type: string | null;
      children: TreeNode[];
    }

    interface Entity {
      id: string;
      revision_id: string;
      parent_entity_id: string | null;
      entity_type: string;
      source_ref: string | null;
      source_index: number | null;
      name: string | null;
      label: string | null;
      tree_path: string;
      sort_order: number;
      geometry_type: string | null;
      area: number | null;
      volume: number | null;
      length: number | null;
      center: unknown;
      bounding_box: Record<string, unknown> | null;
      placement: Record<string, unknown> | null;
      geometry: Record<string, unknown>;
      metadata: Record<string, unknown>;
    }

    interface Mesh {
      id: string;
      revision_id: string;
      entity_id: string;
      mesh_type: 'face';
      positions: number[][];
      indices: number[][];
      normals: number[][] | null;
      color: unknown;
      linear_deflection: number;
      angular_deflection: number | null;
      vertex_count: number;
      triangle_count: number;
    }

    interface FaceTopology {
      edges: Entity[];
      adjacent_faces: Entity[];
      vertices: Entity[];
      faces: Entity[];
    }

    interface EdgeTopology {
      edges: Entity[];
      adjacent_faces: Entity[];
      vertices: Entity[];
      faces: Entity[];
    }
  }
}
