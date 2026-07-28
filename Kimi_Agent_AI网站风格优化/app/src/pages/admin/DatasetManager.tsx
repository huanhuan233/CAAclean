import { useMemo, useState } from 'react';
import { Layers, Plus, Trash2, Star, FileText, Image as ImageIcon, ArrowRight, X } from 'lucide-react';
import { DATASET_LABELS } from '@/data/seed';
import { useStore } from '@/store/AppStore';
import type { DatasetType } from '@/types';

const TYPE_ICONS: Record<string, React.ReactNode> = {
  'text-patent': <FileText className="h-3.5 w-3.5 text-violet-600" />,
  'text-primitive': <FileText className="h-3.5 w-3.5 text-emerald-600" />,
  'image-edit': <ImageIcon className="h-3.5 w-3.5 text-amber-600" />,
  'param-primitive': <FileText className="h-3.5 w-3.5 text-violet-600" />,
};

export default function DatasetManager() {
  const { datasets, addDataset, deleteDataset } = useStore();
  const [tab, setTab] = useState<DatasetType>('text-patent');
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ title: '', input: '', output: '' });

  const list = useMemo(() => datasets.filter((d) => d.type === tab), [datasets, tab]);
  const countOf = (t: DatasetType) => datasets.filter((d) => d.type === t).length;

  const save = () => {
    addDataset({
      id: `DS-${Math.floor(1000 + Math.random() * 9000)}`,
      type: tab, title: form.title, input: form.input, output: form.output,
      pairs: tab === 'image-edit' ? form.output : undefined,
      quality: 0, source: '人工录入', createdAt: new Date().toISOString().slice(0, 10),
    });
    setShowAdd(false);
    setForm({ title: '', input: '', output: '' });
  };

  return (
    <div className="p-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">数据集管理</h1>
          <p className="mt-0.5 text-xs text-slate-500">四类训练/评测数据集：文-图、文-图元、图-文-图、参数文档-图元</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-violet-500">
          <Plus className="h-3.5 w-3.5" /> 录入数据
        </button>
      </header>

      {/* 数据集类型卡片 */}
      <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {(Object.keys(DATASET_LABELS) as DatasetType[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-xl border p-4 text-left transition ${tab === t ? 'border-violet-300 bg-violet-50 ring-1 ring-violet-200' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100">{TYPE_ICONS[t]}</span>
              <Layers className="ml-auto h-3.5 w-3.5 text-slate-400" />
            </div>
            <div className="mt-2.5 text-xs font-medium leading-snug text-slate-700">{DATASET_LABELS[t]}</div>
            <div className="mt-1 font-mono text-lg font-semibold text-violet-700">{countOf(t)}<span className="ml-1 text-[10px] font-normal text-slate-500">条</span></div>
          </button>
        ))}
      </div>

      {/* 记录列表 */}
      <div className="space-y-3">
        {list.map((d) => (
          <div key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-200">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100">{TYPE_ICONS[d.type]}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-slate-800">{d.title}</span>
                  <span className="font-mono text-[10px] text-slate-400">{d.id}</span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{d.source}</span>
                  <span className="flex items-center gap-0.5 text-[11px] text-amber-600">
                    <Star className="h-3 w-3 fill-amber-400" />{d.quality > 0 ? d.quality.toFixed(1) : '未评分'}
                  </span>
                  <span className="ml-auto text-[10px] text-slate-400">{d.createdAt}</span>
                </div>

                {d.type === 'image-edit' ? (
                  <div className="mt-2.5 grid grid-cols-1 gap-2 md:grid-cols-3">
                    {['原图区域', '修改指令', '目标图'].map((label, i) => (
                      <div key={label} className="relative rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="text-[10px] text-slate-500">{label}</div>
                        <div className="mt-1 line-clamp-2 text-xs text-slate-600">
                          {i === 0 ? d.input : i === 1 ? '“' + (d.pairs?.split('→')[1]?.trim().replace(/[“”]/g, '') ?? '') + '”' : d.output}
                        </div>
                        {i < 2 && <ArrowRight className="absolute -right-2.5 top-1/2 hidden h-4 w-4 -translate-y-1/2 rounded-full bg-slate-200 p-0.5 text-slate-600 md:block" />}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-2.5 grid grid-cols-1 gap-2 md:grid-cols-2">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                      <div className="text-[10px] text-slate-500">{d.type === 'param-primitive' ? '制图参数文档' : '自然语言描述'}</div>
                      <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-600">{d.input}</div>
                    </div>
                    <div className="relative rounded-lg border border-violet-200 bg-violet-50 px-3 py-2">
                      <ArrowRight className="absolute -left-2.5 top-1/2 hidden h-4 w-4 -translate-y-1/2 rounded-full bg-slate-200 p-0.5 text-slate-600 md:block" />
                      <div className="text-[10px] text-violet-600">{d.type === 'text-patent' ? '专利附图' : '匹配图元'}</div>
                      <div className="mt-1 line-clamp-2 font-mono text-xs text-violet-700">{d.output}</div>
                    </div>
                  </div>
                )}
              </div>
              <button onClick={() => deleteDataset(d.id)} className="rounded-md p-1.5 text-slate-500 transition hover:bg-rose-500/20 hover:text-rose-600" title="删除记录">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
        {list.length === 0 && <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-xs text-slate-400">该数据集暂无记录</div>}
      </div>

      {/* 录入弹窗 */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setShowAdd(false)}>
          <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-800">录入数据 · {DATASET_LABELS[tab]}</h3>
              <button onClick={() => setShowAdd(false)} className="text-slate-500 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-3">
              <label className="block text-xs text-slate-500">样本标题
                <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="block text-xs text-slate-500">输入（自然语言描述 / 参数文档 / 原图说明）
                <textarea value={form.input} onChange={(e) => setForm({ ...form, input: e.target.value })} rows={3} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="block text-xs text-slate-500">输出（目标专利图编号 / 图元编码 / 目标图说明）
                <textarea value={form.output} onChange={(e) => setForm({ ...form, output: e.target.value })} rows={2} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setShowAdd(false)} className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs text-slate-500 hover:bg-slate-100">取消</button>
              <button onClick={save} disabled={!form.title || !form.input} className="rounded-lg bg-violet-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-violet-500 disabled:opacity-40">保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
