import { useMemo, useState } from 'react';
import { FolderTree, Search, Plus, Pencil, Trash2, X, FolderOpen, Folder, Boxes } from 'lucide-react';
import { categoryTree, PrimitiveGlyph } from '@/data/primitives';
import { useStore } from '@/store/AppStore';
import type { Primitive } from '@/types';

const EMPTY_FORM = { code: '', name: '', category: '01 连接紧固件', standard: '', description: '', material: '', paramsText: '' };

export default function LibraryManager() {
  const { primitives, addPrimitive, updatePrimitive, deletePrimitive } = useStore();
  const [cat, setCat] = useState<string | null>(null);
  const [kw, setKw] = useState('');
  const [modal, setModal] = useState<null | { mode: 'add' | 'edit'; target?: Primitive }>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [confirmDel, setConfirmDel] = useState<Primitive | null>(null);

  const counts = useMemo(() => {
    const m = new Map<string, number>();
    primitives.forEach((p) => m.set(p.category, (m.get(p.category) ?? 0) + 1));
    return m;
  }, [primitives]);

  const list = useMemo(
    () =>
      primitives.filter(
        (p) => (!cat || p.category === cat) && (!kw || p.name.includes(kw) || p.code.includes(kw) || p.standard.includes(kw)),
      ),
    [primitives, cat, kw],
  );

  const openAdd = () => {
    setForm({ ...EMPTY_FORM, category: cat ?? '01 连接紧固件', code: `PRM-0${Math.floor(100 + Math.random() * 800)}` });
    setModal({ mode: 'add' });
  };
  const openEdit = (p: Primitive) => {
    setForm({
      code: p.code, name: p.name, category: p.category, standard: p.standard,
      description: p.description, material: p.material,
      paramsText: p.params.map((x) => `${x.label}|${x.unit ?? ''}|${x.value}`).join('\n'),
    });
    setModal({ mode: 'edit', target: p });
  };

  const save = () => {
    const params = form.paramsText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, i) => {
        const [label, unit, value] = line.split('|');
        return { key: `p${i}`, label: label ?? '', unit: unit ?? '', value: value ?? '' };
      });
    if (modal?.mode === 'add') {
      addPrimitive({
        id: form.code.toLowerCase(), code: form.code, name: form.name, category: form.category,
        standard: form.standard || '企业标准', description: form.description, material: form.material,
        params, version: 'v1.0', status: '待审核', updatedAt: new Date().toISOString().slice(0, 10), usageCount: 0,
      });
    } else if (modal?.target) {
      updatePrimitive({ ...modal.target, ...form, params, updatedAt: new Date().toISOString().slice(0, 10) });
    }
    setModal(null);
  };

  return (
    <div className="p-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">图元库存储管理</h1>
          <p className="mt-0.5 text-xs text-slate-500">目录层级建设 · 元数据管理 · 支持增删改查</p>
        </div>
        <button onClick={openAdd} className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-3.5 py-2 text-xs font-medium text-white shadow shadow-violet-500/20 transition hover:bg-violet-500">
          <Plus className="h-3.5 w-3.5" /> 新增图元
        </button>
      </header>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        {/* 目录树 */}
        <aside className="rounded-xl border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center gap-1.5 px-1 text-xs font-semibold text-slate-600">
            <FolderTree className="h-3.5 w-3.5 text-violet-600" /> 目录层级
          </div>
          <button
            onClick={() => setCat(null)}
            className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition ${!cat ? 'bg-violet-100 text-violet-700' : 'text-slate-500 hover:bg-slate-100'}`}
          >
            <Boxes className="h-3.5 w-3.5" /> {categoryTree.name}
            <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px]">{primitives.length}</span>
          </button>
          <div className="ml-3 mt-1 space-y-0.5 border-l border-slate-200 pl-2">
            {categoryTree.children?.map((c) => (
              <button
                key={c.id}
                onClick={() => setCat(c.name)}
                className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs transition ${cat === c.name ? 'bg-violet-100 text-violet-700' : 'text-slate-500 hover:bg-slate-100'}`}
              >
                {cat === c.name ? <FolderOpen className="h-3.5 w-3.5 text-violet-600" /> : <Folder className="h-3.5 w-3.5" />}
                <span className="truncate">{c.name}</span>
                <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px]">{counts.get(c.name) ?? 0}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-dashed border-slate-200 p-2.5 text-[10px] leading-relaxed text-slate-500">
            支持多级目录扩展。新增目录将同步至用户端图元选择器与向量检索命名空间。
          </div>
        </aside>

        {/* 元数据表 */}
        <section className="lg:col-span-3">
          <div className="mb-3 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
              <input value={kw} onChange={(e) => setKw(e.target.value)} placeholder="按名称 / 编码 / 国标号检索…"
                className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-8 pr-3 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-violet-500" />
            </div>
            <span className="text-xs text-slate-500">共 {list.length} 条元数据</span>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-100 text-slate-500">
                  <th className="px-3 py-2.5">图元</th>
                  <th className="px-3 py-2.5">编码 / 国标</th>
                  <th className="px-3 py-2.5">参数化字段</th>
                  <th className="px-3 py-2.5">版本 / 状态</th>
                  <th className="px-3 py-2.5">调用量</th>
                  <th className="px-3 py-2.5 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {list.map((p) => (
                  <tr key={p.id} className="border-t border-slate-200 text-slate-600 hover:bg-slate-50">
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 text-violet-700">
                          <PrimitiveGlyph id={p.id} className="h-7 w-7" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-800">{p.name}</div>
                          <div className="text-[10px] text-slate-500">{p.category}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="font-mono text-violet-700">{p.code}</div>
                      <div className="mt-0.5 text-[10px] text-slate-500">{p.standard}</div>
                    </td>
                    <td className="max-w-[220px] px-3 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {p.params.map((x) => (
                          <span key={x.key} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{x.label}={x.value}{x.unit !== '-' ? x.unit : ''}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="font-mono text-[10px] text-slate-500">{p.version}</div>
                      <span className={`mt-0.5 inline-block rounded-full px-1.5 py-0.5 text-[10px] ${p.status === '已入库' ? 'bg-emerald-500/15 text-emerald-600' : 'bg-amber-500/15 text-amber-600'}`}>{p.status}</span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-500">{p.usageCount}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => openEdit(p)} className="rounded-md p-1.5 text-slate-500 transition hover:bg-slate-200/60 hover:text-violet-700" title="编辑">
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => setConfirmDel(p)} className="rounded-md p-1.5 text-slate-500 transition hover:bg-rose-500/20 hover:text-rose-600" title="删除">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {list.length === 0 && <div className="py-10 text-center text-xs text-slate-400">无匹配图元</div>}
          </div>
        </section>
      </div>

      {/* 新增/编辑弹窗 */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setModal(null)}>
          <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-800">{modal.mode === 'add' ? '新增图元' : `编辑图元 · ${modal.target?.code}`}</h3>
              <button onClick={() => setModal(null)} className="text-slate-500 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-slate-500">图元编码
                <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="text-xs text-slate-500">图元名称
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="text-xs text-slate-500">所属目录
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500">
                  {categoryTree.children?.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}
                </select>
              </label>
              <label className="text-xs text-slate-500">执行标准
                <input value={form.standard} onChange={(e) => setForm({ ...form, standard: e.target.value })} placeholder="GB/T …" className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="col-span-2 text-xs text-slate-500">材料
                <input value={form.material} onChange={(e) => setForm({ ...form, material: e.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="col-span-2 text-xs text-slate-500">语义描述
                <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
              <label className="col-span-2 text-xs text-slate-500">参数化字段（每行：参数名|单位|默认值）
                <textarea value={form.paramsText} onChange={(e) => setForm({ ...form, paramsText: e.target.value })} rows={3} placeholder={'公称直径|mm|M8\n螺杆长度|mm|35'} className="mt-1 w-full rounded-md border border-slate-200 bg-slate-100 px-2.5 py-1.5 font-mono text-xs text-slate-700 outline-none focus:border-violet-500" />
              </label>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setModal(null)} className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs text-slate-500 hover:bg-slate-100">取消</button>
              <button onClick={save} disabled={!form.name || !form.code} className="rounded-lg bg-violet-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-violet-500 disabled:opacity-40">保存入库</button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认 */}
      {confirmDel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setConfirmDel(null)}>
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-slate-800">确认删除图元？</h3>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              将删除 <span className="text-rose-600">{confirmDel.name}（{confirmDel.code}）</span> 及其元数据与向量索引。该操作不可撤销，关联数据集中的引用将标记为失效。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setConfirmDel(null)} className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs text-slate-500 hover:bg-slate-100">取消</button>
              <button onClick={() => { deletePrimitive(confirmDel.id); setConfirmDel(null); }} className="rounded-lg bg-rose-500 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-rose-400">确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
