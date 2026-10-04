import { ref } from 'vue';
import type { GeometryQueryResponse, GeometryReferencePayload } from '@/service/api/cad';

export type MeasurementOperation = 'idle' | 'distance' | 'angle' | 'section' | 'local_thickness';
export type QueryPayload = {
  operation: Exclude<MeasurementOperation, 'idle'>;
  references: GeometryReferencePayload[];
  parameters: Record<string, unknown>;
  source_policy: 'auxiliary_brep';
};

type QueryFunction = (buildId: string, payload: QueryPayload, signal: AbortSignal) => Promise<GeometryQueryResponse>;

export function createMeasurementSession(query: QueryFunction) {
  const operation = ref<MeasurementOperation>('idle');
  const references = ref<GeometryReferencePayload[]>([]);
  const seedPoints = ref<(number[] | null)[]>([]);
  const parameters = ref<Record<string, unknown>>({});
  const result = ref<GeometryQueryResponse | null>(null);
  const loading = ref(false);
  const error = ref('');
  let generation = 0;
  let controller: AbortController | null = null;

  function cancel() {
    generation += 1;
    controller?.abort();
    controller = null;
    loading.value = false;
  }

  function clear() {
    cancel();
    operation.value = 'idle';
    references.value = [];
    seedPoints.value = [];
    parameters.value = {};
    result.value = null;
    error.value = '';
  }

  function start(next: Exclude<MeasurementOperation, 'idle'>) {
    clear();
    operation.value = next;
    if (next === 'angle') parameters.value = { orientation: 'unoriented' };
  }

  function capture(reference: GeometryReferencePayload, seedPoint: number[] | null = null) {
    if (operation.value === 'idle') return;
    cancel();
    const max = operation.value === 'distance' || operation.value === 'angle' ? 2 : 1;
    references.value = [...references.value, reference].slice(-max);
    seedPoints.value = [...seedPoints.value, seedPoint ? [...seedPoint] : null].slice(-max);
    result.value = null;
    error.value = '';
  }

  async function calculate(buildId: string) {
    const mode = operation.value;
    if (mode === 'idle') return;
    const required = mode === 'distance' || mode === 'angle' ? 2 : 1;
    if (references.value.length !== required) {
      error.value = `需要选择 ${required} 个真实几何对象`;
      return;
    }
    cancel();
    const current = generation;
    controller = new AbortController();
    loading.value = true;
    error.value = '';
    try {
      const response = await query(buildId, {
        operation: mode, references: [...references.value], parameters: { ...parameters.value },
        source_policy: 'auxiliary_brep'
      }, controller.signal);
      if (current !== generation) return;
      result.value = response;
      if (!['success', 'multiple', 'empty'].includes(response.status))
        error.value = response.diagnostic || response.status;
    } catch (reason) {
      if (current === generation)
        error.value = reason instanceof Error ? reason.message : '测量请求失败';
    } finally {
      if (current === generation) loading.value = false;
    }
  }

  return { operation, references, seedPoints, parameters, result, loading, error, start, capture, calculate, cancel, clear };
}
