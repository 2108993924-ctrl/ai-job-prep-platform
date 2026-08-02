// ============================================================
// JD 详情页：/jobs?id=job_id
// 左侧：JD 原文；右侧：备考面板
// （项目能力要求 / 技术栈清单 / 5 道面试题及参考答案）
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAllJobs } from "@/lib/data";
import type { Job } from "@/lib/types";
import InterviewPanel from "@/components/InterviewPanel";

export default function JobDetailPage() {
  // 岗位数据与加载状态
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);

  // 首次渲染后从 URL 读取 job_id 并拉取数据（统一数据层自动降级静态 JSON）
  useEffect(() => {
    const jobId = new URLSearchParams(window.location.search).get("id") || "";
    if (!jobId) {
      setLoading(false);
      return;
    }
    fetchAllJobs().then((all) => {
      setJob(all.find((j) => j.job_id === jobId) ?? null);
      setLoading(false);
    });
  }, []);

  // 加载中骨架屏
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="h-96 animate-pulse rounded-xl bg-slate-200" />
        <div className="h-96 animate-pulse rounded-xl bg-slate-200" />
      </div>
    );
  }

  // 岗位不存在提示
  if (!job) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">
        未找到该岗位（可能已下架），
        <Link href="/" className="text-brand-600 hover:underline">返回首页</Link>
      </div>
    );
  }

  return (
    <div>
      {/* ===== 页面头部：岗位标题与基本信息 ===== */}
      <div className="mb-6">
        <Link
          href={`/company?name=${encodeURIComponent(job.company)}`}
          className="text-sm text-slate-400 hover:text-brand-600"
        >
          ← {job.company} 全部岗位
        </Link>

        <h1 className="mt-3 text-2xl font-bold text-slate-800">{job.job_title}</h1>

        {/* 信息徽章行 */}
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-blue-100 px-3 py-1 font-medium text-blue-700">
            {job.company}
          </span>
          {job.job_type && (
            <span className="rounded-full bg-purple-100 px-3 py-1 font-medium text-purple-700">
              {job.job_type}
            </span>
          )}
          {job.location && (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">📍 {job.location}</span>
          )}
          {job.salary_range && (
            <span className="rounded-full bg-emerald-100 px-3 py-1 font-medium text-emerald-700">
              💰 {job.salary_range}
            </span>
          )}
          {job.publish_date && (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-500">📅 {job.publish_date}</span>
          )}
        </div>
      </div>

      {/* ===== 双栏布局：左原文 / 右备考面板 ===== */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* 左栏：JD 原文 */}
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-bold text-slate-800">
            JD 原文
            {job.source_url && (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded bg-brand-50 px-2 py-0.5 text-xs font-normal text-brand-600 hover:bg-brand-100"
              >
                查看官方原文 ↗
              </a>
            )}
          </h2>

          {/* 保留原文换行与段落结构 */}
          <div className="whitespace-pre-wrap text-sm leading-7 text-slate-600">
            {job.jd_raw_text}
          </div>
        </section>

        {/* 右栏：AI 备考面板 */}
        <InterviewPanel job={job} />
      </div>
    </div>
  );
}
