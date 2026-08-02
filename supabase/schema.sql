-- ============================================================
-- AI-JD-Aggregator 数据库 Schema（Supabase / PostgreSQL）
--
-- 使用方法：Supabase 控制台 -> SQL Editor -> New query
--           -> 粘贴本文件全部内容 -> Run
--
-- 包含：
--   1. jobs 表：岗位 JD + AI 结构化结果
--   2. crawl_logs 表：每日爬取日志
--   3. 索引：中文全文检索（pg_trgm 模糊匹配）+ 常用筛选列
--   4. RLS：匿名用户只读（前端用 anon key），服务端密钥不受限
--   5. updated_at 自动更新触发器
-- ============================================================

-- 开启模糊搜索扩展（Supabase 已预装，直接启用即可）
create extension if not exists pg_trgm;

-- ------------------------------------------------------------
-- 1. 岗位表
-- ------------------------------------------------------------
create table if not exists public.jobs (
    job_id                text primary key,          -- 公司域名+岗位ID 哈希（稳定唯一）
    company               text not null,             -- 公司名
    company_category      text not null,             -- 互联网大厂/大模型独角兽/AI垂直龙头/国企AI
    job_title             text not null,             -- 岗位名
    job_type              text,                      -- AI算法/AI工程/AI产品/AI应用/数据科学
    salary_range          text,                      -- 薪资（若公开）
    location              text,                      -- 工作地
    publish_date          date,                      -- JD 发布日
    crawl_time            timestamptz not null default now(),  -- 抓取时间
    source_url            text,                      -- JD 原文链接
    jd_raw_text           text not null,             -- JD 原文（供展示与 LLM 结构化）
    jd_hash               text not null,             -- JD 原文指纹（增量判断依据）

    -- === AI 结构化结果（Phase 2 填充）===
    project_requirements  jsonb not null default '[]'::jsonb,  -- 项目能力要求（字符串数组）
    tech_stack            jsonb not null default '[]'::jsonb,  -- 技术栈（字符串数组）
    business_domain       jsonb not null default '[]'::jsonb,  -- 业务领域（枚举数组，最多2个）
    interview_questions   jsonb not null default '[]'::jsonb,  -- 5道面试题（含参考答案）
    enriched_at           timestamptz,               -- 最近一次结构化时间
    needs_enrichment      boolean not null default false,      -- 待结构化标记（增量机制）

    is_active             boolean not null default true,       -- 岗位仍可投递（下架置 false）
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now()
);

-- 常用筛选索引（公司列表页 / 公司详情页筛选）
create index if not exists idx_jobs_company        on public.jobs (company);
create index if not exists idx_jobs_category       on public.jobs (company_category);
create index if not exists idx_jobs_job_type       on public.jobs (job_type);
create index if not exists idx_jobs_is_active      on public.jobs (is_active);
create index if not exists idx_jobs_needs_enrich   on public.jobs (needs_enrichment) where needs_enrichment;

-- 中文全文检索索引：
-- 说明：PostgreSQL 内置分词器对中文按"字"处理，配合 trigram 索引的
-- ilike 模糊搜索即可达到实用效果（如搜索"RAG"、"LoRA"、"多模态"）。
-- 索引组合：标题 + 公司名 + 技术栈文本。
create index if not exists idx_jobs_trgm_title
    on public.jobs using gin (job_title gin_trgm_ops);
create index if not exists idx_jobs_trgm_company
    on public.jobs using gin (company gin_trgm_ops);
create index if not exists idx_jobs_trgm_techstack
    on public.jobs using gin (tech_stack gin_trgm_ops);

-- ------------------------------------------------------------
-- 2. 爬取日志表
-- ------------------------------------------------------------
create table if not exists public.crawl_logs (
    id          bigserial primary key,
    company     text not null,
    status      text not null,        -- success / failed / skipped
    message     text,
    crawl_time  timestamptz not null default now()
);

create index if not exists idx_crawl_logs_time on public.crawl_logs (crawl_time desc);

-- ------------------------------------------------------------
-- 3. updated_at 自动更新（触发器）
-- ------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_jobs_updated_at on public.jobs;
create trigger trg_jobs_updated_at
    before update on public.jobs
    for each row execute function public.set_updated_at();

-- ------------------------------------------------------------
-- 4. 行级安全策略（RLS）
--    前端使用 anon key 只读查询；爬虫使用 service role key 可读写
-- ------------------------------------------------------------
alter table public.jobs enable row level security;
alter table public.crawl_logs enable row level security;

-- 匿名用户：允许 SELECT（前端展示），禁止写入
create policy "anon can read jobs" on public.jobs
    for select to anon using (true);

create policy "anon can read crawl_logs" on public.crawl_logs
    for select to anon using (true);

-- 服务端密钥（service_role）绕过 RLS，天然可写，无需额外策略
-- 认证用户（authenticated）暂不需要访问；未来若加管理后台，再补策略

-- ------------------------------------------------------------
-- 5. 常见统计视图（首页公司卡片网格用）
-- ------------------------------------------------------------
create or replace view public.company_stats as
select
    company,
    company_category,
    count(*)                                    as job_count,
    count(*) filter (where job_type = 'AI算法')  as ai_algo_count,
    max(crawl_time)                             as last_crawl
from public.jobs
where is_active = true
group by company, company_category
order by job_count desc;

-- 授权视图给匿名用户
grant select on public.company_stats to anon;
