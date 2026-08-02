// ============================================================
// 公司卡片组件（首页网格使用）
// 展示公司名、类别、AI 岗位数与最近抓取时间
// ============================================================

import Link from "next/link";
import type { CompanyStats } from "@/lib/types";

// 公司类别徽章配色（不同类别不同颜色便于区分）
const CATEGORY_STYLE: Record<string, string> = {
  "互联网大厂": "bg-blue-100 text-blue-700",
  "大模型独角兽": "bg-purple-100 text-purple-700",
  "AI垂直龙头": "bg-emerald-100 text-emerald-700",
  "国企AI": "bg-amber-100 text-amber-700",
};

export default function CompanyCard({ stats }: { stats: CompanyStats }) {
  // 徽章样式：未知类别使用默认灰色
  const badgeStyle = CATEGORY_STYLE[stats.company_category] ?? "bg-slate-100 text-slate-600";

  return (
    <Link
      href={`/company?name=${encodeURIComponent(stats.company)}`}
      className="group rounded-xl border border-slate-200 bg-white p-5 transition hover:border-brand-400 hover:shadow-md"
    >
      {/* 公司名与类别徽章 */}
      <div className="flex items-center justify-between gap-2">
        <h3 className="truncate text-lg font-bold text-slate-800 group-hover:text-brand-600">
          {stats.company}
        </h3>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeStyle}`}>
          {stats.company_category}
        </span>
      </div>

      {/* 岗位统计 */}
      <div className="mt-4 flex items-end justify-between">
        <div>
          <p className="text-3xl font-bold text-brand-600">{stats.job_count}</p>
          <p className="text-xs text-slate-400">个 AI 岗位</p>
        </div>
        <div className="text-right text-xs text-slate-400">
          <p>算法岗 {stats.ai_algo_count}</p>
          {stats.last_crawl && (
            <p className="mt-1">更新于 {new Date(stats.last_crawl).toLocaleDateString("zh-CN")}</p>
          )}
        </div>
      </div>
    </Link>
  );
}
