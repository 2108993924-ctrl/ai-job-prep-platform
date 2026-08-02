# ============================================================
# 手动导入适配器（合规降级方案，PRD 要求）
#
# 适用场景（任一满足即启用）：
#   - 某站点 robots.txt 明确禁止爬取（自动降级，见 base.py crawl()）
#   - 某站点改版导致选择器失效，暂时无法自动化
#   - 某公司暂无公开招聘页，但希望收录其岗位
#
# 使用方法：
#   在项目根目录 data/manual_jobs.json 中按下方格式粘贴 JD 文本
#   （需在 .gitignore 中确认 data/ 已忽略），运行爬虫时自动入库。
#
# 格式示例：
# [
#   {
#     "company": "示例公司",
#     "company_category": "大模型独角兽",
#     "job_title": "大模型算法工程师",
#     "job_type": "AI算法",
#     "location": "北京",
#     "salary_range": "",
#     "publish_date": "2026-07-01",
#     "source_url": "https://example.com/jobs/1",
#     "jd_raw_text": "岗位职责：...\n任职要求：..."
#   }
# ]
# ============================================================

import json
import os
from typing import Dict, List, Optional

from crawler.adapters import register
from crawler.base import BaseSpider, CrawledJob
from utils import logger

# 手动导入数据文件路径（相对项目根目录 data/manual_jobs.json）
# 本文件位于 backend/crawler/adapters/，上溯 4 层到项目根
MANUAL_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "manual_jobs.json",
)


@register("manual")
class ManualImportSpider(BaseSpider):
    """
    手动导入爬虫：直接读取 data/manual_jobs.json，不发起任何网络请求。
    每次运行都会重新读取文件，方便随时增删岗位。
    """

    company: str = "手动导入"
    company_category: str = "手动导入"
    start_url: str = "https://localhost/manual"  # 占位，不会真的访问

    def __init__(self):
        super().__init__(use_playwright=False)

    def crawl(self) -> List[CrawledJob]:
        """重写父类 crawl：不检查 robots、不限速（没有网络请求）"""
        if not os.path.exists(MANUAL_JSON_PATH):
            logger.info("未找到 %s（不存在手动导入数据，跳过）", MANUAL_JSON_PATH)
            return []

        try:
            with open(MANUAL_JSON_PATH, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("手动导入文件解析失败：%s", exc)
            return []

        jobs: List[CrawledJob] = []
        for item in raw_items:
            if not isinstance(item, dict) or not item.get("jd_raw_text"):
                continue
            jd_text = str(item.get("jd_raw_text", "")).strip()
            if len(jd_text) < 30:
                continue
            # 用 source_url + 标题 生成稳定的 job_id
            source_url = str(item.get("source_url", ""))
            external_id = f"{item.get('company', '')}|{item.get('job_title', '')}|{source_url}"
            job = CrawledJob(
                company=str(item.get("company", "未命名公司")),
                company_category=str(item.get("company_category", "手动导入")),
                job_title=str(item.get("job_title", "")),
                job_type=str(item.get("job_type", "")),
                location=str(item.get("location", "")),
                salary_range=str(item.get("salary_range", "")),
                publish_date=str(item.get("publish_date", "")),
                source_url=source_url,
                jd_raw_text=jd_text,
                external_job_id=external_id,
                domain="manual",
            )
            jobs.append(job)
        logger.info("手动导入数据：读取到 %d 条岗位", len(jobs))
        return jobs
