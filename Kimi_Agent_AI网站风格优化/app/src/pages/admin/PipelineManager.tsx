import { Fragment, useState } from 'react';
import { Workflow, ArrowRight, Cpu, Play, CheckCircle2, Loader2, Database, FileText, Boxes, ImageIcon, Braces, ScanSearch } from 'lucide-react';
import { useStore } from '@/store/AppStore';

const NODE_ICONS: Record<string, React.ElementType> = {
  'n-upload': Database, 'n-parse': FileText, 'n-struct': Braces, 'n-embed': ScanSearch, 'n-store': Boxes,
  'n-understand': FileText, 'n-match': ScanSearch, 'n-frame': Workflow, 'n-assemble': ImageIcon, 'n-doc': Braces,
  'n-region': ScanSearch, 'n-instruct': FileText, 'n-rematch': ScanSearch, 'n-redraw': ImageIcon, 'n-merge': Workflow,
};

export default function PipelineManager() {
  const { pipelines, models, setNodeModel, addTokens } = useStore();
  const [running, setRunning] = useState<Record<string, number>>({});

  const connected = models.filter((m) => m.status === '已接入');
  const modelName = (id: string) => models.find((m) => m.id === id)?.name ?? '—';

  const testRun = (plId: string, nodes: { id: string; avgTokens: number }[]) => {
    if (running[plId] !== undefined) return;
    setRunning((r) => ({ ...r, [plId]: 0 }));
    let i = 0;
    const timer = setInterval(() => {
      i += 1;
      if (i <= nodes.length) {
        setRunning((r) => ({ ...r, [plId]: i }));
        const node = nodes[i - 1];
        if (node && node.avgTokens > 0) addTokens('文生图', Math.round(node.avgTokens / 20));
      } else {
        clearInterval(timer);
        setTimeout(() => setRunning((r) => { const n = { ...r }; delete n[plId]; return n; }), 1500);
      }
    }, 900);
  };

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-lg font-semibold text-slate-800">节点流程管理</h1>
        <p className="mt-0.5 text-xs text-slate-500">数据处理 / 文生图 / 图改图 三条流水线，节点级模型配置与试运行</p>
      </header>

      <div className="space-y-5">
        {pipelines.map((pl) => {
          const progress = running[pl.id];
          return (
            <section key={pl.id} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
                  <Workflow className="h-4.5 w-4.5" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">{pl.name}</h2>
                  <p className="text-[11px] text-slate-500">{pl.desc}</p>
                </div>
                <button
                  onClick={() => testRun(pl.id, pl.nodes)}
                  disabled={progress !== undefined}
                  className="ml-auto flex items-center gap-1.5 rounded-lg border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-700 transition hover:bg-violet-100 disabled:opacity-40"
                >
                  <Play className="h-3 w-3" /> 试运行
                </button>
              </div>

              {/* 节点流 */}
              <div className="flex flex-wrap items-stretch gap-2">
                {pl.nodes.map((n, i) => {
                  const Icon = NODE_ICONS[n.id] ?? Cpu;
                  const isActive = progress !== undefined && i === progress;
                  const isDone = progress !== undefined && i < progress;
                  return (
                    <Fragment key={n.id}>
                      {i > 0 && (
                        <div className="flex items-center">
                          <ArrowRight className={`h-4 w-4 ${isDone || isActive ? 'text-violet-600' : 'text-slate-600'}`} />
                        </div>
                      )}
                      <div className={`min-w-[170px] flex-1 rounded-xl border p-3 transition ${
                        isActive ? 'border-violet-400 bg-violet-100 shadow-lg shadow-violet-500/10' : isDone ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-slate-200 bg-slate-50'
                      }`}>
                        <div className="flex items-center gap-2">
                          <Icon className={`h-4 w-4 ${isActive ? 'text-violet-700' : isDone ? 'text-emerald-600' : 'text-slate-500'}`} />
                          <span className="text-xs font-semibold text-slate-800">{n.label}</span>
                          <span className="ml-auto">
                            {isActive ? <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-600" /> : isDone ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : <span className="font-mono text-[9px] text-slate-400">#{i + 1}</span>}
                          </span>
                        </div>
                        <p className="mt-1.5 min-h-[28px] text-[10px] leading-snug text-slate-500">{n.desc}</p>
                        {/* 模型选择 */}
                        {n.modelId ? (
                          <div className="mt-2">
                            <select
                              value={n.modelId}
                              onChange={(e) => setNodeModel(pl.id, n.id, e.target.value)}
                              className="w-full truncate rounded-md border border-slate-300 bg-white px-1.5 py-1 text-[10px] text-violet-700 outline-none focus:border-violet-500"
                            >
                              {connected.map((m) => (
                                <option key={m.id} value={m.id}>{m.name}（{m.provider}）</option>
                              ))}
                            </select>
                          </div>
                        ) : (
                          <div className="mt-2 rounded-md border border-dashed border-slate-200 px-1.5 py-1 text-center text-[10px] text-slate-400">本地处理 · 无模型调用</div>
                        )}
                        <div className="mt-1.5 flex items-center justify-between text-[9px] text-slate-400">
                          <span>模型：{modelName(n.modelId)}</span>
                          {n.avgTokens > 0 && <span className="font-mono">≈{n.avgTokens} tok/次</span>}
                        </div>
                      </div>
                    </Fragment>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
