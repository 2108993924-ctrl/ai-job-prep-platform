// ============================================================
// 统一数据层：Supabase 优先，未配置时降级读取本地静态 JSON
//
// 本地静态数据由 backend/export_frontend_data.py 生成
// （python backend/export_frontend_data.py），存于 public/data/jobs.json。
// 这样本地预览 / 静态部署无需数据库也能正常展示数据。
// ============================================================

import { supabase, isSupabaseConfigured } from "@/lib/supabase";
import type { CompanyStats, Job } from "@/lib/types";

/** 静态 JSON 缓存（避免重复请求） */
let staticCache: Job[] | null = null;

async function fetchStaticJobs(): Promise<Job[]> {
  if (staticCache) return staticCache;
  try {
    const res = await fetch("/data/jobs.json");
    if (!res.ok) return [];
    staticCache = (await res.json()) as Job[];
  } catch {
    staticCache = [];
  }
  return staticCache;
}

/** 获取全部岗位：Supabase -> 本地静态 JSON 自动降级 */
export async function fetchAllJobs(): Promise<Job[]> {
  if (isSupabaseConfigured && supabase) {
    const { data, error } = await supabase
      .from("jobs")
      .select("*")
      .eq("is_active", true)
      .order("crawl_time", { ascending: false });
    if (!error && data) return data as Job[];
  }
  return fetchStaticJobs();
}

/** 按公司统计岗位数（首页公司卡片网格数据源） */
export async function fetchCompanyStats(): Promise<CompanyStats[]> {
  const jobs = await fetchAllJobs();
  const map = new Map<string, CompanyStats>();
  for (const j of jobs) {
    const s = map.get(j.company) ?? {
      company: j.company,
      company_category: j.company_category,
      job_count: 0,
      ai_algo_count: 0,
      last_crawl: null,
    };
    s.job_count += 1;
    if (j.job_type === "AI算法") s.ai_algo_count += 1;
    if (j.crawl_time && (!s.last_crawl || j.crawl_time > s.last_crawl)) {
      s.last_crawl = j.crawl_time;
    }
    map.set(j.company, s);
  }
  // 按岗位数倒序展示
  return Array.from(map.values()).sort((a, b) => b.job_count - a.job_count);
}
