// ============================================================
// 公司详情页：/company?name=公司名
// 展示该公司所有 AI 岗位列表，支持按 job_type / tech_stack / business_domain 筛选
//
// 说明：使用查询参数而非动态路由（/company/[id]），
// 这样静态导出部署时无需在构建期依赖数据库，兼容所有静态托管。
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { fetchAllJobs } from "@/lib/data";
import type { Job } from "@/lib/types";
import JobCard from "@/components/JobCard";
import FilterPanel from "@/components/FilterPanel";

// 筛选条件结构
interface Filters {
  jobType: string;
  techStack: string;
  businessDomain: string;
}

export default function CompanyPage() {
  // 从 URL 查询参数读取公司名（?name=字节跳动）
  const [companyName, setCompanyName] = useState("");

  // 岗位列表与加载状态
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  // 筛选条件
  const [filters, setFilters] = useState<Filters>({ jobType: "", techStack: "", businessDomain: "" });

  // 首次渲染后解析 URL 参数并拉取数据（统一数据层自动降级静态 JSON）
  useEffect(() => {
    const name = new URLSearchParams(window.location.search).get("name") || "";
    setCompanyName(name);
    if (!name) {
      setLoading(false);
      return;
    }
    // 拉取该公司全部岗位（按抓取时间倒序）
    fetchAllJobs().then((all) => {
      setJobs(all.filter((j) => j.company === name));
      setLoading(false);
    });
  }, []);

  // 前端筛选：job_type 精确 / tech_stack 模糊包含 / business_domain 精确
  const filtered = useMemo(() => {
    return jobs.filter((job) => {
      if (filters.jobType && job.job_type !== filters.jobType) return false;
      if (filters.techStack && !(job.tech_stack ?? []).some((t) => t.includes(filters.techStack)))
        return false;
      if (filters.businessDomain && !(job.business_domain ?? []).includes(filters.businessDomain))
        return false;
      return true;
    });
  }, [jobs, filters]);

  // 提取全部技术栈 / 业务领域（供筛选下拉框使用）
  const allTechStacks = useMemo(() => {
    const set = new Set<string>();
    jobs.forEach((j) => (j.tech_stack ?? []).forEach((t) => set.add(t)));
    return Array.from(set);
  }, [jobs]);

  const allBusinessDomains = useMemo(() => {
    const set = new Set<string>();
    jobs.forEach((j) => (j.business_domain ?? []).forEach((d) => set.add(d)));
    return Array.from(set);
  }, [jobs]);

  const category = jobs[0]?.company_category ?? "";

  return (
    <div>
      {/* 返回链接 */}
      <Link href="/" className="mb-4 inline-block text-sm text-slate-400 hover:text-brand-600">
        ← 返回公司列表
      </Link>

      {/* ===== 公司头部 ===== */}
      <div className="mb-6 rounded-2xl bg-white p-6 shadow-sm">
        <h1 className="flex items-center gap-3 text-2xl font-bold">
          {companyName || "公司详情"}
          {category && (
            <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
              {category}
            </span>
          )}
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          共 <span className="font-semibold text-brand-600">{jobs.length}</span> 个 AI 岗位
          {filters.jobType || filters.techStack || filters.businessDomain
            ? `（筛选后 ${filtered.length} 个）`
            : ""}
        </p>
      </div>

      {/* ===== 筛选面板（按岗位类型 / 技术栈 / 业务领域）===== */}
      <FilterPanel
        filters={filters}
        onChange={setFilters}
        techStacks={allTechStacks}
        businessDomains={allBusinessDomains}
      />

      {/* ===== 岗位列表 ===== */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-200" />
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-400">
          {jobs.length === 0 ? "该公司暂无 AI 岗位数据，请先运行爬虫" : "没有符合筛选条件的岗位"}
        </div>
      )}

      <div className="space-y-3">
        {filtered.map((job) => (
          <JobCard key={job.job_id} job={job} />
        ))}
      </div>
    </div>
  );
}
