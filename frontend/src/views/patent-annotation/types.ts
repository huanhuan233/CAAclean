export type SourceKind = 'pdf' | 'step';

export interface Point2D {
  x: number;
  y: number;
}

export interface NormalizedBox {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

export type AnnotationOrigin = 'manual' | 'automatic';
export type ReviewState = 'accepted' | 'review' | 'rejected';

export interface PatentSource {
  id: string;
  kind: SourceKind;
  fileKey: string;
  fileName: string;
  pageCount: number;
  figureNo?: string;
}

export interface PatentAnnotation {
  id: string;
  sourceId: string;
  sourceKind: SourceKind;
  page: number;
  refNo: string;
  partName: string;
  anchor: Point2D;
  elbow: Point2D;
  label: Point2D;
  visible: boolean;
  lineWidth: number;
  fontSize: number;
  origin: AnnotationOrigin;
  reviewState?: ReviewState;
  reviewed?: boolean;
  confidence?: number;
  bbox?: NormalizedBox;
  modelName?: string;
  modelReason?: string;
  entityId?: string;
  worldPoint?: [number, number, number];
}

export interface PatentAnnotationDocument {
  schemaVersion: '0.2';
  sources: PatentSource[];
  annotations: PatentAnnotation[];
}

export type AnnotationPointKey = 'anchor' | 'elbow' | 'label';

export interface AnnotationPointUpdate {
  id: string;
  point: AnnotationPointKey;
  value: Point2D;
}
