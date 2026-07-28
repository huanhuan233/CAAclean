import { useMemo, useState } from 'react';
import { MessageSquareHeart, ThumbsUp, ThumbsDown, MessageSquareText, ArrowLeftRight } from 'lucide-react';
import { useStore } from '@/store/AppStore';
import type { FeedbackRecord } from '@/types';

const FB_ICON: Record<FeedbackRecord['feedbackType'], React.ReactNode> = {
  点赞: <ThumbsUp className="h-3.5 w-3.5 text-emerald-600" />,
  点踩: <ThumbsDown className="h-3.5 w-3.5 text-rose-600" />,
  文字: <MessageSquareText className="h-3.5 w-3.5 text-violet-600" />,
};

const STATUS_STYLE: Record<FeedbackRecord['status'], string> = {
  待处理: 'bg-amber-500/15 text-amber-600',
  已采纳: 'bg-violet-100 text-violet-600',
  已闭环: 'bg-emerald-500/15 text-emerald-600',
};

export default function FeedbackChannel() {
  const { feedback, setFeedbackStatus } = useStore();
  const [filter, setFilter] = useState<'全部' | FeedbackRecord['feature']>('全部');

  const list = useMemo(() => feedback.filter((f) => filter === '全部' || f.feature === filter), [feedback, filter]);
  const up = feedback.filter((f) => f.feedbackType === '点赞').length;
  const down = feedback.filter((f) => f.feedbackType === '点踩').length;

  return (
    <div className="p-6">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">反馈通道</h1>
          <p className="mt-0.5 text-xs text-slate-500">「对应内容 + 反馈内容」左右成对存储，支撑数据集回流与模型迭代</p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 text-emerald-600"><ThumbsUp className="h-3.5 w-3.5" />{up}</span>
          <span className="flex items-center gap-1 text-rose-600"><ThumbsDown className="h-3.5 w-3.5" />{down}</span>
          <span className="text-slate-500">好评率 {feedback.length ? Math.round((up / (up + down || 1)) * 100) : 0}%</span>
        </div>
      </header>

      {/* 过滤 */}
      <div className="mb-4 flex gap-1.5">
        {(['全部', '文生图', '图改图', '图元解析'] as const).map((f) => (
          <button key={f} onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1.5 text-xs transition ${filter === f ? 'bg-violet-600 text-white' : 'border border-slate-200 text-slate-500 hover:border-slate-500'}`}>
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {list.map((f) => (
          <div key={f.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">{f.feature}</span>
              <span className="text-sm font-medium text-slate-800">{f.contentTitle}</span>
              <span className="font-mono text-[10px] text-slate-400">{f.id}</span>
              <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] ${STATUS_STYLE[f.status]}`}>{f.status}</span>
            </div>

            {/* 左右成对 */}
            <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_1fr]">
              {/* 左：对应内容 */}
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="mb-1 text-[10px] font-medium tracking-wide text-slate-500">对应内容（生成/解析记录快照）</div>
                <p className="text-xs leading-relaxed text-slate-600">{f.contentSnapshot}</p>
              </div>
              <div className="hidden items-center md:flex">
                <ArrowLeftRight className="h-4 w-4 text-slate-400" />
              </div>
              {/* 右：反馈内容 */}
              <div className="rounded-lg border border-slate-200 bg-slate-100 p-3">
                <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium tracking-wide text-slate-500">
                  {FB_ICON[f.feedbackType]} 反馈内容 · {f.feedbackType}
                </div>
                <p className="text-xs leading-relaxed text-slate-700">{f.feedbackText}</p>
                <div className="mt-2 flex items-center gap-2 text-[10px] text-slate-400">
                  <span>{f.user}</span><span>·</span><span>{f.createdAt}</span>
                </div>
              </div>
            </div>

            {/* 处理动作 */}
            <div className="mt-3 flex justify-end gap-2">
              {(['待处理', '已采纳', '已闭环'] as const).map((s) => (
                <button key={s} onClick={() => setFeedbackStatus(f.id, s)}
                  className={`rounded-md px-2.5 py-1 text-[10px] transition ${f.status === s ? STATUS_STYLE[s] + ' ring-1 ring-current' : 'border border-slate-200 text-slate-500 hover:text-slate-600'}`}>
                  {s === '待处理' ? '标记待处理' : s === '已采纳' ? '采纳进数据集' : '标记闭环'}
                </button>
              ))}
            </div>
          </div>
        ))}
        {list.length === 0 && <div className="rounded-xl border border-dashed border-slate-200 py-12 text-center text-xs text-slate-400">暂无反馈记录</div>}
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-xl border border-dashed border-slate-200 p-3 text-[11px] leading-relaxed text-slate-500">
        <MessageSquareHeart className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" />
        用户在文生图/图改图中的点赞、点踩与文字反馈，会自动携带生成快照（描述、图元、版本）写入本通道，形成左右成对的反馈数据记录，可直接回流至数据集管理作为偏好对齐样本。
      </div>
    </div>
  );
}
