// ============================================================
// 类型定义：与后端数据模型（jobs 表）一一对应
// ============================================================

/** 岗位类别（PRD 定义） */
export type CompanyCategory = "互联网大厂" | "大模型独角兽" | "AI垂直龙头" | "国企AI";

/** 岗位类型（PRD 定义） */
export type JobType = "AI算法" | "AI工程" | "AI产品" | "AI应用" | "数据科学";

/** 面试题维度（PRD 定义） */
export type QuestionCategory = "基础原理" | "大模型应用" | "工程实现" | "生产调优" | "场景判断";

/** 单道面试题（含参考答案） */
export interface InterviewQuestion {
  question: string;
  category: QuestionCategory;
  reference_answer: string;
}

/** 岗位记录（对应数据库 jobs 表） */
export interface Job {
  job_id: string;
  company: string;
  company_category: CompanyCategory;
  job_title: string;
  job_type: JobType | null;
  salary_range: string | null;
  location: string | null;
  publish_date: string | null;
  crawl_time: string;
  source_url: string | null;
  jd_raw_text: string;
  /** AI 结构化结果 */
  project_requirements: string[];
  tech_stack: string[];
  business_domain: string[];
  interview_questions: InterviewQuestion[];
  enriched_at: string | null;
  is_active: boolean;
}

/** 公司统计（首页卡片网格使用，对应 company_stats 视图） */
export interface CompanyStats {
  company: string;
  company_category: CompanyCategory;
  job_count: number;
  ai_algo_count: number;
  last_crawl: string | null;
}
