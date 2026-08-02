// ============================================================
// 备考面板（JD 详情页右侧核心组件）
//
// 三个板块：
//   1. 项目能力要求 —— 候选人应能独立完成的具体项目
//   2. 技术栈清单 —— 需要掌握的技术/框架/算法
//   3. 5 道针对性面试题（按 5 大维度）与参考答案
//
// 数据来自 enrich_jd() 的结构化结果；未结构化时显示提示。
// ============================================================

"use client";

import { useState } from "react";
import type { Job } from "@/lib/types";

// 面试题维度徽章配色
const CATEGORY_STYLE: Record<string, string> = {
  基础原理: "bg-blue-100 text-blue-700",
  大模型应用: "bg-purple-100 text-purple-700",
  工程实现: "bg-emerald-100 text-emerald-700",
  生产调优: "bg-amber-100 text-amber-700",
  场景判断: "bg-rose-100 text-rose-700",
};

export default function InterviewPanel({ job }: { job: Job }) {
  // 每题展开/收起参考答案（默认全部收起）
  const [openAnswers, setOpenAnswers] = useState<Set<number>>(new Set());

  // 是否有结构化内容（新爬取的岗位可能还没跑 LLM）
  const hasEnrichment =
    (job.project_requirements?.length ?? 0) > 0 ||
    (job.tech_stack?.length ?? 0) > 0 ||
    (job.interview_questions?.length ?? 0) > 0;

  // 切换某道题的参考答案显示状态
  function toggleAnswer(idx: number) {
    setOpenAnswers((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  // ===== 未结构化时的占位提示 =====
  if (!hasEnrichment) {
    return (
      <aside className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-lg font-bold text-slate-700">备考内容生成中</p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          该岗位刚被收录，AI 结构化（项目能力要求 / 技术栈 / 面试题）将在下次定时任务中生成。
          <br />
          可在本地手动执行：<code className="rounded bg-slate-100 px-1">python backend/main.py --enrich-only</code>
        </p>
      </aside>
    );
  }

  return (
    <aside className="space-y-6">
      {/* ========== 板块一：项目能力要求 ========== */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-bold text-slate-800">🎯 项目能力要求</h2>
        {(job.project_requirements ?? []).length === 0 ? (
          <p className="text-sm text-slate-400">JD 中未识别出明确的独立项目要求</p>
        ) : (
          <ol className="space-y-3">
            {job.project_requirements.map((req, idx) => (
              <li key={idx} className="flex gap-3 text-sm leading-6 text-slate-600">
                {/* 序号圆点 */}
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-600">
                  {idx + 1}
                </span>
                {req}
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* ========== 板块二：技术栈清单 ========== */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-bold text-slate-800">🧰 技术栈清单</h2>
        {(job.tech_stack ?? []).length === 0 ? (
          <p className="text-sm text-slate-400">JD 中未识别出明确的技术栈</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {job.tech_stack.map((tech) => (
              <span
                key={tech}
                className="rounded-lg border border-brand-100 bg-brand-50 px-3 py-1.5 text-sm text-brand-700"
              >
                {tech}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* ========== 板块三：面试题（核心）========== */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-1 text-lg font-bold text-slate-800">📝 针对性面试题</h2>
        <p className="mb-4 text-xs text-slate-400">
          共 {job.interview_questions?.length ?? 0} 题，覆盖基础原理 / 大模型应用 / 工程实现 / 生产调优 / 场景判断
        </p>

        {(job.interview_questions ?? []).length === 0 ? (
          <p className="text-sm text-slate-400">暂未生成面试题</p>
        ) : (
          <ol className="space-y-3">
            {job.interview_questions.map((q, idx) => (
              <li key={idx} className="rounded-lg border border-slate-100 bg-slate-50/50 p-4">
                {/* 题目行（点击展开答案） */}
                <button
                  onClick={() => toggleAnswer(idx)}
                  className="flex w-full items-start gap-3 text-left"
                >
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600">
                    {idx + 1}
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-medium leading-6 text-slate-700">
                      {q.question}
                    </span>
                    {/* 维度徽章 */}
                    <span
                      className={`mt-1.5 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        CATEGORY_STYLE[q.category] ?? "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {q.category}
                    </span>
                  </span>
                  {/* 展开箭头 */}
                  <span className={`mt-1 text-xs text-slate-400 transition-transform ${openAnswers.has(idx) ? "rotate-180" : ""}`}>
                    ▼
                  </span>
                </button>

                {/* 参考答案（点击题目展开/收起） */}
                {openAnswers.has(idx) && (
                  <div className="mt-3 rounded-lg border-l-2 border-brand-500 bg-white p-4">
                    <p className="mb-1 text-xs font-semibold text-brand-600">参考答案要点</p>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-slate-600">
                      {q.reference_answer || "（该题未生成参考答案）"}
                    </p>
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </aside>
  );
}
