import { ref } from 'vue';
import { autoLayoutAnnotations, inferFigureNoForSource, snapPointToInk } from '../auto-annotation';
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
        partName: item.name ?? componentByRef.get(item.ref_no) ?? '',
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
    if (localizing.value) throw new Error('当前附图正在自动标注，请稍后再解析说明书');
    parsing.value = true;
    progressText.value = '正在解析说明书 PDF';
    try {
      const { parsePatentDocument } = await import('@/service/api/patent-annotation');
      const result = await unwrapApi<Api.PatentAnnotation.DocumentParseResult>(
        parsePatentDocument(file, { fast: options.fast }) as Promise<
          ApiResponse<Api.PatentAnnotation.DocumentParseResult>
        >
      );
      parseResult.value = result;
      selectedRefs.value = new Set(result.components.map(component => component.ref_no));
      ensureSourceFigureNos(options.sources ?? store.document.value.sources.filter(source => source.kind === 'pdf'), {
        reset: true
      });
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

  function ensureSourceFigureNos(sources: PatentSource[], options: { reset?: boolean } = {}) {
    const result = parseResult.value;
    if (!result) return;
    const pdfSources = sources.filter(item => item.kind === 'pdf');
    const validFigureNos = new Set(result.figures.map(figure => figure.figure_no));
    const usedFigureNos = new Set<string>();
    const pendingSources: PatentSource[] = [];

    for (const source of pdfSources) {
      const keepExisting =
        !options.reset &&
        Boolean(source.figureNo && validFigureNos.has(source.figureNo) && !usedFigureNos.has(source.figureNo));
      if (keepExisting && source.figureNo) {
        usedFigureNos.add(source.figureNo);
      } else {
        if (source.figureNo) store.updateSource(source.id, { figureNo: undefined });
        pendingSources.push(source);
      }
    }

    for (const source of pendingSources) {
      const preferred = inferFigureNoForSource({ ...source, figureNo: undefined }, pdfSources, result.figures);
      const figureNo =
        preferred && !usedFigureNos.has(preferred)
          ? preferred
          : result.figures.find(figure => !usedFigureNos.has(figure.figure_no))?.figure_no;
      if (figureNo) {
        store.updateSource(source.id, { figureNo });
        usedFigureNos.add(figureNo);
      }
    }
  }

  async function localizeCurrentPage(params: {
    workspace: PdfWorkspaceCapture;
    sourceId: string;
    page: number;
    confirmReplace?: () => Promise<boolean> | boolean;
  }) {
    if (parsing.value) throw new Error('说明书正在解析，请稍后再自动标注');
    if (localizing.value) throw new Error('当前页正在自动标注');
    if (!parseResult.value) throw new Error('请先上传并解析专利说明书 PDF');
    const mappedSource = store.document.value.sources.find(item => item.id === params.sourceId);
    if (!mappedSource) throw new Error('当前附图 PDF 不存在');
    if (!mappedSource?.figureNo) throw new Error('请先为当前附图选择对应图号');

    localizing.value = true;
    progressText.value = '正在渲染当前附图';
    try {
      const figure = figureForSource(mappedSource, parseResult.value.figures);
      if (!figure) throw new Error('当前图号不在说明书解析结果中，请重新选择图号');
      const oldAuto = store
        .annotationsFor(params.sourceId, params.page)
        .some(annotation => annotation.origin === 'automatic');
      if (oldAuto && params.confirmReplace && !(await params.confirmReplace())) {
        return { added: 0, reviewCount: 0, warnings: [] as string[] };
      }
      const candidates = candidatesForFigure(figure, parseResult.value, selectedRefs.value);
      if (!candidates.length) throw new Error('请至少选择一个候选部件');
      const imageFile = await params.workspace.getCurrentPageImageBlob({ scale: 1 });
      const imageData = params.workspace.getCurrentPageImageData();
      progressText.value = '正在识别可见部件';
      const { localizePatentPage } = await import('@/service/api/patent-annotation');
      const localization = await unwrapApi<Api.PatentAnnotation.NormalizedLocalizationResult>(
        localizePatentPage({
          imageFile,
          fileName: `${mappedSource.fileName || 'page'}-${params.page}.png`,
          figureNo: figure.figure_no,
          figureDescription: figure.description,
          figureContext: figure.context,
          documentContext: parseResult.value.document_context ?? '',
          components: candidates
        }) as Promise<ApiResponse<Api.PatentAnnotation.NormalizedLocalizationResult>>
      );
      progressText.value = '正在生成引线布局';
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

  return {
    parseResult,
    selectedRefs,
    parsing,
    localizing,
    progressText,
    parseDocument,
    updateComponentName,
    ensureSourceFigureNos,
    localizeCurrentPage
  };
}

export function candidatesForFigure(
  _figure: Api.PatentAnnotation.Figure | undefined,
  result: Api.PatentAnnotation.DocumentParseResult,
  selectedRefs: Set<string>
) {
  return result.components.filter(component => selectedRefs.has(component.ref_no));
}

function figureForSource(source: PatentSource, figures: Api.PatentAnnotation.Figure[]) {
  return figures.find(figure => figure.figure_no === source.figureNo);
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
    if (wrapped.data === undefined || wrapped.data === null) throw new Error('自动标注请求失败');
    return wrapped.data;
  }
  return response as T;
}

function requestMessage(error: unknown) {
  const candidate = error as { response?: { data?: { detail?: { message?: string } } }; message?: string };
  return candidate.response?.data?.detail?.message ?? candidate.message ?? '自动标注请求失败';
}
