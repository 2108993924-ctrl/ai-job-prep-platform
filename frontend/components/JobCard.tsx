// ============================================================
// 岗位卡片组件（公司详情页 / 搜索页列表使用）
// 展示岗位标题、公司、类型、地点、薪资、技术栈标签
// ============================================================

import Link from "next/link";
import type { Job } from "@/lib/types";

// 岗位类型徽章配色
const JOB_TYPE_STYLE: Record<string, string> = {
  "AI算法": "bg-purple-100 text-purple-700",
  "AI工程": "bg-blue-100 text-blue-700",
  "AI产品": "bg-amber-100 text-amber-700",
  "AI应用": "bg-emerald-100 text-emerald-700",
  "数据科学": "bg-cyan-100 text-cyan-700",
};

export default function JobCard({ job }: { job: Job }) {
  // 展示前 3 个技术栈标签（技术栈过多时截断）
  const techTags = (job.tech_stack ?? []).slice(0, 3);

  return (
    <Link
      href={`/jobs?id=${encodeURIComponent(job.job_id)}`}
      className="block rounded-xl border border-slate-200 bg-white p-5 transition hover:border-brand-400 hover:shadow-md"
    >
      {/* 第一行：岗位名 + 类型徽章 + 公司 */}
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-bold text-slate-800 hover:text-brand-600">{job.job_title}</h3>
        {job.job_type && (
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              JOB_TYPE_STYLE[job.job_type] ?? "bg-slate-100 text-slate-600"
            }`}
          >
            {job.job_type}
          </span>
        )}
        <span className="text-xs text-slate-400">{job.company}</span>
      </div>

      {/* 第二行：地点 / 薪资 / 发布时间 */}
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        {job.location && <span>📍 {job.location}</span>}
        {job.salary_range && <span className="font-medium text-emerald-600">💰 {job.salary_range}</span>}
        {job.publish_date && <span>📅 {job.publish_date}</span>}
        {/* 结构化完成标记（体现 AI 备考价值） */}
        {job.enriched_at && (
          <span className="rounded bg-brand-50 px-1.5 py-0.5 text-brand-600">已生成备考内容</span>
        )}
      </div>

      {/* 第三行：技术栈标签 */}
      {techTags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {techTags.map((tag) => (
            <span
              key={tag}
              className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
            >
              {tag}
            </span>
          ))}
          {(job.tech_stack ?? []).length > 3 && (
            <span className="px-1 text-xs text-slate-400">
              +{(job.tech_stack ?? []).length - 3} 项
            </span>
          )}
        </div>
      )}
    </Link>
  );
}
