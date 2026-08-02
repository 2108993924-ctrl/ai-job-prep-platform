# ============================================================
# 美团官方招聘页适配器
# 官网：https://hr.meituan.com（JS 渲染，Playwright 解析）
#
# 美团首页含校招/社招入口，岗位链接通常带 /campus/jobs/ 或 /job/ 特征，
# 选择器失效时按 README「故障排查」更新。
# ============================================================

from typing import Dict, List, Optional

from crawler.adapters import register
from crawler.base import BaseSpider

# 岗位链接特征（含校招 jobs 与社招 job 两种路径）
LINK_PATTERN = "a[href*='/job'], a[href*='/jobs/'], a[href*='/position']"
DETAIL_BODY_SELECTOR = ".job-detail, .job-info, .jd-content, .position-content"


@register("meituan")
class MeituanSpider(BaseSpider):
    """美团（互联网大厂，本地生活 AI 岗位多）"""

    company: str = "美团"
    company_category: str = "互联网大厂"
    start_url: str = "https://hr.meituan.com"

    def __init__(self):
        super().__init__(use_playwright=True)

    def fetch_job_list(self) -> List[dict]:
        """打开招聘首页提取岗位链接（首页通常已含岗位入口）"""
        html = self.fetch_page_html(self.start_url, wait_ms=8000)
        if not html:
            return []
        soup = self.parse_html(html)
        result: List[dict] = []
        seen: set = set()
        for link in soup.select(LINK_PATTERN):
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://hr.meituan.com" + href
            job_id = href.rstrip("/").rsplit("/", 1)[-1]
            if not job_id or job_id in seen or len(job_id) > 40:
                continue
            seen.add(job_id)
            title = self.extract_text(link)
            if not title or len(title) > 60:
                continue
            result.append({"job_key": job_id, "title": title, "url": href})
        return result

    def fetch_job_detail(self, url: str, job_key: str) -> Optional[dict]:
        html = self.fetch_page_html(url, wait_selector=DETAIL_BODY_SELECTOR, wait_ms=6000)
        if not html:
            return None
        soup = self.parse_html(html)
        title_node = soup.select_one("h1") or soup.select_one(".job-title") or soup.select_one("title")
        title = self.extract_text(title_node)
        body_node = soup.select_one(DETAIL_BODY_SELECTOR)
        body = self.extract_text(body_node)
        if not body:
            return None
        return {
            "job_title": title,
            "jd_raw_text": f"岗位名称：{title}\n{body}",
            "location": "",
            "salary_range": "",
            "publish_date": "",
        }
