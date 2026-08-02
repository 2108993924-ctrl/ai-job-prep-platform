# ============================================================
# 腾讯官方招聘页适配器
# 官网：https://careers.tencent.com（JS 渲染 SPA）
#
# 抓取策略（2026-08 实测）：
#   1. 优先调用腾讯公开岗位 API（careers.tencent.com/tencentcareer/api/post/Query），
#      响应含完整职责描述（Responsibility），无需逐条打开详情页
#   2. 按用户需求只保留「深圳 / 广州」两地的岗位（腾讯总部在深圳）
#   3. 结合 ai_filter 关键词粗筛 AI 岗位，控制拉取量（遵守单域名日限 200 条）
# ============================================================

from typing import Dict, List, Optional

from ai_filter import STRONG_TITLE_KEYWORDS, WEAK_BODY_KEYWORDS
from crawler.adapters import register
from crawler.base import BaseSpider

# 腾讯公开岗位查询 API（分页参数 pageIndex/pageSize，返回 Data.Posts）
LIST_API = "https://careers.tencent.com/tencentcareer/api/post/Query"
# 目标城市（用户在广东，只保留深圳/广州岗位）
TARGET_CITIES = ("深圳", "广州")
# 每页拉取条数（接口上限 100）
PAGE_SIZE = 100


@register("tencent")
class TencentSpider(BaseSpider):
    """腾讯（互联网大厂，总部深圳）—— 社招岗位"""

    company: str = "腾讯"
    company_category: str = "互联网大厂"
    start_url: str = "https://careers.tencent.com"

    def __init__(self):
        # 纯 API 路线，不需要 Playwright 浏览器
        super().__init__(use_playwright=False)

    # ========================================================
    # 第一步：获取岗位列表（API 分页拉取 + 广深 + AI 粗筛）
    # ========================================================

    def fetch_job_list(self) -> List[dict]:
        result: List[dict] = []
        seen: set = set()
        for page in range(1, 20):  # 最多拉 20 页（2000 条，够覆盖广深 AI 岗）
            page_items, raw_count = self._fetch_page(page)
            if page_items is None:
                break  # 请求失败
            new_count = 0
            for post in page_items:
                # _fetch_page 返回的 item 键名为 job_key（非 API 原始字段 PostId）
                post_id = str(post.get("job_key", "") or "")
                if not post_id or post_id in seen:
                    continue
                seen.add(post_id)
                new_count += 1
                result.append(post)
            self.logger.info("腾讯第 %d 页解析到 %d 个岗位（累计 %d）", page, new_count, len(result))
            if raw_count < PAGE_SIZE:
                break  # 拉到底了（用 API 原始条数判断，而非过滤后条数）
        # 缓存列表结果，供 fetch_job_detail 复用（避免逐条请求）
        self._list_items_cache = {it["job_key"]: it for it in result}
        self.logger.info("腾讯广深 AI 岗位候选 %d 个", len(result))
        return result

    def _fetch_page(self, page: int) -> tuple:
        """拉取一页并过滤广深+AI；返回 (过滤后的岗位列表, API 原始条数)"""
        try:
            resp = self.http_get(LIST_API, timeout=20, params={
                "timestamp": "",  # 服务端未校验
                "countryId": "", "cityId": "", "bgIds": "", "productId": "",
                "categoryId": "", "parentCategoryId": "", "attrId": "",
                "keyword": "", "pageIndex": page, "pageSize": PAGE_SIZE,
                "language": "zh-cn", "area": "cn",
            })
            data = resp.json()
            posts = (data.get("Data") or {}).get("Posts") or []
        except Exception as exc:
            self.logger.warning("腾讯 API 第 %d 页请求失败：%s", page, exc)
            return None, 0

        result: List[dict] = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            title = str(post.get("RecruitPostName", "") or "").strip()
            location = str(post.get("LocationName", "") or "").strip()
            responsibility = str(post.get("Responsibility", "") or "").strip()
            if not title:
                continue
            # 1) 城市过滤：深圳 / 广州
            if not any(city in location for city in TARGET_CITIES):
                continue
            # 2) AI 粗筛：标题命中强词，或正文命中弱词
            if not any(kw.lower() in title.lower() for kw in STRONG_TITLE_KEYWORDS) and \
               not any(kw.lower() in responsibility.lower() for kw in WEAK_BODY_KEYWORDS):
                continue
            post_id = str(post.get("PostId", "") or post.get("Id", ""))
            result.append({
                "job_key": post_id,
                "title": title,
                "url": str(post.get("PostURL", "") or f"https://careers.tencent.com/jobdesc.html?postId={post_id}"),
                # 列表 API 已含完整职责描述，详情直接复用，不再请求
                "_jd_raw_text": f"岗位名称：{title}\n{responsibility}",
                "_location": location,
                "_salary": str(post.get("RequireWorkYearsName", "") or ""),
                "_publish": self._fmt_time(post.get("LastUpdateTime")),
            })
        return result, len(posts)

    @staticmethod
    def _fmt_time(ts) -> str:
        """LastUpdateTime 为毫秒时间戳，转 YYYY-MM-DD；无效返回空串"""
        if not ts:
            return ""
        try:
            import time
            return time.strftime("%Y-%m-%d", time.localtime(int(ts) / 1000))
        except Exception:
            return ""

    # ========================================================
    # 第二步：获取单条 JD 详情（直接用列表页数据，不再请求）
    # ========================================================

    def fetch_job_detail(self, url: str, job_key: str) -> Optional[dict]:
        # 列表阶段已存了完整 JD（_jd_raw_text），直接构造
        item = self._pending_item(url, job_key)
        if item:
            return {
                "job_title": item["title"],
                "jd_raw_text": item.get("_jd_raw_text", ""),
                "location": item.get("_location", ""),
                "salary_range": item.get("_salary", ""),
                "publish_date": item.get("_publish", ""),
            }
        return None

    def _pending_item(self, url: str, job_key: str) -> Optional[dict]:
        """从最近一次列表结果中按 job_key 找回原始 item"""
        cache = getattr(self, "_list_items_cache", None)
        return cache.get(job_key) if cache else None
