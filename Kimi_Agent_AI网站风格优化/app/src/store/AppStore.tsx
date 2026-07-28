import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { Primitive, DatasetRecord, FeedbackRecord, ModelInfo, Pipeline, TokenLog } from '@/types';
import { primitives as seedPrimitives } from '@/data/primitives';
import { seedDatasets, seedFeedback, seedModels, seedPipelines, seedTokenLogs } from '@/data/seed';

interface Store {
  primitives: Primitive[];
  addPrimitive: (p: Primitive) => void;
  updatePrimitive: (p: Primitive) => void;
  deletePrimitive: (id: string) => void;
  datasets: DatasetRecord[];
  addDataset: (d: DatasetRecord) => void;
  deleteDataset: (id: string) => void;
  models: ModelInfo[];
  toggleModel: (id: string) => void;
  pipelines: Pipeline[];
  setNodeModel: (pipelineId: string, nodeId: string, modelId: string) => void;
  tokenLogs: TokenLog[];
  feedback: FeedbackRecord[];
  addFeedback: (f: FeedbackRecord) => void;
  setFeedbackStatus: (id: string, status: FeedbackRecord['status']) => void;
  addTokens: (node: keyof Omit<TokenLog, 'date'>, amount: number) => void;
}

const Ctx = createContext<Store | null>(null);
const LS_KEY = 'patent-ai-store-v1';

interface Persisted {
  primitives: Primitive[];
  datasets: DatasetRecord[];
  models: ModelInfo[];
  pipelines: Pipeline[];
  tokenLogs: TokenLog[];
  feedback: FeedbackRecord[];
}

function load(): Persisted {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return {
    primitives: seedPrimitives,
    datasets: seedDatasets,
    models: seedModels,
    pipelines: seedPipelines,
    tokenLogs: seedTokenLogs,
    feedback: seedFeedback,
  };
}

export function AppStoreProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<Persisted>(load);

  useEffect(() => {
    localStorage.setItem(LS_KEY, JSON.stringify(state));
  }, [state]);

  const store = useMemo<Store>(() => ({
    ...state,
    addPrimitive: (p) => setState((s) => ({ ...s, primitives: [p, ...s.primitives] })),
    updatePrimitive: (p) => setState((s) => ({ ...s, primitives: s.primitives.map((x) => (x.id === p.id ? p : x)) })),
    deletePrimitive: (id) => setState((s) => ({ ...s, primitives: s.primitives.filter((x) => x.id !== id) })),
    addDataset: (d) => setState((s) => ({ ...s, datasets: [d, ...s.datasets] })),
    deleteDataset: (id) => setState((s) => ({ ...s, datasets: s.datasets.filter((x) => x.id !== id) })),
    toggleModel: (id) => setState((s) => ({ ...s, models: s.models.map((m) => (m.id === id ? { ...m, status: m.status === '已接入' ? '未接入' : '已接入' } : m)) })),
    setNodeModel: (pipelineId, nodeId, modelId) =>
      setState((s) => ({
        ...s,
        pipelines: s.pipelines.map((pl) =>
          pl.id === pipelineId ? { ...pl, nodes: pl.nodes.map((n) => (n.id === nodeId ? { ...n, modelId } : n)) } : pl,
        ),
      })),
    addFeedback: (f) => setState((s) => ({ ...s, feedback: [f, ...s.feedback] })),
    setFeedbackStatus: (id, status) => setState((s) => ({ ...s, feedback: s.feedback.map((f) => (f.id === id ? { ...f, status } : f)) })),
    addTokens: (node, amount) =>
      setState((s) => {
        const logs = [...s.tokenLogs];
        const last = { ...logs[logs.length - 1] };
        last[node] = last[node] + amount;
        logs[logs.length - 1] = last;
        return { ...s, tokenLogs: logs };
      }),
  }), [state]);

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export function useStore() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useStore must be used within AppStoreProvider');
  return ctx;
}
