declare namespace Api {
  namespace PatentAnnotation {
    type Parser = 'mineru' | 'pypdf';
    type ReviewState = 'accepted' | 'review' | 'rejected';

    interface Component {
      ref_no: string;
      name: string;
    }

    interface DetailMarker {
      marker: string;
      parent_figure_no: string;
    }

    interface Figure {
      figure_no: string;
      description: string;
      context: string;
      explicit_ref_nos: string[];
      candidate_ref_nos: string[];
      detail_markers: DetailMarker[];
    }

    interface DocumentParseResult {
      file_name: string;
      parser: Parser;
      components: Component[];
      figures: Figure[];
      document_context?: string;
      warnings: string[];
    }

    interface LocalizationCandidate {
      ref_no: string;
      name: string;
    }

    interface NormalizedPoint {
      x: number;
      y: number;
    }

    interface NormalizedBox {
      x_min: number;
      y_min: number;
      x_max: number;
      y_max: number;
    }

    interface NormalizedLocalizationItem {
      ref_no: string;
      name?: string | null;
      visible: boolean;
      confidence: number;
      reason: string;
      anchor: NormalizedPoint | null;
      bbox: NormalizedBox | null;
      review_state: ReviewState;
    }

    interface NormalizedLocalizationResult {
      items: NormalizedLocalizationItem[];
      warnings: string[];
    }
  }
}
