import { request } from '../request';

const PATENT_DOCUMENT_TIMEOUT_MS = 4 * 60 * 1000;
const PATENT_LOCALIZATION_TIMEOUT_MS = 11 * 60 * 1000;

export function parsePatentDocument(file: File, options: { fast?: boolean } = {}) {
  const data = new FormData();
  data.append('pdf_file', file);
  if (options.fast !== undefined) data.append('fast', String(options.fast));

  return request<Api.PatentAnnotation.DocumentParseResult>({
    url: '/api/patent-annotations/parse-document',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
      'X-Client-Silent-Error': '1'
    },
    timeout: PATENT_DOCUMENT_TIMEOUT_MS
  });
}

export function localizePatentPage(params: {
  imageFile: Blob;
  fileName?: string;
  figureNo: string;
  figureDescription?: string;
  figureContext?: string;
  documentContext?: string;
  components: Api.PatentAnnotation.LocalizationCandidate[];
}) {
  const data = new FormData();
  data.append('image_file', params.imageFile, params.fileName || 'page.png');
  data.append('figure_no', params.figureNo);
  if (params.figureDescription) data.append('figure_description', params.figureDescription);
  if (params.figureContext) data.append('figure_context', params.figureContext);
  if (params.documentContext) data.append('document_context', params.documentContext);
  data.append('components_json', JSON.stringify(params.components));

  return request<Api.PatentAnnotation.NormalizedLocalizationResult>({
    url: '/api/patent-annotations/localize-page',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data',
      'X-Client-Silent-Error': '1'
    },
    timeout: PATENT_LOCALIZATION_TIMEOUT_MS
  });
}
