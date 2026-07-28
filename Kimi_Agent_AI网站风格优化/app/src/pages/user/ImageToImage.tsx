import { useEffect, useRef, useState } from 'react';
import {
  SquareDashedMousePointer, MousePointer2, Trash2, RefreshCw, Loader2, CheckCircle2,
  Download, FileDown, History, CircleAlert,
} from 'lucide-react';
import PrimitivePicker from '@/components/PrimitivePicker';
import PatentFigure3D from '@/components/PatentFigure3D';
import { buildParamDoc, exportFigureAsPng } from '@/components/PatentFigure';
import ParamDoc, { paramDocToMarkdown, downloadText } from '@/components/ParamDoc';
import { useStore } from '@/store/AppStore';
import type { EditRegion, GeneratedResult } from '@/types';

const GEN_STAGES = ['区域解析：识别框选范围内构件', '指令理解：融合修改描述与替换图元', '图元重匹配：检索替换图元', '局部修改：区域内重绘', '组装合成：全图合成与文档更新'];

const BASE_IDS = ['prm-0604', 'prm-0701', 'prm-0306', 'prm-0301', 'prm-0201', 'prm-0202', 'prm-0101', 'prm-0102'];

const BASE: GeneratedResult = {
  id: 'G-BASE01',
  version: 1,
  prompt: '一种齿轮减速传动装置，电机经联轴器驱动齿轮副，传动轴由轴承支承于箱体',
  primitiveIds: BASE_IDS,
  docRows: buildParamDoc(BASE_IDS),
  createdAt: new Date().toLocaleString('zh-CN', { hour12: false }),
};

interface DragRect { x0: number; y0: number; x1: number; y1: number }

export default function ImageToImage() {
  const { addTokens } = useStore();
  const [versions, setVersions] = useState<GeneratedResult[]>([BASE]);
  const [vIdx, setVIdx] = useState(0);
  const [toolOn, setToolOn] = useState(true);
  const [regions, setRegions] = useState<EditRegion[]>([]);
  const [drag, setDrag] = useState<DragRect | null>(null);
  const [stage, setStage] = useState(-1);
  const figWrapRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const current = versions[vIdx];
  const generating = stage >= 0 && stage < GEN_STAGES.length;
  const isLatest = vIdx === versions.length - 1;

  // ---------- 框选 ----------
  const pct = (e: React.MouseEvent) => {
    const rect = figWrapRef.current!.getBoundingClientRect();
    return {
      x: Math.min(100, Math.max(0, ((e.clientX - rect.left) / rect.width) * 100)),
      y: Math.min(100, Math.max(0, ((e.clientY - rect.top) / rect.height) * 100)),
    };
  };

  const onDown = (e: React.MouseEvent) => {
    if (!toolOn || generating || !isLatest) return;
    if (regions.length >= 3) return;
    const p = pct(e);
    setDrag({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  };
  const onMove = (e: React.MouseEvent) => {
    if (!drag) return;
    const p = pct(e);
    setDrag({ ...drag, x1: p.x, y1: p.y });
  };
  const onUp = () => {
    if (!drag) return;
    const x = Math.min(drag.x0, drag.x1), y = Math.min(drag.y0, drag.y1);
    const w = Math.abs(drag.x1 - drag.x0), h = Math.abs(drag.y1 - drag.y0);
    if (w > 3 && h > 3) {
      setRegions((rs) => [...rs, { id: `R${Date.now()}`, x, y, w, h, instruction: '', primitiveIds: [] }]);
    }
    setDrag(null);
  };

  const updateRegion = (id: string, patch: Partial<EditRegion>) =>
    setRegions((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const toggleRegionPrimitive = (id: string, pid: string) =>
    setRegions((rs) =>
      rs.map((r) => (r.id === id ? { ...r, primitiveIds: r.primitiveIds.includes(pid) ? r.primitiveIds.filter((x) => x !== pid) : [...r.primitiveIds, pid] } : r)),
    );

  // ---------- 重新生成 ----------
  const canRegen = regions.length > 0 && regions.every((r) => r.instruction.trim() || r.primitiveIds.length > 0);

  const regenerate = () => {
    if (!canRegen || generating) return;
    setStage(0);
    addTokens('图改图', 5200);
    addTokens('参数文档', 900);
    let s = 0;
    timer.current = setInterval(() => {
      s += 1;
      setStage(s);
      if (s >= GEN_STAGES.length) {
        if (timer.current) clearInterval(timer.current);
        const added = regions.flatMap((r) => r.primitiveIds).filter((id) => !current.primitiveIds.includes(id));
        const newIds = [...current.primitiveIds, ...added].slice(0, 9);
        const nv: GeneratedResult = {
          id: `G-${Date.now()}`,
          version: current.version + 1,
          prompt: current.prompt,
          primitiveIds: newIds,
          docRows: buildParamDoc(newIds),
          createdAt: new Date().toLocaleString('zh-CN', { hour12: false }),
          regions,
        };
        setVersions((vs) => [...vs, nv]);
        setVIdx(versions.length);
        setRegions([]);
      }
    }, 900);
  };

  const exportPng = () => {
    const svg = figWrapRef.current?.querySelector('svg');
    if (svg) exportFigureAsPng(svg as SVGSVGElement, `专利附图_V${current.version}.png`);
  };

  const dragRect = drag && {
    x: Math.min(drag.x0, drag.x1), y: Math.min(drag.y0, drag.y1),
    w: Math.abs(drag.x1 - drag.x0), h: Math.abs(drag.y1 - drag.y0),
  };

  return (
    <div className="grid min-h-full grid-cols-1 gap-0 lg:grid-cols-[400px_1fr]">
      {/* 左侧：区域修改指令 */}
      <div className="border-b border-slate-200 p-5 lg:border-b-0 lg:border-r">
        <h1 className="flex items-center gap-2 text-base font-semibold text-slate-800">
          <SquareDashedMousePointer className="h-4.5 w-4.5 text-violet-600" /> 图改图
        </h1>
        <p className="mt-1 text-xs text-slate-500">在右侧图上框选区域（最多 3 个），为每个区域描述修改意图并可勾选替换图元</p>

        {/* 工具开关 */}
        <div className="mt-4 flex items-center gap-2">
          <button onClick={() => setToolOn(!toolOn)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border py-2 text-xs font-medium transition ${toolOn ? 'border-violet-300 bg-violet-100 text-violet-700' : 'border-slate-200 text-slate-500'}`}>
            <SquareDashedMousePointer className="h-3.5 w-3.5" /> 框选工具 {toolOn ? '· 开启' : '· 关闭'}
          </button>
          <span className="rounded-lg border border-slate-200 px-2.5 py-2 font-mono text-xs text-slate-500">{regions.length}/3</span>
        </div>

        {/* 区域卡片 */}
        <div className="mt-4 space-y-3">
          {regions.map((r, i) => (
            <div key={r.id} className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
              <div className="mb-2 flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-amber-500/20 text-[10px] font-bold text-amber-600">{i + 1}</span>
                <span className="text-xs font-medium text-slate-700">修改区域 {i + 1}</span>
                <span className="font-mono text-[9px] text-slate-400">({r.x.toFixed(0)}%, {r.y.toFixed(0)}%) {r.w.toFixed(0)}×{r.h.toFixed(0)}%</span>
                <button onClick={() => setRegions((rs) => rs.filter((x) => x.id !== r.id))} className="ml-auto rounded p-1 text-slate-500 hover:bg-rose-500/20 hover:text-rose-600">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
              <textarea
                value={r.instruction}
                onChange={(e) => updateRegion(r.id, { instruction: e.target.value })}
                rows={2}
                placeholder="自然语言描述修改，例如：把该区域改为弹性套柱销联轴器…"
                className="w-full resize-none rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-700 outline-none placeholder:text-slate-400 focus:border-amber-500/60"
              />
              <div className="mt-2">
                <div className="mb-1 text-[10px] text-slate-500">选择替换/新增图元（{r.primitiveIds.length}）</div>
                <PrimitivePicker selected={r.primitiveIds} onToggle={(pid) => toggleRegionPrimitive(r.id, pid)} maxHeight="max-h-44" />
              </div>
            </div>
          ))}

          {regions.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-200 py-8 text-center">
              <MousePointer2 className="mx-auto h-6 w-6 text-slate-600" />
              <div className="mt-2 text-xs text-slate-500">尚未框选区域</div>
              <div className="mt-1 text-[10px] text-slate-400">在右侧图上按住拖拽即可框选</div>
            </div>
          )}
        </div>

        <button onClick={regenerate} disabled={!canRegen || generating || !isLatest}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-rose-800 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-500/20 transition hover:opacity-90 disabled:opacity-40">
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {generating ? '修改生成中…' : '按区域指令重新生成'}
        </button>
        {!isLatest && (
          <div className="mt-2 flex items-start gap-1.5 text-[10px] leading-relaxed text-slate-500">
            <CircleAlert className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" />
            当前查看的是历史版本 V{current.version}，切回最新版本后才能继续框选修改。
          </div>
        )}
      </div>

      {/* 右侧：画布面板 */}
      <div className="flex flex-col p-5">
        {/* 版本切换条（仿 Kimi 版本切换） */}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <History className="h-4 w-4 text-slate-500" />
          <div className="flex items-center rounded-full border border-slate-200 bg-white p-1">
            {versions.map((v, i) => (
              <button key={v.id} onClick={() => setVIdx(i)}
                className={`rounded-full px-3.5 py-1 text-xs font-medium transition ${i === vIdx ? 'bg-violet-600 text-white shadow shadow-violet-500/20' : 'text-slate-500 hover:text-slate-700'}`}>
                V{v.version}
              </button>
            ))}
          </div>
          {vIdx < versions.length - 1 && (
            <button onClick={() => setVIdx(versions.length - 1)} className="text-[11px] text-violet-600 hover:underline">回到最新 V{versions[versions.length - 1].version}</button>
          )}
          <span className="text-[11px] text-slate-400">{current.createdAt}</span>
          <div className="ml-auto flex items-center gap-1.5">
            <button onClick={exportPng} className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:border-violet-300 hover:text-violet-700">
              <Download className="h-3.5 w-3.5" />导出图片
            </button>
            <button onClick={() => downloadText(`参数文档_V${current.version}.md`, paramDocToMarkdown(current.docRows, `制图参数文档 V${current.version}`, current.prompt))}
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:border-violet-300 hover:text-violet-700">
              <FileDown className="h-3.5 w-3.5" />导出参数文档
            </button>
          </div>
        </div>

        {/* 画布 + 框选层 */}
        <div className="relative overflow-hidden rounded-xl border border-slate-200" ref={figWrapRef}>
          <PatentFigure3D
            primitiveIds={current.primitiveIds}
            seedKey={current.id}
            regions={[...(current.regions ?? []), ...regions]}
            changedRegionIds={(current.regions ?? []).map((r) => r.id)}
            title={`图1  机械结构三维示意图（版本 V${current.version}）`}
          />
          {/* 框选交互层 */}
          {toolOn && isLatest && !generating && (
            <div
              className={`absolute inset-0 ${regions.length >= 3 ? 'cursor-not-allowed' : 'cursor-crosshair'}`}
              onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
            >
              {dragRect && (
                <div className="absolute border-2 border-dashed border-amber-400 bg-amber-400/10"
                  style={{ left: `${dragRect.x}%`, top: `${dragRect.y}%`, width: `${dragRect.w}%`, height: `${dragRect.h}%` }} />
              )}
              {regions.length >= 3 && (
                <div className="absolute inset-x-0 top-3 mx-auto w-fit rounded-full bg-white/95 px-3 py-1 text-[11px] text-amber-600 ring-1 ring-amber-500/40">
                  已达最大框选数（3 个）
                </div>
              )}
            </div>
          )}

          {/* 生成中遮罩 */}
          {generating && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/85 backdrop-blur-sm">
              <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white/95 p-4">
                <div className="mb-2.5 flex items-center gap-2 text-xs font-medium text-slate-700">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600" /> 图改图流水线运行中
                </div>
                <ol className="space-y-1.5">
                  {GEN_STAGES.map((s, i) => (
                    <li key={s} className={`flex items-center gap-2 text-[11px] ${i < stage ? 'text-slate-500' : i === stage ? 'text-amber-700' : 'text-slate-600'}`}>
                      {i < stage ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" /> : i === stage ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="h-3.5 w-3.5 rounded-full border border-slate-200" />}
                      {s}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          )}
        </div>

        {/* 参数文档 */}
        <div className="mt-4">
          <div className="mb-1.5 flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-700">制图参数文档</h2>
            <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">V{current.version}</span>
            {current.version > 1 && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-600">已按区域指令更新</span>}
          </div>
          <ParamDoc rows={current.docRows} compact />
        </div>
      </div>
    </div>
  );
}
