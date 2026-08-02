# ============================================================
# 通用官网招聘频道适配器（配置化）
#
# 适用于「官网自建招聘频道」的公司：页面是 JS 渲染的岗位列表，
# 但不同公司的选择器不同。这里把选择器抽成配置，新公司只需
# 调用 make_official_site_spider() 注册一份配置即可（见文件底部）。
#
# 已覆盖：MiniMax / 智谱 AI / 科大讯飞
# ============================================================

from typing import Dict, List, Optional

from crawler.adapters import register
from crawler.base import BaseSpider


class OfficialSiteSpider(BaseSpider):
    """
    官网招聘频道通用爬虫。
    子类（或工厂生成的类）只需配置：
      - link_pattern:       岗位链接的 CSS 选择器（如 "a[href*='/job/']"）
      - detail_selector:    详情页正文容器选择器
      - title_selector:     详情页标题选择器（默认 h1 兜底）
    """

    link_pattern: str = "a[href*='/job/'], a[href*='/position/'], a[href*='/careers/']"
    detail_selector: str = ".job-detail, .job-content, .position-detail, .detail-content, .job-description"
    title_selector: str = "h1, .job-title, .position-title, title"

    def __init__(self):
        super().__init__(use_playwright=True)

    def fetch_job_list(self) -> List[dict]:
        """打开招聘频道页，滚动加载后提取全部岗位链接"""
        html = self.fetch_page_html(self.start_url, wait_ms=8000)
        if not html:
            return []
        soup = self.parse_html(html)
        result: List[dict] = []
        seen: set = set()
        for link in soup.select(self.link_pattern):
            href = link.get("href", "")
            if not href.startswith("http"):
                href = self.start_url.rstrip("/").rsplit("/", 1)[0] + href
            job_id = href.rstrip("/").rsplit("/", 1)[-1]
            # 过滤掉明显不是岗位的链接（如品牌页 /about/、工具页 /join/）
            if not job_id or len(job_id) > 40 or job_id in seen:
                continue
            seen.add(job_id)
            title = self.extract_text(link)
            if not title or len(title) > 60:
                continue
            result.append({"job_key": job_id, "title": title, "url": href})
        return result

    def fetch_job_detail(self, url: str, job_key: str) -> Optional[dict]:
        """打开岗位详情页，提取标题与正文"""
        html = self.fetch_page_html(url, wait_selector=self.detail_selector, wait_ms=6000)
        if not html:
            return None
        soup = self.parse_html(html)
        title_node = soup.select_one(self.title_selector)
        title = self.extract_text(title_node)
        body_node = soup.select_one(self.detail_selector)
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


# ------------------------------------------------------------
# 工厂函数：用一份配置生成并注册一个公司适配器
# ------------------------------------------------------------

def make_official_site_spider(
    adapter_id: str,
    company: str,
    company_category: str,
    start_url: str,
    link_pattern: str = None,
    detail_selector: str = None,
):
    """
    根据配置动态生成适配器类并注册到 REGISTRY。
    :param adapter_id: 唯一 id（命令行 --adapter 参数使用）
    :param company: 公司名
    :param company_category: 公司类别（互联网大厂/大模型独角兽/AI垂直龙头/国企AI）
    :param start_url: 招聘频道入口 URL
    :param link_pattern: 岗位链接选择器（不传用默认）
    :param detail_selector: 详情正文选择器（不传用默认）
    """
    attrs = {
        "company": company,
        "company_category": company_category,
        "start_url": start_url,
        "link_pattern": link_pattern or OfficialSiteSpider.link_pattern,
        "detail_selector": detail_selector or OfficialSiteSpider.detail_selector,
    }
    cls = type(f"{adapter_id.capitalize()}Spider", (OfficialSiteSpider,), attrs)
    register(adapter_id)(cls)
    return cls


# ============================================================
# 各公司配置注册（后续新增官网自建招聘频道的公司，照抄一行即可）
# ============================================================

# MiniMax：大模型独角兽（海螺 / 星野背后的公司）
make_official_site_spider(
    adapter_id="minimax",
    company="MiniMax",
    company_category="大模型独角兽",
    start_url="https://www.minimax.io/careers",
    link_pattern="a[href*='/job'], a[href*='/careers/']",
    detail_selector=".job-detail, .career-detail, .post-content",
)

# 智谱 AI：国产大模型第一梯队（GLM 系列）
make_official_site_spider(
    adapter_id="zhipu",
    company="智谱AI",
    company_category="大模型独角兽",
    start_url="https://www.zhipuai.cn/careers",
    link_pattern="a[href*='/job'], a[href*='/career'], a[href*='/position']",
    detail_selector=".job-detail, .career-content, .position-detail",
)

# 科大讯飞：AI 垂直龙头（语音识别 / 星火大模型）
make_official_site_spider(
    adapter_id="iflytek",
    company="科大讯飞",
    company_category="AI垂直龙头",
    start_url="https://www.iflytek.com/join",
    link_pattern="a[href*='/job'], a[href*='/position'], a[href*='/join/']",
    detail_selector=".job-detail, .join-content, .recruit-detail",
)
