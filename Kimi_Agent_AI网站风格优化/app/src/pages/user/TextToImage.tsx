import { useEffect, useRef, useState } from 'react';
import {
  Wand2, Sparkles, ThumbsUp, ThumbsDown, Download, FileDown, Loader2,
  CheckCircle2, RotateCcw, Lightbulb, FileText, ImagePlus, X, ChevronDown,
  ZoomIn, ZoomOut, Maximize, Eye, Table2,
} from 'lucide-react';
import PrimitivePicker from '@/components/PrimitivePicker';
import PatentFigure3D from '@/components/PatentFigure3D';
import { buildParamDoc, exportFigureAsPng } from '@/components/PatentFigure';
import ParamDoc, { paramDocToMarkdown, downloadText } from '@/components/ParamDoc';
import { matchPrimitives, PROMPT_TEMPLATES } from '@/lib/match';
import { getPrimitive } from '@/data/primitives';
import { useStore } from '@/store/AppStore';
import type { GeneratedResult } from '@/types';

const GEN_STAGES_BASE = ['语义理解：解析构件与装配关系', '图元匹配：向量检索图元库', '形成框架：布局骨架与标记编号', '组装成图：参数化实例化装配', '生成参数文档：尺寸/材料/关系'];

export default function TextToImage() {
  const { addFeedback, addTokens } = useStore();
  const [prompt, setPrompt] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(true);
  const [docFile, setDocFile] = useState<string | null>(null);
  const [refImg, setRefImg] = useState<{ name: string; url: string } | null>(null);
  const [stage, setStage] = useState(-1);
  const [stages, setStages] = useState(GEN_STAGES_BASE);
  const [result, setResult] = useState<GeneratedResult | null>(null);
  const [fbSent, setFbSent] = useState<'up' | 'down' | null>(null);
  const [tab, setTab] = useState<'figure' | 'doc'>('figure');
  const [zoom, setZoom] = useState(1);
  const figRef = useRef<HTMLDivElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  const generating = stage >= 0 && stage < stages.length;

  const generate = () => {
    if ((!prompt.trim() && !docFile) || generating) return;
    const effPrompt = prompt.trim() || `基于上传文档《${docFile}》解析生成`;
    setResult(null);
    setFbSent(null);
    setTab('figure');
    setZoom(1);
    const st = docFile ? ['文档解析：抽取权利要求技术特征', ...GEN_STAGES_BASE] : GEN_STAGES_BASE;
    setStages(st);
    setStage(0);
    addTokens('文生图', 7100);
    addTokens('参数文档', 1200);
    if (docFile) addTokens('数据解析', 3200);
    const finalIds = picked.length > 0 ? ['prm-0604', ...picked.filter((x) => x !== 'prm-0604')].slice(0, 9) : matchPrimitives(effPrompt);
    let s = 0;
    timer.current = setInterval(() => {
      s += 1;
      setStage(s);
      if (s >= st.length) {
        if (timer.current) clearInterval(timer.current);
        setResult({
          id: `G-${Date.now()}`,
          version: 1,
          prompt: effPrompt,
          primitiveIds: finalIds,
          docRows: buildParamDoc(finalIds),
          createdAt: new Date().toLocaleString('zh-CN', { hour12: false }),
        });
      }
    }, 950);
  };

  const sendFeedback = (t: 'up' | 'down') => {
    if (!result || fbSent) return;
    setFbSent(t);
    addFeedback({
      id: `FB-${Math.floor(1000 + Math.random() * 9000)}`,
      feature: '文生图',
      contentTitle: `文生图结果 · ${result.id.slice(-6)}`,
      contentSnapshot: `描述：“${result.prompt.slice(0, 40)}${result.prompt.length > 40 ? '…' : ''}”｜图元 ${result.primitiveIds.length} 个（${result.primitiveIds.map((i) => getPrimitive(i)?.name).slice(0, 3).join('、')}等）`,
      feedbackType: t === 'up' ? '点赞' : '点踩',
      feedbackText: t === 'up' ? '用户对生成结果满意' : '用户对生成结果不满意（待补充具体意见）',
      user: 'current_user',
      createdAt: new Date().toLocaleString('zh-CN', { hour12: false }),
      status: '待处理',
    });
  };

  const exportPng = () => {
    const svg = figRef.current?.querySelector('svg');
    if (svg) exportFigureAsPng(svg as SVGSVGElement, `专利附图_${result?.id ?? 'export'}.png`);
  };

  const onDocPick = (files: FileList | null) => {
    if (files && files[0]) setDocFile(files[0].name);
  };
  const onImgPick = (files: FileList | null) => {
    if (files && files[0]) {
      if (refImg) URL.revokeObjectURL(refImg.url);
      setRefImg({ name: files[0].name, url: URL.createObjectURL(files[0]) });
    }
  };

  const toggle = (id: string) => setPicked((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const zoomBy = (d: number) => setZoom((z) => Math.min(2.5, Math.max(0.5, Math.round((z + d) * 10) / 10)));

  return (
    <div className="grid min-h-full grid-cols-1 gap-0 lg:grid-cols-[400px_1fr]">
      {/* 左侧输入区 */}
      <div className="border-b border-slate-200 p-5 lg:border-b-0 lg:border-r">
        <h1 className="flex items-center gap-2 text-base font-semibold text-slate-800">
          <Wand2 className="h-4.5 w-4.5 text-violet-600" /> 文生图
        </h1>
        <p className="mt-1 text-xs text-slate-500">输入技术描述或上传专利文档，系统将解析技术特征并生成三维示意附图</p>

        {/* 技术描述 */}
        <div className="mt-4">
          <div className="mb-1.5 flex items-center justify-between">
            <label className="text-xs font-medium text-slate-600">技术描述</label>
            <span className="font-mono text-[10px] text-slate-400">{prompt.length}/5000</span>
          </div>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value.slice(0, 5000))}
            rows={4}
            placeholder="请输入权利要求书、技术方案、结构描述等文本内容，系统将自动解析技术特征并生成附图…"
            className="w-full resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-700 outline-none placeholder:text-slate-400 focus:border-violet-500 focus:bg-white"
          />
          <div className="mt-2">
            <div className="mb-1 flex items-center gap-1 text-[10px] text-slate-400"><Lightbulb className="h-3 w-3 text-amber-500" />专利场景提示词模板</div>
            <div className="flex flex-wrap gap-1.5">
              {PROMPT_TEMPLATES.map((t, i) => (
                <button key={i} onClick={() => setPrompt(t)}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] text-slate-500 transition hover:border-violet-300 hover:text-violet-600">
                  模板{['一·减速传动', '二·液压夹紧', '三·直线滑台', '四·密封轴系'][i]}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 文档上传 */}
        <div className="mt-4">
          <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-slate-600">
            <FileText className="h-3.5 w-3.5 text-violet-600" /> 文档上传
            <span className="font-normal text-slate-400">（Word/PDF/XML，≤20MB）</span>
          </label>
          <input ref={docInputRef} type="file" accept=".doc,.docx,.pdf,.xml" className="hidden" onChange={(e) => onDocPick(e.target.files)} />
          {docFile ? (
            <div className="flex items-center gap-2 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2.5">
              <FileText className="h-4 w-4 shrink-0 text-violet-600" />
              <span className="min-w-0 flex-1 truncate text-xs text-slate-700">{docFile}</span>
              <span className="rounded bg-violet-100 px-1.5 py-0.5 text-[10px] text-violet-600">待解析</span>
              <button onClick={() => setDocFile(null)} className="rounded p-0.5 text-slate-400 hover:text-rose-500"><X className="h-3.5 w-3.5" /></button>
            </div>
          ) : (
            <button onClick={() => docInputRef.current?.click()}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 py-3 text-xs text-slate-500 transition hover:border-violet-300 hover:bg-violet-50 hover:text-violet-600">
              <FileText className="h-4 w-4" /> 点击上传专利文档
            </button>
          )}
        </div>

        {/* 参考图片 */}
        <div className="mt-4">
          <label className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-slate-600">
            <ImagePlus className="h-3.5 w-3.5 text-violet-600" /> 参考图片
            <span className="font-normal text-slate-400">（JPG/PNG/SVG，≤10MB）</span>
          </label>
          <input ref={imgInputRef} type="file" accept=".jpg,.jpeg,.png,.svg" className="hidden" onChange={(e) => onImgPick(e.target.files)} />
          {refImg ? (
            <div className="flex items-center gap-3 rounded-lg border border-violet-200 bg-violet-50 p-2.5">
              <img src={refImg.url} alt="参考图片" className="h-14 w-14 rounded-md border border-slate-200 bg-white object-contain" />
              <span className="min-w-0 flex-1 truncate text-xs text-slate-700">{refImg.name}</span>
              <button onClick={() => { URL.revokeObjectURL(refImg.url); setRefImg(null); }} className="rounded p-0.5 text-slate-400 hover:text-rose-500"><X className="h-3.5 w-3.5" /></button>
            </div>
          ) : (
            <button onClick={() => imgInputRef.current?.click()}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 py-3 text-xs text-slate-500 transition hover:border-violet-300 hover:bg-violet-50 hover:text-violet-600">
              <ImagePlus className="h-4 w-4" /> 上传参考图片
            </button>
          )}
        </div>

        {/* 核心图元（可收起展开） */}
        <div className="mt-4">
          <button onClick={() => setPickerOpen(!pickerOpen)} className="mb-1.5 flex w-full items-center gap-1.5 text-left">
            <span className="text-xs font-medium text-slate-600">核心图元</span>
            <span className="text-[10px] font-normal text-slate-400">（可选，{picked.length} 已选）</span>
            <span className="ml-auto flex items-center gap-2">
              {picked.length > 0 && (
                <span onClick={(e) => { e.stopPropagation(); setPicked([]); }} className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-violet-600">
                  <RotateCcw className="h-3 w-3" />清空
                </span>
              )}
              <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${pickerOpen ? '' : '-rotate-90'}`} />
            </span>
          </button>
          {pickerOpen && (
            <>
              <PrimitivePicker selected={picked} onToggle={toggle} maxHeight="max-h-[260px]" />
              <p className="mt-1.5 text-[10px] leading-relaxed text-slate-400">
                不勾选时由语义理解节点自动匹配；勾选后将以所选图元为约束进行组装。
              </p>
            </>
          )}
        </div>

        <button
          onClick={generate}
          disabled={(!prompt.trim() && !docFile) || generating}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-rose-800 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-500/20 transition hover:opacity-90 disabled:opacity-40"
        >
          {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {generating ? '生成中…' : '生成附图'}
        </button>
      </div>

      {/* 右侧结果面板 */}
      <div className="flex min-w-0 flex-col">
        {/* Tab 栏 */}
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-5 pt-3">
          <div className="flex gap-1">
            {([['figure', Eye, '附图预览'], ['doc', Table2, '参数文档']] as const).map(([v, Icon, label]) => (
              <button key={v} onClick={() => setTab(v)}
                className={`flex items-center gap-1.5 border-b-2 px-3 pb-2.5 pt-1 text-xs font-medium transition ${
                  tab === v ? 'border-violet-600 text-violet-700' : 'border-transparent text-slate-400 hover:text-slate-600'
                }`}>
                <Icon className="h-3.5 w-3.5" />{label}
              </button>
            ))}
          </div>

          {/* 缩放控制（仅附图页） */}
          {tab === 'figure' && result && !generating && (
            <div className="ml-2 flex items-center gap-1 pb-2">
              <button onClick={() => zoomBy(-0.2)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"><ZoomOut className="h-3.5 w-3.5" /></button>
              <span className="w-10 text-center font-mono text-[11px] text-slate-500">{Math.round(zoom * 100)}%</span>
              <button onClick={() => zoomBy(0.2)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"><ZoomIn className="h-3.5 w-3.5" /></button>
              <button onClick={() => setZoom(1)} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="适应画布"><Maximize className="h-3.5 w-3.5" /></button>
            </div>
          )}

          <div className="ml-auto flex items-center gap-1.5 pb-2">
            {result && !generating && (
              <>
                <button onClick={() => sendFeedback('up')}
                  className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs transition ${fbSent === 'up' ? 'border-emerald-300 bg-emerald-50 text-emerald-600' : 'border-slate-200 text-slate-500 hover:border-emerald-300 hover:text-emerald-600'}`}>
                  <ThumbsUp className="h-3.5 w-3.5" />{fbSent === 'up' ? '已赞' : '满意'}
                </button>
                <button onClick={() => sendFeedback('down')}
                  className={`flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs transition ${fbSent === 'down' ? 'border-rose-300 bg-rose-50 text-rose-600' : 'border-slate-200 text-slate-500 hover:border-rose-300 hover:text-rose-600'}`}>
                  <ThumbsDown className="h-3.5 w-3.5" />{fbSent === 'down' ? '已踩' : '不满意'}
                </button>
                <span className="mx-1 h-4 w-px bg-slate-200" />
                {tab === 'figure' ? (
                  <button onClick={exportPng} className="flex items-center gap-1 rounded-lg bg-violet-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-violet-500">
                    <Download className="h-3.5 w-3.5" />导出PNG
                  </button>
                ) : (
                  <button onClick={() => downloadText(`参数文档_${result.id}.md`, paramDocToMarkdown(result.docRows, '制图参数文档', result.prompt))}
                    className="flex items-center gap-1 rounded-lg bg-violet-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-violet-500">
                    <FileDown className="h-3.5 w-3.5" />导出参数文档
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Tab 内容 */}
        <div className="min-h-0 flex-1 overflow-auto p-5">
          {!result && !generating && (
            <div className="flex h-full min-h-[380px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 text-center">
              {tab === 'figure' ? <Eye className="h-10 w-10 text-slate-300" /> : <Table2 className="h-10 w-10 text-slate-300" />}
              <div className="mt-3 text-sm text-slate-500">
                {tab === 'figure' ? '在左侧输入技术描述并点击"生成附图"' : '生成后可在此查看制图参数文档'}
              </div>
              <div className="mt-1 text-xs text-slate-400">
                {tab === 'figure' ? '系统将在此处展示生成的三维示意附图' : '包含附图标记、构件参数、材料与装配关系'}
              </div>
            </div>
          )}

          {generating && (
            <div className="flex h-full min-h-[380px] flex-col items-center justify-center">
              <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Loader2 className="h-4 w-4 animate-spin text-violet-600" /> 文生图流水线运行中
                </div>
                <ol className="space-y-2.5">
                  {stages.map((s, i) => (
                    <li key={s} className={`flex items-center gap-2.5 text-xs transition ${i < stage ? 'text-slate-500' : i === stage ? 'text-violet-700' : 'text-slate-300'}`}>
                      {i < stage ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : i === stage ? <Loader2 className="h-4 w-4 animate-spin text-violet-600" /> : <span className="h-4 w-4 rounded-full border border-slate-200" />}
                      {s}
                    </li>
                  ))}
                </ol>
                <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full bg-gradient-to-r from-violet-600 to-rose-800 transition-all duration-500" style={{ width: `${(stage / stages.length) * 100}%` }} />
                </div>
              </div>
            </div>
          )}

          {result && !generating && tab === 'figure' && (
            <div className="flex h-full flex-col">
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded-full bg-violet-100 px-3 py-1 text-xs font-medium text-violet-700">生成结果 V{result.version}</span>
                <span className="text-[11px] text-slate-400">{result.createdAt}</span>
                {refImg && <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">已参考：{refImg.name}</span>}
              </div>
              <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm">
                <div ref={figRef} style={{ transform: `scale(${zoom})`, transformOrigin: 'top left', width: `${100 / zoom}%` }}>
                  <PatentFigure3D primitiveIds={result.primitiveIds} seedKey={result.id} />
                </div>
              </div>
              {fbSent && (
                <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                  感谢反馈！该反馈已与本次生成内容成对记录至管理端「反馈通道」。
                </div>
              )}
            </div>
          )}

          {result && !generating && tab === 'doc' && (
            <div>
              <div className="mb-2 flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-700">制图参数文档</h2>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">DOC-{result.id.slice(-6)}</span>
                <span className="text-[11px] text-slate-400">{result.createdAt}</span>
              </div>
              <ParamDoc rows={result.docRows} />
              {fbSent && (
                <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                  感谢反馈！该反馈已与本次生成内容成对记录至管理端「反馈通道」。
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
