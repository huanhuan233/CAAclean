export type SourceKind = 'pdf' | 'step';

export interface Point2D {
  x: number;
  y: number;
}

export interface PatentSource {
  id: string;
  kind: SourceKind;
  fileKey: string;
  fileName: string;
  pageCount: number;
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
  entityId?: string;
  worldPoint?: [number, number, number];
}

export interface PatentAnnotationDocument {
  schemaVersion: '0.1';
  sources: PatentSource[];
  annotations: PatentAnnotation[];
}

export type AnnotationPointKey = 'anchor' | 'elbow' | 'label';

export interface AnnotationPointUpdate {
  id: string;
  point: AnnotationPointKey;
  value: Point2D;
}
