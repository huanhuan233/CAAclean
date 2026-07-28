import { useState } from 'react';
import {
  DraftingCompass, Database, FolderTree, Layers, Workflow, Cpu, BarChart3, MessageSquareHeart,
  Wand2, SquareDashedMousePointer, Boxes, ShieldCheck, UserRound, ChevronRight,
} from 'lucide-react';
import { AppStoreProvider } from '@/store/AppStore';
import DataGovernance from '@/pages/admin/DataGovernance';
import LibraryManager from '@/pages/admin/LibraryManager';
import DatasetManager from '@/pages/admin/DatasetManager';
import PipelineManager from '@/pages/admin/PipelineManager';
import ModelHub from '@/pages/admin/ModelHub';
import Dashboard from '@/pages/admin/Dashboard';
import FeedbackChannel from '@/pages/admin/FeedbackChannel';
import TextToImage from '@/pages/user/TextToImage';
import ImageToImage from '@/pages/user/ImageToImage';

type Portal = 'user' | 'admin';

const USER_PAGES = [
  { id: 't2i', name: '文生图', icon: Wand2, desc: '自然语言生成专利附图' },
  { id: 'i2i', name: '图改图', icon: SquareDashedMousePointer, desc: '框选区域局部修改' },
];

const ADMIN_PAGES = [
  { id: 'gov', name: '图元数据治理', icon: Database, desc: '上传 · 解析 · 输出' },
  { id: 'lib', name: '图元库存储管理', icon: FolderTree, desc: '目录层级 · 元数据 CRUD' },
  { id: 'dataset', name: '数据集管理', icon: Layers, desc: '四类训练数据集' },
  { id: 'pipeline', name: '节点流程管理', icon: Workflow, desc: '三条业务流水线' },
  { id: 'model', name: '模型 API 接入', icon: Cpu, desc: '节点级模型切换' },
  { id: 'dash', name: '数据看板', icon: BarChart3, desc: 'Token 消耗统计' },
  { id: 'fb', name: '反馈通道', icon: MessageSquareHeart, desc: '内容-反馈成对记录' },
];

function Shell() {
  const [portal, setPortal] = useState<Portal>('user');
  const [page, setPage] = useState('t2i');

  const pages = portal === 'user' ? USER_PAGES : ADMIN_PAGES;
  const current = pages.find((p) => p.id === page) ?? pages[0];

  const switchPortal = (p: Portal) => {
    setPortal(p);
    setPage(p === 'user' ? 't2i' : 'gov');
  };

  return (
    <div className="flex h-screen flex-col bg-[#f3f4f6] text-slate-700">
      {/* 顶栏 */}
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-slate-200 bg-white/90 px-4 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/20">
            <DraftingCompass className="h-4.5 w-4.5" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight text-slate-800">专利附图智能生成系统</div>
            <div className="text-[10px] leading-tight text-slate-500">基于参数化图元库 · Parametric Primitive Engine</div>
          </div>
        </div>

        {/* 门户切换 */}
        <div className="mx-auto flex items-center rounded-full border border-slate-200 bg-slate-100 p-1">
          {(['user', 'admin'] as Portal[]).map((p) => (
            <button
              key={p}
              onClick={() => switchPortal(p)}
              className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition ${
                portal === p ? 'bg-violet-600 text-white shadow shadow-violet-500/20' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {p === 'user' ? <UserRound className="h-3.5 w-3.5" /> : <ShieldCheck className="h-3.5 w-3.5" />}
              {p === 'user' ? '用户端' : '管理端 · AI 基础设施'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="hidden items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-emerald-600 md:flex">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
            引擎在线
          </span>
          <span className="hidden md:inline">v1.2.0</span>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* 侧栏 */}
        <aside className="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            {portal === 'user' ? '创作工作台' : 'AI 基础设施'}
          </div>
          <nav className="space-y-1">
            {pages.map((p) => (
              <button
                key={p.id}
                onClick={() => setPage(p.id)}
                className={`group flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition ${
                  page === p.id
                    ? 'bg-violet-100 text-violet-700 ring-1 ring-inset ring-violet-200'
                    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'
                }`}
              >
                <p.icon className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium">{p.name}</span>
                  <span className="block truncate text-[10px] text-slate-400">{p.desc}</span>
                </span>
                {page === p.id && <ChevronRight className="h-3.5 w-3.5 text-violet-600" />}
              </button>
            ))}
          </nav>

          <div className="mt-auto rounded-lg border border-slate-200 bg-white p-3">
            <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-slate-600">
              <Boxes className="h-3.5 w-3.5 text-violet-600" /> 图元库概况
            </div>
            <div className="text-[10px] leading-relaxed text-slate-500">
              7 大目录 · 29 个参数化图元
              <br />覆盖机械结构类专利场景
            </div>
          </div>
        </aside>

        {/* 主内容 */}
        <main className="min-w-0 flex-1 overflow-auto">
          {page === 't2i' && <TextToImage />}
          {page === 'i2i' && <ImageToImage />}
          {page === 'gov' && <DataGovernance />}
          {page === 'lib' && <LibraryManager />}
          {page === 'dataset' && <DatasetManager />}
          {page === 'pipeline' && <PipelineManager />}
          {page === 'model' && <ModelHub />}
          {page === 'dash' && <Dashboard />}
          {page === 'fb' && <FeedbackChannel />}
          {current && false}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AppStoreProvider>
      <Shell />
    </AppStoreProvider>
  );
}
