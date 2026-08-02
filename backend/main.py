# ============================================================
# 爬虫任务主入口（Phase 1 + Phase 2 的编排器）
#
# 用法：
#   # 完整跑一遍（爬取 -> 过滤 -> 入库 -> LLM 结构化）
#   python backend/main.py
#
#   # 只爬取指定公司（调试单个适配器）
#   python backend/main.py --adapter bytedance --no-enrich
#
#   # 只对库中待结构化的 JD 跑 LLM（爬取已完成时）
#   python backend/main.py --enrich-only
#
#   # 以本地定时任务模式运行（每天 06:00 自动执行）
#   python backend/main.py --schedule
#
# 流程：
#   1. 逐家公司爬取（robots 检查 / 限速 / 优雅降级自动生效）
#   2. AI 岗位过滤 + job_type 归类
#   3. 增量入库（同 job_id 比对 jd_hash，变化才更新）
#   4. 对需要结构化的 JD 调用 LLM（缓存：hash 不变不重复调用）
#   5. 全程失败重试 + 结束发送汇总告警
# ============================================================

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Dict, List

# 保证能从项目根目录直接运行：backend/ 加入模块搜索路径
sys.path.insert(0, "backend")

import config
from ai_filter import filter_and_classify
from crawler.adapters import REGISTRY, get_all_spiders
from crawler.base import CrawledJob
from enrichment.llm import enrich_jd
from storage.supabase_store import JobStore
from utils import compute_jd_hash, compute_job_id, logger, send_alert


# ------------------------------------------------------------
# 第一步：爬取 + 过滤 + 标准化为存储行
# ------------------------------------------------------------

def crawl_all(adapter_ids: List[str] = None) -> Dict[str, List[dict]]:
    """
    爬取全部（或指定）公司，返回 {公司名: [存储行 dict, ...]}
    每家公司的失败互不影响（优雅降级），结果按公司分组便于日志与入库。
    """
    results: Dict[str, List[dict]] = {}
    spiders = get_all_spiders(adapter_ids)

    if not spiders:
        logger.error("没有可用的适配器。检查 backend/crawler/adapters/ 是否正确导入")
        return results

    for spider in spiders:
        try:
            raw_jobs: List[CrawledJob] = spider.crawl()
            if not raw_jobs:
                # 空结果也记录日志（站点改版 / robots 禁止 / 额度用尽）
                logger.warning("%s 爬取结果为空", spider.company)
                continue

            # 过滤 AI 岗位并归类
            ai_jobs = filter_and_classify(raw_jobs)

            # 转为存储行（补齐 job_id / jd_hash 等派生字段）
            rows = []
            for job in ai_jobs:
                row = {
                    "job_id": compute_job_id(job.domain, job.external_job_id),
                    "company": job.company,
                    "company_category": job.company_category,
                    "job_title": job.job_title,
                    "job_type": job.job_type,
                    "salary_range": job.salary_range,
                    "location": job.location,
                    "publish_date": job.publish_date or None,
                    "crawl_time": datetime.now(timezone.utc).isoformat(),
                    "source_url": job.source_url,
                    "jd_raw_text": job.jd_raw_text,
                    "jd_hash": compute_jd_hash(job.jd_raw_text),
                    # 结构化结果字段初始为空，等待 Phase 2 填充
                    "project_requirements": [],
                    "tech_stack": [],
                    "business_domain": [],
                    "interview_questions": [],
                    "needs_enrichment": True,
                    "is_active": True,
                }
                rows.append(row)
            results[spider.company] = rows
            logger.info("%s：AI 岗位 %d 条准备入库", spider.company, len(rows))
        except Exception as exc:
            # 整家公司失败：记录并继续下一家（不中断整体任务）
            logger.error("%s 爬取异常：%s", spider.company, exc)

    return results


# ------------------------------------------------------------
# 第二步：LLM 结构化（Phase 2）
# ------------------------------------------------------------

def run_enrichment(store: JobStore, limit: int = 50) -> Dict[str, int]:
    """
    对库中 needs_enrichment=true 的岗位批量调用 LLM。
    增量策略由存储层保证：
      - JD 未变的岗位不会进入待处理队列（不会重复调用 LLM）
      - JD 变化的岗位重新结构化
    """
    if not config.is_llm_configured():
        logger.warning("未配置 OPENAI_API_KEY，跳过 LLM 结构化（可稍后运行 --enrich-only 补做）")
        return {"enriched": 0, "failed": 0}

    pending = store.get_jobs_needing_enrichment(limit=limit)
    if not pending:
        logger.info("没有待结构化的 JD（增量缓存生效）")
        return {"enriched": 0, "failed": 0}

    logger.info("开始 LLM 结构化：共 %d 条待处理", len(pending))
    enriched_count = 0
    failed_count = 0

    for idx, item in enumerate(pending, start=1):
        job_id = item["job_id"]
        jd_text = item["jd_raw_text"]
        logger.info("[%d/%d] 结构化：%s", idx, len(pending), job_id)
        try:
            result = enrich_jd(jd_text)
            if result is None:
                failed_count += 1
                continue
            if store.save_enrichment(job_id, result):
                enriched_count += 1
            else:
                failed_count += 1
        except Exception as exc:
            # 单条失败不影响整体（优雅降级）
            logger.error("结构化失败（%s）：%s", job_id, exc)
            failed_count += 1

    logger.info("LLM 结构化完成：成功 %d / 失败 %d", enriched_count, failed_count)
    return {"enriched": enriched_count, "failed": failed_count}


# ------------------------------------------------------------
# 完整任务：爬取 + 入库 + 结构化
# ------------------------------------------------------------

def run_daily_job(adapter_ids: List[str] = None, do_enrich: bool = True) -> Dict[str, int]:
    """
    每日任务的完整流程（GitHub Actions 与本地调度都调用它）。
    返回统计信息，供告警使用。
    """
    started_at = datetime.now()
    summary: Dict[str, int] = {"companies": 0, "ai_jobs": 0, "inserted": 0, "updated": 0, "unchanged": 0, "enriched": 0, "failed": 0}
    store = JobStore()

    # ---- Phase 1：爬取 + 过滤 + 入库 ----
    results = crawl_all(adapter_ids)
    for company, rows in results.items():
        summary["companies"] += 1
        summary["ai_jobs"] += len(rows)
        stats = store.sync_jobs(rows)
        summary["inserted"] += stats["inserted"]
        summary["updated"] += stats["updated"]
        summary["unchanged"] += stats["unchanged"]

    # ---- Phase 2：LLM 结构化 ----
    if do_enrich:
        enrich_stats = run_enrichment(store, limit=config.DAILY_MAX_JOBS_PER_DOMAIN)
        summary["enriched"] = enrich_stats["enriched"]
        summary["failed"] = enrich_stats["failed"]

    elapsed = (datetime.now() - started_at).total_seconds()
    summary["elapsed_seconds"] = int(elapsed)

    # ---- 汇总日志 + 告警 ----
    message = (
        f"运行时长 {elapsed:.0f}s；公司 {summary['companies']} 家；"
        f"AI 岗位 {summary['ai_jobs']} 条；新增 {summary['inserted']} / 更新 {summary['updated']} / 未变 {summary['unchanged']}；"
        f"结构化成功 {summary['enriched']} / 失败 {summary['failed']}"
    )
    logger.info("每日任务完成：%s", message)
    if summary["failed"] > 0:
        send_alert("AI-JD-Aggregator 部分任务失败", message)
    elif summary["companies"] == 0:
        send_alert("AI-JD-Aggregator 无有效结果", message)
    else:
        logger.info("任务全部成功，无需告警")
    return summary


# ------------------------------------------------------------
# 本地定时调度（模拟 GitHub Actions 的每日 06:00）
# ------------------------------------------------------------

def run_with_schedule() -> None:
    """使用 APScheduler 每日 06:00 执行一次（本地开发调试用）"""
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(run_daily_job, "cron", hour=6, minute=0, args=[None, True])
    logger.info("本地定时任务已启动：每天 06:00（Asia/Shanghai）执行爬取 + 结构化")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("定时任务已停止")


# ------------------------------------------------------------
# 命令行入口
# ------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI 岗位招聘信息聚合爬虫")
    parser.add_argument(
        "--adapter", nargs="*", default=None,
        help="只运行指定适配器（如：--adapter bytedance mokahr_generic），默认全部",
    )
    parser.add_argument(
        "--no-enrich", action="store_true",
        help="跳过 LLM 结构化（只爬取入库）",
    )
    parser.add_argument(
        "--enrich-only", action="store_true",
        help="只对库中待结构化的 JD 调用 LLM（不爬取）",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="以本地定时模式运行（每天 06:00 自动执行）",
    )
    args = parser.parse_args()

    # 校验 --adapter 参数合法性（给出可选项提示）
    if args.adapter:
        unknown = [a for a in args.adapter if a not in REGISTRY]
        if unknown:
            logger.error("未知适配器：%s，可选：%s", unknown, list(REGISTRY.keys()))
            sys.exit(1)

    if args.schedule:
        run_with_schedule()
        return

    if args.enrich_only:
        store = JobStore()
        # 一次性处理全部待结构化岗位（limit 给大，避免分批多次运行）
        run_enrichment(store, limit=500)
        return

    run_daily_job(adapter_ids=args.adapter, do_enrich=not args.no_enrich)


if __name__ == "__main__":
    main()
