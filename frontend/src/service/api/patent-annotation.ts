import { request } from '../request';

export function parsePatentDocument(file: File, options: { fast?: boolean } = {}) {
  const data = new FormData();
  data.append('pdf_file', file);
  if (options.fast !== undefined) data.append('fast', String(options.fast));

  return request<Api.PatentAnnotation.DocumentParseResult>({
    url: '/api/patent-annotations/parse-document',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}

export function localizePatentPage(params: {
  imageFile: Blob;
  fileName?: string;
  figureNo: string;
  figureDescription?: string;
  figureContext?: string;
  components: Api.PatentAnnotation.LocalizationCandidate[];
}) {
  const data = new FormData();
  data.append('image_file', params.imageFile, params.fileName || 'page.png');
  data.append('figure_no', params.figureNo);
  if (params.figureDescription) data.append('figure_description', params.figureDescription);
  if (params.figureContext) data.append('figure_context', params.figureContext);
  data.append('components_json', JSON.stringify(params.components));

  return request<Api.PatentAnnotation.NormalizedLocalizationResult>({
    url: '/api/patent-annotations/localize-page',
    method: 'post',
    data,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}
