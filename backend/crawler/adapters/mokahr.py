# ============================================================
# 通用 mokahr 系统适配器
#
# 多家 AI 独角兽（阶跃星辰、速腾聚创等）使用 mokahr 招聘 SaaS 系统，
# 页面结构与 API 一致，写一个适配器即可复用。
#
# 抓取策略（2025+ 新版页面，2026-08 实测）：
#   1. 公开 API 已升级为全链路加密（/api/outer/ats-apply/website/jobs/v2
#      返回 data+necromancer 加密串，解密逻辑在前端 JS，无法直接调用），
#      因此不再走 API，以 DOM 解析为主路线
#   2. 列表页为 hash 路由 SPA（#/jobs?page=N），岗位数据内嵌在页面 DOM 中
#      （每条岗位的 a 标签内含有完整【岗位描述】），一次渲染即可取全，
#      无需逐条打开详情页，兼顾速度与服务器负载
# ============================================================

import re
from typing import Dict, List, Optional

from crawler.adapters import register
from crawler.base import BaseSpider, CrawledJob
from utils import logger

# mokahr 新版页面选择器（hash 路由 SPA，2026-08 实测）
LIST_LINK_SELECTOR = "a[href*='#/job/']"       # 岗位卡片链接
DESC_SELECTOR = "[class*='job-description']"   # 岗位描述容器（列表页内嵌完整 JD）
DETAIL_TEXT_SELECTORS = [
    "[class*='job-description']",
    "[class*='job-detail']",
    ".job-detail-content",
    ".job-detail",
]
# 标题行常见徽章词（如“急”“热”），提取标题时跳过
BADGE_WORDS = ("急", "热", "新", "紧急", "急聘")
# 地点正则：匹配“北京市”“上海市”等城市名
LOCATION_RE = re.compile(r"[\u4e00-\u9fa5]{2,8}(?:市|自治州)")


def _deep_get(data: dict, keys: List[str], default=""):
    """
    从嵌套 dict 中按多个候选 key 找值（mokahr API 字段名各版本不一致，宽松匹配）。
    例：_deep_get(resp, ["data", "job", "title"]) 或 ["title"]
    """
    for key in keys:
        if isinstance(data, dict) and key in data:
            return data[key]
    return default


@register("mokahr_generic")
class MokahrSpider(BaseSpider):
    """mokahr 招聘系统的通用适配器（子类只需覆盖 company 与 org 配置）"""

    # ---- 子类必须覆盖 ----
    company: str = "MOKAHR公司"
    company_category: str = "大模型独角兽"
    # mokahr 招聘页路径，例如：https://app.mokahr.com/campus-recruitment/step/141903
    org_path: str = ""
    # 详情页 URL 模板：{path} 为 org_path，{job_id} 为岗位 ID
    detail_url_template: str = "https://app.mokahr.com{path}/job/{job_id}"
    # 列表页无城市信息时使用的默认工作地点（如速腾聚创总部在深圳）
    default_location: str = ""

    start_url: str = "https://app.mokahr.com"

    def __init__(self):
        # 若子类未设置 org_path，直接报错提醒（比运行时报错更清晰）
        if not self.org_path:
            raise ValueError(f"{self.company} 适配器未配置 org_path")
        self.start_url = f"https://app.mokahr.com{self.org_path}"
        self.domain = "app.mokahr.com"
        # 列表页抓取时暂存的完整 JD（job_key -> 描述），避免逐条重开浏览器
        self._list_jd_cache: Dict[str, dict] = {}
        super().__init__(use_playwright=True)

    # ========================================================
    # 第一步：获取岗位列表（DOM 主路线，列表页内嵌完整 JD）
    # ========================================================

    def fetch_job_list(self) -> List[dict]:
        return self._fetch_list_via_dom()

    def _fetch_list_via_dom(self) -> List[dict]:
        """主路线：Playwright 打开列表页（#/jobs?page=N），从 DOM 提取岗位。

        新版列表页每条岗位的 a 标签内直接包含完整【岗位描述】
        （class 含 job-description），一次渲染即可取全，无需逐条开详情页。
        翻页直到没有新岗位为止（每页请求间隔由基类限速器控制）。
        """
        result: List[dict] = []
        seen: set = set()
        self._list_jd_cache = {}
        for page in range(1, 6):  # 最多翻 5 页（保守，避免过多请求）
            list_url = f"{self.start_url}#/jobs?page={page}"
            html = self.fetch_page_html(list_url, wait_selector=LIST_LINK_SELECTOR, wait_ms=6000)
            if not html:
                logger.warning("%s 列表页第 %d 页加载失败", self.company, page)
                break
            soup = self.parse_html(html)
            new_count = 0
            for link in soup.select(LIST_LINK_SELECTOR):
                href = link.get("href", "")
                # href 形如 ...141903#/job/4fd27b27-xxxx，取 hash 内最后一段为 job_id
                job_id = href.rsplit("/", 1)[-1] if "/" in href else ""
                if not job_id or job_id in seen:
                    continue
                seen.add(job_id)
                new_count += 1
                # 标题：取文本首行（跳过“急/热”等徽章词）
                lines = [ln.strip() for ln in link.get_text("\n", strip=True).splitlines() if ln.strip()]
                title = next((ln for ln in lines if ln not in BADGE_WORDS), lines[0] if lines else "")
                # 完整 JD：优先描述容器，兜底取链接全文
                desc_node = link.select_one(DESC_SELECTOR)
                desc = self.extract_text(desc_node) if desc_node else self.extract_text(link)
                # 地点：从链接文本提取城市名（去重拼接）
                locations: List[str] = []
                for m in LOCATION_RE.finditer(link.get_text(" ", strip=True)):
                    if m.group(0) not in locations:
                        locations.append(m.group(0))
                item = {
                    "job_key": job_id,
                    "title": title,
                    "url": f"{self.start_url}#/job/{job_id}",
                    "_jd_raw_text": desc,
                    "_location": " ".join(locations),
                }
                result.append(item)
                self._list_jd_cache[job_id] = item
            logger.info("%s 列表第 %d 页解析到 %d 个岗位（累计 %d）", self.company, page, new_count, len(result))
            if new_count == 0:
                break  # 没有新岗位，停止翻页
        return result

    # ========================================================
    # 第二步：获取单条 JD 详情（优先用列表页缓存，避免逐条开浏览器）
    # ========================================================

    def fetch_job_detail(self, url: str, job_key: str) -> Optional[dict]:
        cached = self._list_jd_cache.get(job_key)
        if cached and cached.get("_jd_raw_text"):
            return {
                "job_title": cached["title"],
                "jd_raw_text": cached["_jd_raw_text"],
                "location": cached.get("_location") or self.default_location,
                "salary_range": "",
                "publish_date": "",
            }
        # 兜底：列表页无内嵌描述时打开详情页
        return self._fetch_detail_via_dom(url)

    def _fetch_detail_via_dom(self, url: str) -> Optional[dict]:
        """兜底：Playwright 打开详情页（hash 路由）提取正文"""
        html = self.fetch_page_html(url, wait_selector=DESC_SELECTOR, wait_ms=5000)
        if not html:
            return None
        soup = self.parse_html(html)
        # 提取标题：h1 / 包含岗位名的元素 / title 标签
        title = ""
        for selector in ("h1", "[class*='job-name']", ".job-title", ".position-name", "title"):
            node = soup.select_one(selector)
            if node:
                title = self.extract_text(node)
                if title:
                    break
        # 提取正文：多个候选容器
        body = ""
        for selector in DETAIL_TEXT_SELECTORS:
            node = soup.select_one(selector)
            if node:
                body = self.extract_text(node)
                if body:
                    break
        if not body:
            return None
        return {
            "job_title": title,
            "jd_raw_text": f"岗位名称：{title}\n{body}",
            "location": "",
            "salary_range": "",
            "publish_date": "",
        }


# ============================================================
# 使用 mokahr 系统的具体公司注册（每家公司一个子类，仅改配置）
# ============================================================

@register("stepfun")
class StepFunSpider(MokahrSpider):
    """阶跃星辰（StepFun）：多模态大模型独角兽"""
    company: str = "阶跃星辰"
    company_category: str = "大模型独角兽"
    org_path: str = "/campus-recruitment/step/141903"


@register("robosense")
class RoboSenseSpider(MokahrSpider):
    """速腾聚创（RoboSense）：激光雷达 + AI 感知，总部位于深圳"""
    company: str = "速腾聚创"
    company_category: str = "AI垂直龙头"
    org_path: str = "/campus-recruitment/robosense/69887"
    default_location: str = "深圳市"
