import { computed, ref, watch } from 'vue';
import type { ComputedRef, Ref } from 'vue';
import { clamp01, createDefaultLeaderPoints, normalizePatentAnnotationDocument, normalizePoint } from '../geometry';
import type { PatentAnnotation, PatentAnnotationDocument, PatentSource, Point2D, SourceKind } from '../types';

export const PATENT_ANNOTATION_STORAGE_KEY = 'patent-annotation-draft-v0.1';

interface AnnotationStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface UsePatentAnnotationsOptions {
  storage?: AnnotationStorage | null;
  storageKey?: string;
}

interface CreateAnnotationInput {
  sourceId: string;
  sourceKind: SourceKind;
  page: number;
  anchor: Point2D;
  entityId?: string;
  worldPoint?: [number, number, number];
}

export interface PatentAnnotationStore {
  document: Ref<PatentAnnotationDocument>;
  selectedAnnotationId: Ref<string>;
  selectedAnnotation: ComputedRef<PatentAnnotation | null>;
  getOrCreateSource(input: Omit<PatentSource, 'id'>): PatentSource;
  updateSource(sourceId: string, patch: Partial<Pick<PatentSource, 'fileName' | 'pageCount'>>): void;
  annotationsFor(sourceId: string, page: number): PatentAnnotation[];
  createAnnotation(input: CreateAnnotationInput): PatentAnnotation;
  updateAnnotation(annotationId: string, patch: Partial<PatentAnnotation>): void;
  removeAnnotation(annotationId: string): void;
  clearPage(sourceId: string, page: number): void;
  clearSource(sourceId: string): void;
  replaceDocument(input: unknown): void;
  exportDocument(): PatentAnnotationDocument;
  applySuggestedAnnotations(items: PatentAnnotation[]): void;
}

export function usePatentAnnotations(options: UsePatentAnnotationsOptions = {}): PatentAnnotationStore {
  const storage = options.storage === undefined ? browserStorage() : options.storage;
  const storageKey = options.storageKey ?? PATENT_ANNOTATION_STORAGE_KEY;
  const document = ref(loadDocument(storage, storageKey));
  const selectedAnnotationId = ref('');
  let storageWarningShown = false;

  const selectedAnnotation = computed(
    () => document.value.annotations.find(item => item.id === selectedAnnotationId.value) ?? null
  );

  function getOrCreateSource(input: Omit<PatentSource, 'id'>) {
    const existing = document.value.sources.find(item => item.kind === input.kind && item.fileKey === input.fileKey);
    if (existing) {
      existing.fileName = input.fileName;
      existing.pageCount = Math.max(existing.pageCount, normalizePageCount(input.pageCount));
      return existing;
    }

    const source: PatentSource = {
      id: createId(),
      kind: input.kind,
      fileKey: input.fileKey,
      fileName: input.fileName,
      pageCount: normalizePageCount(input.pageCount)
    };
    document.value.sources.push(source);
    return source;
  }

  function updateSource(sourceId: string, patch: Partial<Pick<PatentSource, 'fileName' | 'pageCount'>>) {
    const source = document.value.sources.find(item => item.id === sourceId);
    if (!source) return;
    if (patch.fileName !== undefined) source.fileName = String(patch.fileName);
    if (patch.pageCount !== undefined) {
      source.pageCount = normalizePageCount(patch.pageCount);
      document.value.annotations
        .filter(item => item.sourceId === sourceId)
        .forEach(item => {
          item.page = Math.min(item.page, source.pageCount);
        });
    }
  }

  function annotationsFor(sourceId: string, page: number) {
    return document.value.annotations.filter(item => item.sourceId === sourceId && item.page === page);
  }

  function createAnnotation(input: CreateAnnotationInput) {
    const source = document.value.sources.find(item => item.id === input.sourceId);
    if (!source) throw new Error('无法为不存在的来源创建标注');
    if (source.kind !== input.sourceKind) throw new Error('标注来源类型不匹配');

    const anchor = normalizePoint(input.anchor);
    const defaults = createDefaultLeaderPoints(anchor);
    const annotation: PatentAnnotation = {
      id: createId(),
      sourceId: source.id,
      sourceKind: source.kind,
      page: clampPage(input.page, source.pageCount),
      refNo: nextRefNo(source.id),
      partName: '',
      anchor,
      elbow: defaults.elbow,
      label: defaults.label,
      visible: true,
      lineWidth: 1.2,
      fontSize: 16
    };
    if (input.entityId) annotation.entityId = input.entityId;
    if (input.worldPoint?.length === 3 && input.worldPoint.every(Number.isFinite)) {
      annotation.worldPoint = [...input.worldPoint] as [number, number, number];
    }

    document.value.annotations.push(annotation);
    selectedAnnotationId.value = annotation.id;
    return annotation;
  }

  function updateAnnotation(annotationId: string, patch: Partial<PatentAnnotation>) {
    const annotation = document.value.annotations.find(item => item.id === annotationId);
    if (!annotation) return;
    const source = document.value.sources.find(item => item.id === annotation.sourceId);

    if (patch.refNo !== undefined) annotation.refNo = String(patch.refNo);
    if (patch.partName !== undefined) annotation.partName = String(patch.partName);
    if (patch.page !== undefined && source) annotation.page = clampPage(patch.page, source.pageCount);
    if (patch.anchor) annotation.anchor = normalizePoint(patch.anchor);
    if (patch.elbow) annotation.elbow = normalizePoint(patch.elbow);
    if (patch.label) annotation.label = normalizePoint(patch.label);
    if (patch.visible !== undefined) annotation.visible = Boolean(patch.visible);
    if (patch.lineWidth !== undefined) {
      annotation.lineWidth = clampRange(patch.lineWidth, { min: 0.5, max: 8, fallback: 1.2 });
    }
    if (patch.fontSize !== undefined) {
      annotation.fontSize = clampRange(patch.fontSize, { min: 8, max: 72, fallback: 16 });
    }
    if (patch.entityId !== undefined) annotation.entityId = patch.entityId || undefined;
    if (patch.worldPoint?.length === 3 && patch.worldPoint.every(Number.isFinite)) {
      annotation.worldPoint = [...patch.worldPoint] as [number, number, number];
    }
  }

  function removeAnnotation(annotationId: string) {
    document.value.annotations = document.value.annotations.filter(item => item.id !== annotationId);
    if (selectedAnnotationId.value === annotationId) selectedAnnotationId.value = '';
  }

  function clearPage(sourceId: string, page: number) {
    const removedIds = new Set(
      document.value.annotations.filter(item => item.sourceId === sourceId && item.page === page).map(item => item.id)
    );
    document.value.annotations = document.value.annotations.filter(
      item => item.sourceId !== sourceId || item.page !== page
    );
    if (removedIds.has(selectedAnnotationId.value)) selectedAnnotationId.value = '';
  }

  function clearSource(sourceId: string) {
    const removedIds = new Set(
      document.value.annotations.filter(item => item.sourceId === sourceId).map(item => item.id)
    );
    document.value.annotations = document.value.annotations.filter(item => item.sourceId !== sourceId);
    if (removedIds.has(selectedAnnotationId.value)) selectedAnnotationId.value = '';
  }

  function replaceDocument(input: unknown) {
    const normalized = normalizePatentAnnotationDocument(input);
    document.value = normalized;
    selectedAnnotationId.value = '';
  }

  function exportDocument() {
    return normalizePatentAnnotationDocument(JSON.parse(JSON.stringify(document.value)));
  }

  function applySuggestedAnnotations(items: PatentAnnotation[]) {
    const existingIds = new Set(document.value.annotations.map(item => item.id));
    const nextItems = items.filter(item => !existingIds.has(item.id));
    const normalized = normalizePatentAnnotationDocument({
      schemaVersion: '0.1',
      sources: document.value.sources,
      annotations: [...document.value.annotations, ...nextItems]
    });
    document.value = normalized;
  }

  function nextRefNo(sourceId: string) {
    const numeric = document.value.annotations
      .filter(item => item.sourceId === sourceId && /^\d+$/.test(item.refNo))
      .map(item => Number(item.refNo));
    return String((numeric.length ? Math.max(...numeric) : 0) + 1);
  }

  watch(
    document,
    value => {
      if (!storage) return;
      try {
        storage.setItem(storageKey, JSON.stringify(value));
      } catch {
        if (!storageWarningShown && typeof window !== 'undefined') {
          window.$message?.warning('本地草稿保存失败，请及时导出 JSON');
          storageWarningShown = true;
        }
      }
    },
    { deep: true }
  );

  return {
    document,
    selectedAnnotationId,
    selectedAnnotation,
    getOrCreateSource,
    updateSource,
    annotationsFor,
    createAnnotation,
    updateAnnotation,
    removeAnnotation,
    clearPage,
    clearSource,
    replaceDocument,
    exportDocument,
    applySuggestedAnnotations
  };
}

function emptyDocument(): PatentAnnotationDocument {
  return {
    schemaVersion: '0.1',
    sources: [],
    annotations: []
  };
}

function loadDocument(storage: AnnotationStorage | null, storageKey: string) {
  if (!storage) return emptyDocument();
  try {
    const raw = storage.getItem(storageKey);
    return raw ? normalizePatentAnnotationDocument(JSON.parse(raw)) : emptyDocument();
  } catch {
    return emptyDocument();
  }
}

function browserStorage(): AnnotationStorage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function createId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function normalizePageCount(value: number) {
  return Math.max(1, Math.trunc(Number.isFinite(value) ? value : 1));
}

function clampPage(value: number, pageCount: number) {
  const page = Math.trunc(Number.isFinite(value) ? value : 1);
  return Math.min(pageCount, Math.max(1, page));
}

function clampRange(value: number, range: { min: number; max: number; fallback: number }) {
  if (!Number.isFinite(value)) return range.fallback;
  return Math.min(range.max, Math.max(range.min, value));
}

export function clampPercentage(value: number) {
  return clamp01(value / 100) * 100;
}
