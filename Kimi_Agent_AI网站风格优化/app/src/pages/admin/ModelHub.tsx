import { useState } from 'react';
import { Cpu, Zap, FlaskConical, Loader2, CheckCircle2 } from 'lucide-react';
import { useStore } from '@/store/AppStore';

const TYPE_COLOR: Record<string, string> = {
  LLM: 'bg-violet-100 text-violet-600',
  多模态: 'bg-violet-500/15 text-violet-600',
  向量化: 'bg-emerald-500/15 text-emerald-600',
  图像生成: 'bg-amber-500/15 text-amber-600',
};

export default function ModelHub() {
  const { models, toggleModel, pipelines, setNodeModel } = useStore();
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { score: number; latency: string }>>({});

  const modelNodes = (mid: string) =>
    pipelines.flatMap((pl) => pl.nodes.filter((n) => n.modelId === mid).map((n) => `${pl.name.replace('流程', '')}·${n.label}`));

  const runTest = (mid: string) => {
    if (testing) return;
    setTesting(mid);
    setTimeout(() => {
      setTestResult((r) => ({ ...r, [mid]: { score: Math.round((3.4 + Math.random() * 1.6) * 10) / 10, latency: (0.8 + Math.random() * 3).toFixed(1) + 's' } }));
      setTesting(null);
    }, 1800);
  };

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-lg font-semibold text-slate-800">模型 API 选用接入</h1>
        <p className="mt-0.5 text-xs text-slate-500">统一管理模型接入状态，支持在不同节点切换模型并测试生成效果</p>
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        {/* 模型卡片 */}
        <div className="space-y-3 xl:col-span-2">
          {models.map((m) => {
            const usedBy = modelNodes(m.id);
            const result = testResult[m.id];
            const connected = m.status === '已接入';
            return (
              <div key={m.id} className={`rounded-xl border p-4 transition ${connected ? 'border-slate-200 bg-white' : 'border-slate-200 bg-slate-50 opacity-60'}`}>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                    <Cpu className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-800">{m.name}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] ${TYPE_COLOR[m.type]}`}>{m.type}</span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-slate-500">{m.provider}</div>
                  </div>
                  <div className="ml-auto flex items-center gap-4">
                    <div className="hidden text-right sm:block">
                      <div className="flex items-center gap-1 text-xs text-slate-600"><Zap className="h-3 w-3 text-amber-600" />{m.latency}</div>
                      <div className="mt-0.5 font-mono text-[10px] text-slate-500">{m.costPer1k}/1K tok</div>
                    </div>
                    <button
                      onClick={() => toggleModel(m.id)}
                      className={`relative h-6 w-11 rounded-full transition ${connected ? 'bg-violet-600' : 'bg-slate-200'}`}
                      title={connected ? '断开接入' : '接入'}
                    >
                      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${connected ? 'left-[22px]' : 'left-0.5'}`} />
                    </button>
                  </div>
                </div>

                {connected && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-3">
                    <span className="text-[10px] text-slate-500">服务节点：</span>
                    {usedBy.length > 0 ? usedBy.map((x) => (
                      <span key={x} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">{x}</span>
                    )) : <span className="text-[10px] text-slate-400">未被引用（可在节点流程管理中挂载）</span>}
                    <div className="ml-auto flex items-center gap-2">
                      {result && (
                        <span className="flex items-center gap-1.5 text-[11px] text-emerald-600">
                          <CheckCircle2 className="h-3.5 w-3.5" /> 效果分 {result.score}/5 · 延迟 {result.latency}
                        </span>
                      )}
                      <button onClick={() => runTest(m.id)} disabled={testing !== null}
                        className="flex items-center gap-1 rounded-md border border-violet-500/40 bg-violet-500/10 px-2.5 py-1 text-[10px] font-medium text-violet-700 hover:bg-violet-500/20 disabled:opacity-40">
                        {testing === m.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <FlaskConical className="h-3 w-3" />}
                        {testing === m.id ? '测试中…' : '效果测试'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 节点-模型切换矩阵 */}
        <aside className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-1 text-sm font-semibold text-slate-700">节点 × 模型 快速切换</h2>
          <p className="mb-3 text-[11px] text-slate-500">为任意可调用节点直接指定模型，立即生效</p>
          <div className="space-y-3">
            {pipelines.map((pl) => (
              <div key={pl.id}>
                <div className="mb-1.5 text-[11px] font-medium text-violet-600">{pl.name}</div>
                <div className="space-y-1.5">
                  {pl.nodes.filter((n) => n.modelId).map((n) => (
                    <div key={n.id} className="flex items-center gap-2">
                      <span className="w-20 shrink-0 truncate text-[11px] text-slate-500">{n.label}</span>
                      <select
                        value={n.modelId}
                        onChange={(e) => setNodeModel(pl.id, n.id, e.target.value)}
                        className="min-w-0 flex-1 rounded-md border border-slate-200 bg-slate-100 px-1.5 py-1 text-[10px] text-slate-700 outline-none focus:border-violet-500"
                      >
                        {models.filter((m) => m.status === '已接入').map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-dashed border-slate-200 p-2.5 text-[10px] leading-relaxed text-slate-500">
            提示：切换后可在「节点流程管理」发起试运行，或在用户端实际生成，对比不同模型的生成效果与 Token 消耗。
          </div>
        </aside>
      </div>
    </div>
  );
}
