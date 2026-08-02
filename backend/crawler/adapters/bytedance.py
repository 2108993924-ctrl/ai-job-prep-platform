# ============================================================
# 字节跳动官方招聘页适配器
# 官网：https://jobs.bytedance.com/campus
#
# 抓取策略（API 优先，DOM 降级）：
#   1. 优先调用 jobs.bytedance.com 公开 JSON 搜索接口
#   2. API 不可用时降级为 Playwright 解析页面
# ============================================================

from typing import Dict, List, Optional

from crawler.adapters import register
from crawler.base import BaseSpider
from utils import logger

# 字节校招岗位卡片选择器（页面改版后需更新）
LIST_CARD_SELECTOR = "a[href*='/campus/position/']"
# 详情正文容器选择器
DETAIL_BODY_SELECTOR = ".job-detail-section, .job-detail, .section-container"


def _deep_get(data: dict, keys: List[str], default=""):
    """从嵌套 dict 中按多个候选 key 取第一个存在的值（字段名版本兼容）"""
    for key in keys:
        if isinstance(data, dict) and key in data:
            return data[key]
    return default


@register("bytedance")
class ByteDanceSpider(BaseSpider):
    """字节跳动（互联网大厂代表）"""

    company: str = "字节跳动"
    company_category: str = "互联网大厂"
    start_url: str = "https://jobs.bytedance.com/campus"

    def __init__(self):
        super().__init__(use_playwright=True)

    # ========================================================
    # 第一步：获取岗位列表
    # ========================================================

    def fetch_job_list(self) -> List[dict]:
        jobs = self._fetch_list_via_api()
        if jobs:
            return jobs
        logger.info("字节跳动 API 不可用，降级为页面解析")
        return self._fetch_list_via_dom()

    def _fetch_list_via_api(self) -> List[dict]:
        """
        调用字节跳动公开招聘搜索接口。
        依次尝试多个常见端点（各版本端点可能不同），请求两个关键词合并去重。
        """
        endpoints = [
            "https://jobs.bytedance.com/api/v1/search/job/posts",
            "https://jobs.bytedance.com/api/v1/campus/position/list",
        ]
        # AI 相关关键词：合并两次查询结果，覆盖更多岗位
        keywords = ["AI", "算法"]
        result: List[dict] = []
        seen: set = set()

        for endpoint in endpoints:
            for keyword in keywords:
                try:
                    resp = self.http_post(endpoint, json={
                        "keyword": keyword,
                        "limit": 100,
                        "offset": 0,
                        "type": "campus",  # 校招
                    }, timeout=25)
                    data = resp.json()
                except Exception as exc:
                    logger.warning("字节 API 请求失败（%s, %s）：%s", endpoint, keyword, exc)
                    continue

                # 兼容不同返回结构：data.job_post / data.list / data.positionList ...
                payload = data.get("data", data) if isinstance(data, dict) else None
                items = []
                if isinstance(payload, dict):
                    for key in ("job_post", "list", "positionList", "records", "items", "content"):
                        if isinstance(payload.get(key), list):
                            items = payload[key]
                            break
                for job in items:
                    if not isinstance(job, dict):
                        continue
                    job_id = str(_deep_get(job, ["id", "jobId"], ""))
                    title = str(_deep_get(job, ["title", "job_title", "position_name"], ""))
                    if not job_id or not title or job_id in seen:
                        continue
                    seen.add(job_id)
                    result.append({
                        "job_key": job_id,
                        "title": title,
                        "url": f"https://jobs.bytedance.com/campus/position/{job_id}/detail",
                    })
                if result:
                    # 已拿到结果就不必再试其它端点
                    logger.info("字节 API（%s）解析到 %d 条", endpoint, len(result))
                    return result
        return result

    def _fetch_list_via_dom(self) -> List[dict]:
        """降级方案：Playwright 打开校招首页解析岗位链接"""
        html = self.fetch_page_html(self.start_url, wait_selector=LIST_CARD_SELECTOR, wait_ms=8000)
        if not html:
            return []
        soup = self.parse_html(html)
        result: List[dict] = []
        seen: set = set()
        for link in soup.select(LIST_CARD_SELECTOR):
            href = link.get("href", "")
            if not href.startswith("http"):
                href = "https://jobs.bytedance.com" + href
            job_id = href.rstrip("/").rsplit("/", 1)[-1]
            if job_id in seen:
                continue
            seen.add(job_id)
            result.append({
                "job_key": job_id,
                "title": self.extract_text(link),
                "url": href,
            })
        return result

    # ========================================================
    # 第二步：获取单条 JD 详情
    # ========================================================

    def fetch_job_detail(self, url: str, job_key: str) -> Optional[dict]:
        detail = self._fetch_detail_via_api(job_key)
        if detail:
            return detail
        return self._fetch_detail_via_dom(url)

    def _fetch_detail_via_api(self, job_id: str) -> Optional[dict]:
        """调用岗位详情 API（尝试多个端点）"""
        endpoints = [
            f"https://jobs.bytedance.com/api/v1/campus/position/{job_id}",
            f"https://jobs.bytedance.com/api/v1/campus/job/{job_id}",
        ]
        for endpoint in endpoints:
            try:
                resp = self.http_get(endpoint, timeout=25)
                data = resp.json()
            except Exception as exc:
                logger.warning("字节详情 API 失败（%s）：%s", endpoint, exc)
                continue
            job = data.get("data", data) if isinstance(data, dict) else None
            if not isinstance(job, dict):
                continue
            title = _deep_get(job, ["title", "job_title", "position_name"], "")
            description = _deep_get(job, ["description", "job_description", "detail", "content"], "")
            if not description:
                continue
            return {
                "job_title": str(title),
                "jd_raw_text": f"岗位名称：{title}\n{description}",
                "location": str(_deep_get(job, ["location", "city", "campus_address"], "")),
                "salary_range": str(_deep_get(job, ["salary", "salary_range", "salary_desc"], "")),
                "publish_date": str(_deep_get(job, ["publish_time", "publishTime", "create_time"], "")),
            }
        return None

    def _fetch_detail_via_dom(self, url: str) -> Optional[dict]:
        """降级方案：Playwright 打开详情页提取正文"""
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
