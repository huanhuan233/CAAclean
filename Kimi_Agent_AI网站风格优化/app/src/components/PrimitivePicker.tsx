import { useMemo, useState } from 'react';
import { Search, Check } from 'lucide-react';
import { PrimitiveGlyph, categoryTree } from '@/data/primitives';
import { useStore } from '@/store/AppStore';

interface Props {
  selected: string[];
  onToggle: (id: string) => void;
  maxHeight?: string;
}

/** 图元选择器：目录分组 + 示意图 + 名称 */
export default function PrimitivePicker({ selected, onToggle, maxHeight = 'max-h-72' }: Props) {
  const { primitives } = useStore();
  const [kw, setKw] = useState('');
  const [cat, setCat] = useState<string | null>(null);

  const list = useMemo(() => {
    return primitives.filter(
      (p) =>
        (!cat || p.category === cat) &&
        (!kw || p.name.includes(kw) || p.code.toLowerCase().includes(kw.toLowerCase())),
    );
  }, [primitives, kw, cat]);

  const groups = useMemo(() => {
    const m = new Map<string, typeof list>();
    list.forEach((p) => {
      if (!m.has(p.category)) m.set(p.category, []);
      m.get(p.category)!.push(p);
    });
    return [...m.entries()];
  }, [list]);

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50">
      <div className="flex items-center gap-2 border-b border-slate-200 p-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            value={kw}
            onChange={(e) => setKw(e.target.value)}
            placeholder="搜索图元名称 / 编码…"
            className="w-full rounded-md border border-slate-200 bg-slate-100 py-1.5 pl-7 pr-2 text-xs text-slate-700 outline-none placeholder:text-slate-500 focus:border-violet-500"
          />
        </div>
        <select
          value={cat ?? ''}
          onChange={(e) => setCat(e.target.value || null)}
          className="rounded-md border border-slate-200 bg-slate-100 px-2 py-1.5 text-xs text-slate-600 outline-none focus:border-violet-500"
        >
          <option value="">全部目录</option>
          {categoryTree.children?.map((c) => (
            <option key={c.id} value={c.name}>{c.name}</option>
          ))}
        </select>
      </div>
      <div className={`overflow-auto p-2 ${maxHeight}`}>
        {groups.map(([g, items]) => (
          <div key={g} className="mb-3">
            <div className="mb-1.5 px-1 text-[11px] font-medium tracking-wide text-slate-500">{g}</div>
            <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4">
              {items.map((p) => {
                const on = selected.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => onToggle(p.id)}
                    title={`${p.code} · ${p.description}`}
                    className={`group relative flex flex-col items-center rounded-md border p-1.5 transition ${
                      on
                        ? 'border-violet-600 bg-violet-600 text-white shadow-sm shadow-violet-500/30'
                        : 'border-slate-200 bg-white text-slate-500 hover:border-violet-300 hover:text-violet-600'
                    }`}
                  >
                    {on && (
                      <span className="absolute right-1 top-1 rounded-full bg-violet-600 p-0.5 text-white">
                        <Check className="h-2.5 w-2.5" />
                      </span>
                    )}
                    <PrimitiveGlyph id={p.id} className="h-9 w-9" />
                    <span className="mt-1 line-clamp-1 text-[11px]">{p.name}</span>
                    <span className="font-mono text-[9px] text-slate-400">{p.code}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        {list.length === 0 && <div className="py-8 text-center text-xs text-slate-500">未找到匹配图元</div>}
      </div>
    </div>
  );
}
