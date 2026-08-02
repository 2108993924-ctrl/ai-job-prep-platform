// ============================================================
// 首页：公司卡片网格
// 展示各公司 AI 岗位数量统计，点击进入公司详情页。
// 数据来源：Supabase company_stats 视图（构建时 + 浏览器端拉取）
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { fetchCompanyStats } from "@/lib/data";
import type { CompanyStats } from "@/lib/types";
import CompanyCard from "@/components/CompanyCard";

export default function HomePage() {
  // 公司统计列表
  const [stats, setStats] = useState<CompanyStats[]>([]);
  // 加载状态（首屏骨架屏）
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 统一数据层：Supabase 优先，未配置时自动降级到本地静态数据
    async function loadStats() {
      const stats = await fetchCompanyStats();
      setStats(stats);
      setLoading(false);
    }
    loadStats();
  }, []);

  return (
    <div>
      {/* ===== 顶部横幅 ===== */}
      <section className="mb-8 rounded-2xl bg-gradient-to-r from-brand-600 to-indigo-600 px-8 py-10 text-white">
        <h1 className="text-3xl font-bold">AI 岗位备考平台</h1>
        <p className="mt-3 max-w-2xl text-brand-50">
          聚合各企业官方招聘页公开的 AI 岗位要求，用 AI 解析出
          「项目能力要求 / 技术栈 / 针对性面试题」，帮你明确方向、从零备考。
        </p>
        {/* 搜索入口 */}
        <div className="mt-6 flex max-w-xl gap-2">
          <form action="/search" className="flex flex-1 gap-2">
            <input
              name="q"
              placeholder="搜索技术栈，如 RAG / LoRA / 多模态 / PyTorch"
              className="flex-1 rounded-lg border-0 px-4 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-white"
            />
            <button
              type="submit"
              className="rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-brand-600 hover:bg-brand-50"
            >
              搜索
            </button>
          </form>
        </div>
      </section>

      {/* ===== 公司卡片网格 ===== */}
      <section>
        <h2 className="mb-4 text-xl font-bold text-slate-800">入驻公司</h2>

        {/* 加载中骨架屏 */}
        {loading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-40 animate-pulse rounded-xl bg-slate-200" />
            ))}
          </div>
        )}

        {/* 空数据提示（本地还没有爬取数据） */}
        {!loading && stats.length === 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            <p className="font-semibold text-slate-700">暂无数据</p>
            <p className="mt-1">
              请先在本地运行爬虫（<code>python backend/main.py</code>）写入数据，
              然后运行 <code>python backend/export_frontend_data.py</code> 刷新本页。
            </p>
          </div>
        )}

        {/* 公司卡片网格 */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {stats.map((s) => (
            <CompanyCard key={s.company} stats={s} />
          ))}
        </div>
      </section>

      {/* ===== 备考指引（新手友好说明）===== */}
      <section className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { title: "① 看公司", desc: "浏览各企业 AI 岗位数量，了解哪些公司、哪些方向在招人" },
          { title: "② 看 JD", desc: "查看 JD 原文与 AI 解析出的项目能力要求、技术栈清单" },
          { title: "③ 练面试", desc: "按 5 大维度针对性面试题逐题准备，明确提升方向" },
        ].map((step) => (
          <div key={step.title} className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="font-bold text-brand-600">{step.title}</h3>
            <p className="mt-2 text-sm text-slate-500">{step.desc}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
