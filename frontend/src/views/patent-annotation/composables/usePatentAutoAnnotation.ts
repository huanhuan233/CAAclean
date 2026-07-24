import { ref } from 'vue';
import { autoLayoutAnnotations, inferFigureNo, snapPointToInk } from '../auto-annotation';
import { createDefaultLeaderPoints } from '../geometry';
import type { PatentAnnotation, PatentSource, Point2D, SourceKind } from '../types';
import type { PatentAnnotationStore } from './usePatentAnnotations';

export interface PdfWorkspaceCapture {
  getCurrentPageImageBlob(options?: { scale?: number }): Promise<Blob>;
  getCurrentPageImageData(): ImageData | null;
}

export interface SuggestionBuildInput {
  sourceId: string;
  sourceKind: SourceKind;
  page: number;
  components: Api.PatentAnnotation.Component[];
  localization: Api.PatentAnnotation.NormalizedLocalizationResult;
  imageData?: ImageData | null;
  modelName?: string;
}

export function buildAutoAnnotationSuggestions(input: SuggestionBuildInput): PatentAnnotation[] {
  const componentByRef = new Map(input.components.map(component => [component.ref_no, component.name]));
  const layoutItems = autoLayoutAnnotations(
    input.localization.items
      .filter(item => item.visible && item.review_state !== 'rejected' && item.anchor)
      .map(item => ({
        refNo: item.ref_no,
        anchor: input.imageData ? snapPointToInk(toPoint(item.anchor!), input.imageData) : toPoint(item.anchor!)
      }))
  );
  const layoutByRef = new Map(layoutItems.map(item => [item.refNo, item]));

  return input.localization.items
    .filter(item => item.visible && item.review_state !== 'rejected' && item.anchor)
    .map(item => {
      const layout = layoutByRef.get(item.ref_no);
      const anchor = layout?.anchor ?? toPoint(item.anchor!);
      const defaults = createDefaultLeaderPoints(anchor);
      return {
        id: `auto-${input.sourceId}-${input.page}-${item.ref_no}`,
        sourceId: input.sourceId,
        sourceKind: input.sourceKind,
        page: input.page,
        refNo: item.ref_no,
        partName: componentByRef.get(item.ref_no) ?? '',
        anchor,
        elbow: layout?.elbow ?? defaults.elbow,
        label: layout?.label ?? defaults.label,
        visible: true,
        lineWidth: 1.2,
        fontSize: 16,
        origin: 'automatic',
        reviewState: item.review_state,
        reviewed: item.review_state === 'accepted',
        confidence: item.confidence,
        bbox: item.bbox
          ? {
              xMin: item.bbox.x_min,
              yMin: item.bbox.y_min,
              xMax: item.bbox.x_max,
              yMax: item.bbox.y_max
            }
          : undefined,
        modelName: input.modelName,
        modelReason: item.reason
      };
    });
}

export function usePatentAutoAnnotation(store: PatentAnnotationStore) {
  const parseResult = ref<Api.PatentAnnotation.DocumentParseResult | null>(null);
  const selectedRefs = ref(new Set<string>());
  const parsing = ref(false);
  const localizing = ref(false);
  const progressText = ref('');

  async function parseDocument(file: File, options: { fast?: boolean; sources?: PatentSource[] } = {}) {
    parsing.value = true;
    progressText.value = 'Parsing PDF';
    try {
      const { parsePatentDocument } = await import('@/service/api/patent-annotation');
      const result = await unwrapApi<Api.PatentAnnotation.DocumentParseResult>(
        parsePatentDocument(file, { fast: options.fast }) as Promise<ApiResponse<Api.PatentAnnotation.DocumentParseResult>>
      );
      parseResult.value = result;
      selectedRefs.value = new Set(result.components.map(component => component.ref_no));
      assignFigureNumbers(options.sources ?? store.document.value.sources.filter(source => source.kind === 'pdf'), result.figures);
      return result;
    } catch (error) {
      throw new Error(requestMessage(error), { cause: error });
    } finally {
      parsing.value = false;
      progressText.value = '';
    }
  }

  function updateComponentName(refNo: string, name: string) {
    if (!parseResult.value) return;
    parseResult.value = {
      ...parseResult.value,
      components: parseResult.value.components.map(component =>
        component.ref_no === refNo ? { ...component, name } : component
      )
    };
  }

  async function localizeCurrentPage(params: {
    workspace: PdfWorkspaceCapture;
    sourceId: string;
    page: number;
    confirmReplace?: () => Promise<boolean> | boolean;
  }) {
    if (!parseResult.value) throw new Error('Parse a PDF first');
    const source = store.document.value.sources.find(item => item.id === params.sourceId);
    if (!source) throw new Error('Current PDF source was not found');
    const oldAuto = store
      .annotationsFor(params.sourceId, params.page)
      .some(annotation => annotation.origin === 'automatic');
    if (oldAuto && params.confirmReplace && !(await params.confirmReplace())) {
      return { added: 0, reviewCount: 0, warnings: [] as string[] };
    }

    localizing.value = true;
    progressText.value = 'Localizing current page';
    try {
      const figure = figureForSource(source, parseResult.value.figures);
      const candidates = candidatesForFigure(figure, parseResult.value, selectedRefs.value);
      const imageFile = await params.workspace.getCurrentPageImageBlob({ scale: 1 });
      const imageData = params.workspace.getCurrentPageImageData();
      const { localizePatentPage } = await import('@/service/api/patent-annotation');
      const localization = await unwrapApi<Api.PatentAnnotation.NormalizedLocalizationResult>(
        localizePatentPage({
          imageFile,
          fileName: `${source.fileName || 'page'}-${params.page}.png`,
          figureNo: figure?.figure_no || source.figureNo || String(params.page),
          figureDescription: figure?.description,
          figureContext: figure?.context,
          components: candidates
        }) as Promise<ApiResponse<Api.PatentAnnotation.NormalizedLocalizationResult>>
      );
      const suggestions = buildAutoAnnotationSuggestions({
        sourceId: params.sourceId,
        sourceKind: 'pdf',
        page: params.page,
        components: candidates,
        localization,
        imageData,
        modelName: localization.warnings.find(item => item.startsWith('model:'))?.slice(6)
      });
      const result = store.applySuggestedAnnotations(suggestions, {
        sourceId: params.sourceId,
        page: params.page,
        replaceAuto: true
      });
      return {
        added: result.added,
        reviewCount: suggestions.filter(item => item.reviewState === 'review').length,
        warnings: localization.warnings
      };
    } catch (error) {
      throw new Error(requestMessage(error), { cause: error });
    } finally {
      localizing.value = false;
      progressText.value = '';
    }
  }

  function assignFigureNumbers(sources: PatentSource[], figures: Api.PatentAnnotation.Figure[]) {
    sources
      .filter(source => source.kind === 'pdf' && !source.figureNo)
      .forEach((source, index) => {
        store.updateSource(source.id, { figureNo: inferFigureNo(source.fileName, figures, index) });
      });
  }

  return {
    parseResult,
    selectedRefs,
    parsing,
    localizing,
    progressText,
    parseDocument,
    updateComponentName,
    localizeCurrentPage
  };
}

function candidatesForFigure(
  figure: Api.PatentAnnotation.Figure | undefined,
  result: Api.PatentAnnotation.DocumentParseResult,
  selectedRefs: Set<string>
) {
  const refs = new Set<string>();
  for (const refNo of figure?.candidate_ref_nos ?? result.components.map(component => component.ref_no)) {
    if (selectedRefs.has(refNo)) refs.add(refNo);
  }
  const byRef = new Map(result.components.map(component => [component.ref_no, component]));
  const candidates: Api.PatentAnnotation.Component[] = [];
  for (const refNo of refs) {
    const component = byRef.get(refNo);
    if (component) candidates.push(component);
  }
  for (const marker of figure?.detail_markers ?? []) {
    candidates.push({
      ref_no: marker.marker,
      name: `Detail ${marker.marker} of figure ${marker.parent_figure_no}`
    });
  }
  return candidates;
}

function figureForSource(source: PatentSource, figures: Api.PatentAnnotation.Figure[]) {
  return figures.find(figure => figure.figure_no === source.figureNo) ?? figures[0];
}

function toPoint(point: Api.PatentAnnotation.NormalizedPoint): Point2D {
  return { x: point.x, y: point.y };
}

type ApiResponse<T> = T | { data?: T; error?: unknown };

async function unwrapApi<T>(promise: Promise<ApiResponse<T>>) {
  const response = await promise;
  if (response && typeof response === 'object' && 'error' in response) {
    const wrapped = response as { data?: T; error?: unknown };
    if (wrapped.error) throw wrapped.error;
    if (wrapped.data === undefined || wrapped.data === null) throw new Error('Auto annotation request failed');
    return wrapped.data;
  }
  return response as T;
}

function requestMessage(error: unknown) {
  const candidate = error as { response?: { data?: { detail?: { message?: string } } }; message?: string };
  return candidate.response?.data?.detail?.message ?? candidate.message ?? 'Auto annotation request failed';
}
