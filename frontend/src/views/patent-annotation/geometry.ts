import { clamp01, clientPointToNormalized } from '../../utils/normalized-coordinates';
import type {
  AnnotationOrigin,
  NormalizedBox,
  PatentAnnotation,
  PatentAnnotationDocument,
  PatentSource,
  Point2D,
  ReviewState,
  SourceKind
} from './types';

type UnknownRecord = Record<string, unknown>;
type NumberRange = { min: number; max: number; fallback: number };

const SOURCE_KINDS = new Set<SourceKind>(['pdf', 'step']);
const SCHEMA_VERSIONS = new Set(['0.1', '0.2']);
const ANNOTATION_ORIGINS = new Set<AnnotationOrigin>(['manual', 'automatic']);
const REVIEW_STATES = new Set<ReviewState>(['accepted', 'review', 'rejected']);

export { clamp01, clientPointToNormalized };

export function normalizePoint(point: Point2D): Point2D {
  return {
    x: clamp01(Number(point.x)),
    y: clamp01(Number(point.y))
  };
}

export function normalizedPointToPixels(point: Point2D, width: number, height: number): Point2D {
  return {
    x: clamp01(point.x) * Math.max(0, width),
    y: clamp01(point.y) * Math.max(0, height)
  };
}

export function createDefaultLeaderPoints(anchorInput: Point2D) {
  const anchor = normalizePoint(anchorInput);
  const direction = anchor.x > 0.78 ? -1 : 1;
  const label = normalizePoint({
    x: anchor.x + direction * 0.18,
    y: anchor.y - 0.12
  });

  return {
    elbow: normalizePoint({
      x: anchor.x + direction * 0.09,
      y: label.y
    }),
    label
  };
}

export function normalizePatentAnnotationDocument(input: unknown): PatentAnnotationDocument {
  const root = requireRecord(input, '标注文档必须是对象');
  if (typeof root.schemaVersion !== 'string' || !SCHEMA_VERSIONS.has(root.schemaVersion)) {
    throw new Error('不支持的标注文档版本');
  }
  if (!Array.isArray(root.sources) || !Array.isArray(root.annotations)) {
    throw new TypeError('标注文档缺少 sources 或 annotations 数组');
  }

  const sourceIds = new Set<string>();
  const sources = root.sources.map((item, index) => normalizeSource(item, index, sourceIds));
  const sourceById = new Map(sources.map(source => [source.id, source]));
  const annotationIds = new Set<string>();
  const annotations = root.annotations.map((item, index) =>
    normalizeAnnotation(item, index, { sources: sourceById, ids: annotationIds })
  );

  return {
    schemaVersion: '0.2',
    sources,
    annotations
  };
}

function normalizeSource(input: unknown, index: number, ids: Set<string>): PatentSource {
  const source = requireRecord(input, `第 ${index + 1} 个来源不是对象`);
  const id = requireString(source.id, `第 ${index + 1} 个来源缺少 id`);
  if (ids.has(id)) throw new Error(`来源 id 重复：${id}`);
  ids.add(id);

  const kind = requireSourceKind(source.kind, `来源 ${id} 的 kind 非法`);
  const fileKey = requireString(source.fileKey, `来源 ${id} 缺少 fileKey`);
  const fileName = requireString(source.fileName, `来源 ${id} 缺少 fileName`);
  const pageCount = clampInteger(source.pageCount, { min: 1, max: 100000, fallback: 1 });
  const figureNo = typeof source.figureNo === 'string' && source.figureNo.trim() ? source.figureNo.trim() : undefined;

  return { id, kind, fileKey, fileName, pageCount, ...(figureNo ? { figureNo } : {}) };
}

function normalizeAnnotation(
  input: unknown,
  index: number,
  context: { sources: Map<string, PatentSource>; ids: Set<string> }
): PatentAnnotation {
  const annotation = requireRecord(input, `第 ${index + 1} 个标注不是对象`);
  const id = requireString(annotation.id, `第 ${index + 1} 个标注缺少 id`);
  if (context.ids.has(id)) throw new Error(`标注 id 重复：${id}`);
  context.ids.add(id);

  const sourceId = requireString(annotation.sourceId, `标注 ${id} 缺少 sourceId`);
  const source = context.sources.get(sourceId);
  if (!source) throw new Error(`标注 ${id} 的来源不存在`);

  const sourceKind = requireSourceKind(annotation.sourceKind, `标注 ${id} 的 sourceKind 非法`);
  if (sourceKind !== source.kind) throw new Error(`标注 ${id} 的来源类型不匹配`);

  const normalized: PatentAnnotation = {
    id,
    sourceId,
    sourceKind,
    page: clampInteger(annotation.page, { min: 1, max: source.pageCount, fallback: 1 }),
    refNo: String(annotation.refNo ?? ''),
    partName: String(annotation.partName ?? ''),
    anchor: normalizeUnknownPoint(annotation.anchor, `标注 ${id} 缺少 anchor`),
    elbow: normalizeUnknownPoint(annotation.elbow, `标注 ${id} 缺少 elbow`),
    label: normalizeUnknownPoint(annotation.label, `标注 ${id} 缺少 label`),
    visible: typeof annotation.visible === 'boolean' ? annotation.visible : true,
    lineWidth: clampNumber(annotation.lineWidth, { min: 0.5, max: 8, fallback: 1.2 }),
    fontSize: clampNumber(annotation.fontSize, { min: 8, max: 72, fallback: 16 }),
    origin: normalizeOrigin(annotation.origin),
    reviewed: typeof annotation.reviewed === 'boolean' ? annotation.reviewed : undefined
  };
  const reviewState = normalizeReviewState(annotation.reviewState);
  if (reviewState) normalized.reviewState = reviewState;
  const confidence = normalizeOptionalConfidence(annotation.confidence);
  if (confidence !== undefined) normalized.confidence = confidence;
  const bbox = normalizeOptionalBox(annotation.bbox);
  if (bbox) normalized.bbox = bbox;
  if (typeof annotation.modelName === 'string' && annotation.modelName.trim()) normalized.modelName = annotation.modelName.trim();
  if (typeof annotation.modelReason === 'string' && annotation.modelReason.trim()) {
    normalized.modelReason = annotation.modelReason.trim();
  }

  if (typeof annotation.entityId === 'string' && annotation.entityId.trim()) {
    normalized.entityId = annotation.entityId;
  }
  const worldPoint = normalizeWorldPoint(annotation.worldPoint);
  if (worldPoint) normalized.worldPoint = worldPoint;

  return normalized;
}

function normalizeOrigin(input: unknown): AnnotationOrigin {
  if (typeof input === 'string' && ANNOTATION_ORIGINS.has(input as AnnotationOrigin)) return input as AnnotationOrigin;
  return 'manual';
}

function normalizeReviewState(input: unknown): ReviewState | undefined {
  if (typeof input === 'string' && REVIEW_STATES.has(input as ReviewState)) return input as ReviewState;
  return undefined;
}

function normalizeOptionalConfidence(input: unknown): number | undefined {
  if (input === undefined || input === null) return undefined;
  return clampNumber(input, { min: 0, max: 1, fallback: 0 });
}

function normalizeOptionalBox(input: unknown): NormalizedBox | undefined {
  if (input === undefined || input === null) return undefined;
  const box = requireRecord(input, 'bbox 必须是对象');
  const x1 = clampNumber(box.xMin, { min: 0, max: 1, fallback: 0 });
  const x2 = clampNumber(box.xMax, { min: 0, max: 1, fallback: 0 });
  const y1 = clampNumber(box.yMin, { min: 0, max: 1, fallback: 0 });
  const y2 = clampNumber(box.yMax, { min: 0, max: 1, fallback: 0 });
  return {
    xMin: Math.min(x1, x2),
    yMin: Math.min(y1, y2),
    xMax: Math.max(x1, x2),
    yMax: Math.max(y1, y2)
  };
}

function normalizeUnknownPoint(input: unknown, message: string): Point2D {
  const point = requireRecord(input, message);
  return normalizePoint({
    x: Number(point.x),
    y: Number(point.y)
  });
}

function normalizeWorldPoint(input: unknown): [number, number, number] | null {
  if (!Array.isArray(input) || input.length !== 3) return null;
  const values = input.map(Number);
  if (!values.every(Number.isFinite)) return null;
  return [values[0], values[1], values[2]];
}

function requireRecord(input: unknown, message: string): UnknownRecord {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new TypeError(message);
  return input as UnknownRecord;
}

function requireString(input: unknown, message: string) {
  if (typeof input !== 'string' || !input.trim()) throw new Error(message);
  return input.trim();
}

function requireSourceKind(input: unknown, message: string): SourceKind {
  if (typeof input !== 'string' || !SOURCE_KINDS.has(input as SourceKind)) throw new Error(message);
  return input as SourceKind;
}

function clampNumber(input: unknown, range: NumberRange) {
  const value = Number(input);
  if (!Number.isFinite(value)) return range.fallback;
  return Math.min(range.max, Math.max(range.min, value));
}

function clampInteger(input: unknown, range: NumberRange) {
  return Math.trunc(clampNumber(input, range));
}
