// ============================================================
// 搜索页：/search?q=关键词
// 按技术栈 / 岗位名 / JD 内容跨公司检索（RAG、LoRA、多模态...）
// 使用 Supabase ilike 模糊查询（配合数据库 pg_trgm 索引）
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { fetchAllJobs } from "@/lib/data";
import type { Job } from "@/lib/types";
import JobCard from "@/components/JobCard";

export default function SearchPage() {
  // 搜索关键词（从 URL ?q= 读取）
  const [keyword, setKeyword] = useState("");
  // 输入框当前值（允许用户修改后再次搜索）
  const [input, setInput] = useState("");
  // 搜索结果
  const [results, setResults] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  // 首次渲染：解析 URL 参数并搜索
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q") || "";
    if (q) {
      setKeyword(q);
      setInput(q);
      doSearch(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 执行搜索：技术栈 / 岗位名 / 公司名 / JD 原文 四路命中
  // 统一数据层：Supabase 未配置时自动降级为本地静态 JSON + 前端过滤
  async function doSearch(q: string) {
    const query = q.trim().toLowerCase();
    if (!query) return;
    setLoading(true);
    setSearched(true);

    const all = await fetchAllJobs();
    const matched = all.filter((j) => {
      if ((j.job_title ?? "").toLowerCase().includes(query)) return true;
      if ((j.company ?? "").toLowerCase().includes(query)) return true;
      if ((j.tech_stack ?? []).some((t) => t.toLowerCase().includes(query))) return true;
      if ((j.business_domain ?? []).some((d) => d.toLowerCase().includes(query))) return true;
      if ((j.jd_raw_text ?? "").toLowerCase().includes(query)) return true;
      return false;
    });
    setResults(matched.slice(0, 50));
    setLoading(false);
  }

  // 表单提交：跳转 URL（便于分享链接）并搜索
  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q) return;
    setKeyword(q);
    // 更新地址栏 URL（不刷新页面）
    window.history.pushState({}, "", `/search?q=${encodeURIComponent(q)}`);
    doSearch(q);
  }

  return (
    <div>
      {/* ===== 搜索框 ===== */}
      <h1 className="mb-4 text-xl font-bold">技术栈搜索</h1>
      <form onSubmit={onSubmit} className="mb-6 flex max-w-2xl gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入技术栈 / 关键词，如 RAG、LoRA、多模态、PyTorch、Agent"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
        />
        <button
          type="submit"
          className="rounded-lg bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
        >
          搜索
        </button>
      </form>

      {/* ===== 常用技术栈快捷标签 ===== */}
      <div className="mb-6 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-slate-400">热门：</span>
        {["RAG", "LoRA", "多模态", "PyTorch", "Agent", "向量数据库", "Transformer", "推荐系统"].map((tag) => (
          <button
            key={tag}
            onClick={() => {
              setInput(tag);
              setKeyword(tag);
              window.history.pushState({}, "", `/search?q=${encodeURIComponent(tag)}`);
              doSearch(tag);
            }}
            className={`rounded-full px-3 py-1 ${
              keyword === tag
                ? "bg-brand-600 text-white"
                : "border border-slate-300 bg-white text-slate-600 hover:border-brand-400 hover:text-brand-600"
            }`}
          >
            {tag}
          </button>
        ))}
      </div>

      {/* ===== 搜索结果 ===== */}
      {searched && !loading && (
        <p className="mb-4 text-sm text-slate-500">
          「{keyword}」共找到 <span className="font-semibold text-brand-600">{results.length}</span> 个岗位
        </p>
      )}

      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-200" />
          ))}
        </div>
      )}

      {searched && !loading && results.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">
          没有找到包含「{keyword}」的岗位，试试其他关键词？
        </div>
      )}

      <div className="space-y-3">
        {results.map((job) => (
          <JobCard key={job.job_id} job={job} />
        ))}
      </div>
    </div>
  );
}
