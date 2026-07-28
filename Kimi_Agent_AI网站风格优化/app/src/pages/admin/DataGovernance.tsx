import { useEffect, useRef, useState } from 'react';
import {
  UploadCloud, FileText, FileCode2, FileImage, CheckCircle2, Loader2, ChevronRight,
  Braces, Table2, Sparkles, ArrowRight,
} from 'lucide-react';
import { seedParseOutput } from '@/data/seed';
import { PrimitiveGlyph } from '@/data/primitives';
import { useStore } from '@/store/AppStore';

const STAGES = ['文件接入与校验', '段落级语义解析', '结构化信息抽取', '向量化', '写入图元库'];

interface Task {
  id: string;
  fileName: string;
  fileType: string;
  stage: number;
  done: boolean;
  time: string;
}

const HISTORY: Task[] = [
  { id: 'T-2031', fileName: 'CN114xxxxxxA_减速器.docx', fileType: 'DOCX', stage: 5, done: true, time: '2026-07-22 16:40' },
  { id: 'T-2032', fileName: '蜗杆传动图元.xml', fileType: 'XML', stage: 5, done: true, time: '2026-07-23 09:12' },
  { id: 'T-2033', fileName: '密封件合集.pdf', fileType: 'PDF', stage: 5, done: true, time: '2026-07-23 15:26' },
];

function StageIcon({ state }: { state: 'wait' | 'run' | 'done' }) {
  if (state === 'done') return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (state === 'run') return <Loader2 className="h-4 w-4 animate-spin text-violet-600" />;
  return <span className="h-4 w-4 rounded-full border border-slate-300" />;
}

export default function DataGovernance() {
  const { addTokens } = useStore();
  const [task, setTask] = useState<Task | null>(null);
  const [view, setView] = useState<'table' | 'json'>('table');
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const startParse = (name: string) => {
    if (task && !task.done) return;
    const ext = name.split('.').pop()?.toUpperCase() ?? 'DOCX';
    const t: Task = { id: `T-${2034 + Math.floor(Math.random() * 40)}`, fileName: name, fileType: ext, stage: 0, done: false, time: new Date().toLocaleString('zh-CN', { hour12: false }) };
    setTask(t);
    addTokens('数据解析', 3200);
    let s = 0;
    timer.current = setInterval(() => {
      s += 1;
      setTask((prev) => (prev ? { ...prev, stage: s, done: s >= STAGES.length } : prev));
      if (s === 3) addTokens('向量化', 800);
      if (s >= STAGES.length && timer.current) clearInterval(timer.current);
    }, 1300);
  };

  const onFiles = (files: FileList | null) => {
    if (files && files.length > 0) startParse(files[0].name);
  };

  const out = seedParseOutput;

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-lg font-semibold text-slate-800">图元数据治理</h1>
        <p className="mt-0.5 text-xs text-slate-500">图元/专利文档上传 → 段落级语义解析 → 结构化输出，支持 DOCX / PDF / XML / SVG 两种及以上格式</p>
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
        {/* 左：上传 + 流程 */}
        <div className="space-y-5 xl:col-span-2">
          {/* 上传模块 */}
          <section
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles(e.dataTransfer.files); }}
            onClick={() => inputRef.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
              drag ? 'border-violet-400 bg-violet-50' : 'border-slate-200 bg-white hover:border-slate-500'
            }`}
          >
            <input ref={inputRef} type="file" accept=".docx,.pdf,.xml,.svg" className="hidden" onChange={(e) => onFiles(e.target.files)} />
            <UploadCloud className="mx-auto h-10 w-10 text-violet-600" />
            <div className="mt-3 text-sm font-medium text-slate-700">点击或拖拽上传图元/专利文档</div>
            <div className="mt-1 text-xs text-slate-500">支持 DOCX · PDF · XML · SVG，单文件 ≤ 50MB</div>
            <div className="mt-4 flex justify-center gap-2">
              {['DOCX', 'PDF', 'XML', 'SVG'].map((f) => (
                <span key={f} className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">{f}</span>
              ))}
            </div>
          </section>

          {/* 解析流程 */}
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">解析流程</h2>
              {task && (
                <span className={`rounded-full px-2 py-0.5 text-[10px] ${task.done ? 'bg-emerald-500/15 text-emerald-600' : 'bg-violet-100 text-violet-600'}`}>
                  {task.done ? '解析完成' : `解析中 · 阶段 ${Math.min(task.stage + 1, 5)}/5`}
                </span>
              )}
            </div>
            {!task ? (
              <div className="py-6 text-center text-xs text-slate-400">上传文件后自动启动五阶段解析流水线</div>
            ) : (
              <div>
                <div className="mb-3 flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2">
                  {task.fileType === 'PDF' ? <FileText className="h-4 w-4 text-rose-600" /> : task.fileType === 'XML' ? <FileCode2 className="h-4 w-4 text-amber-600" /> : task.fileType === 'SVG' ? <FileImage className="h-4 w-4 text-emerald-600" /> : <FileText className="h-4 w-4 text-violet-600" />}
                  <span className="truncate text-xs text-slate-600">{task.fileName}</span>
                  <span className="ml-auto shrink-0 font-mono text-[10px] text-slate-500">{task.id}</span>
                </div>
                <ol className="space-y-2">
                  {STAGES.map((s, i) => {
                    const state = i < task.stage ? 'done' : i === task.stage ? 'run' : 'wait';
                    return (
                      <li key={s} className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs transition ${state === 'run' ? 'bg-violet-50 text-violet-700' : state === 'done' ? 'text-slate-600' : 'text-slate-400'}`}>
                        <StageIcon state={state} />
                        <span className="flex-1">{s}</span>
                        {state === 'done' && <span className="font-mono text-[10px] text-slate-400">{(0.6 + i * 1.1).toFixed(1)}s</span>}
                      </li>
                    );
                  })}
                </ol>
                {/* 进度条 */}
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-violet-600 to-emerald-400 transition-all duration-700" style={{ width: `${(task.stage / STAGES.length) * 100}%` }} />
                </div>
              </div>
            )}

            {/* 历史任务 */}
            <div className="mt-4 border-t border-slate-200 pt-3">
              <div className="mb-2 text-[11px] font-medium text-slate-500">近期解析任务</div>
              <div className="space-y-1.5">
                {HISTORY.map((t) => (
                  <div key={t.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500/70" />
                    <span className="truncate">{t.fileName}</span>
                    <span className="ml-auto shrink-0 text-[10px] text-slate-400">{t.time}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>

        {/* 右：解析输出 */}
        <section className="rounded-xl border border-slate-200 bg-white p-4 xl:col-span-3">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-700">解析内容输出</h2>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-500">{out.fileName}</span>
            <div className="ml-auto flex rounded-md border border-slate-200 p-0.5">
              {([['table', Table2, '结构化'], ['json', Braces, 'JSON']] as const).map(([v, Icon, label]) => (
                <button key={v} onClick={() => setView(v)} className={`flex items-center gap-1 rounded px-2 py-1 text-[11px] ${view === v ? 'bg-violet-100 text-violet-700' : 'text-slate-500'}`}>
                  <Icon className="h-3 w-3" />{label}
                </button>
              ))}
            </div>
          </div>

          {view === 'json' ? (
            <pre className="max-h-[560px] overflow-auto rounded-lg bg-slate-50 p-4 font-mono text-[11px] leading-relaxed text-emerald-700">
              {JSON.stringify(out, null, 2)}
            </pre>
          ) : (
            <div className="space-y-4">
              {/* 元信息 */}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {Object.entries(out.meta).map(([k, v]) => (
                  <div key={k} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                    <div className="text-[10px] text-slate-500">{k}</div>
                    <div className="mt-0.5 text-xs font-medium text-slate-700">{v}</div>
                  </div>
                ))}
              </div>

              {/* 构件表 */}
              <div>
                <div className="mb-1.5 text-xs font-medium text-slate-500">抽取构件（段落级语义解析，{out.components.length} 项）</div>
                <div className="overflow-hidden rounded-lg border border-slate-200">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-slate-100 text-slate-500">
                        <th className="px-3 py-2">标记</th><th className="px-3 py-2">构件名称</th><th className="px-3 py-2">关键参数</th><th className="px-3 py-2">置信度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {out.components.map((c) => (
                        <tr key={c.refNo} className="border-t border-slate-200 text-slate-600">
                          <td className="px-3 py-2"><span className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-300">{c.refNo}</span></td>
                          <td className="px-3 py-2 text-slate-800">{c.name}</td>
                          <td className="px-3 py-2 text-slate-500">{c.params.join('；')}</td>
                          <td className="px-3 py-2">
                            <div className="flex items-center gap-1.5">
                              <div className="h-1 w-14 overflow-hidden rounded-full bg-slate-200">
                                <div className="h-full rounded-full bg-emerald-500" style={{ width: `${c.confidence * 100}%` }} />
                              </div>
                              <span className="font-mono text-[10px] text-slate-500">{(c.confidence * 100).toFixed(0)}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* 连接关系 */}
              <div>
                <div className="mb-1.5 text-xs font-medium text-slate-500">装配 / 连接关系（{out.relations.length} 条）</div>
                <div className="space-y-1.5">
                  {out.relations.map((r) => (
                    <div key={r} className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      <ChevronRight className="h-3 w-3 shrink-0 text-violet-600" />{r}
                    </div>
                  ))}
                </div>
              </div>

              {/* 推荐图元 */}
              <div>
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-slate-500">
                  <Sparkles className="h-3.5 w-3.5 text-amber-600" /> 智能匹配图元（向量检索 Top-4）
                </div>
                <div className="flex flex-wrap gap-2">
                  {out.suggestedPrimitives.map((id) => (
                    <div key={id} className="flex items-center gap-2 rounded-lg border border-violet-300 bg-violet-50 px-3 py-2">
                      <PrimitiveGlyph id={id} className="h-8 w-8 text-violet-700" />
                      <div>
                        <div className="text-xs text-slate-700">{id.replace('prm-', 'PRM-')}</div>
                        <div className="flex items-center gap-1 text-[10px] text-violet-600">相似度 0.9{Math.floor(Math.random() * 9)} <ArrowRight className="h-2.5 w-2.5" /> 待入库审核</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
