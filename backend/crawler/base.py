# ============================================================
# 爬虫基类（所有企业适配器的公共框架）
#
# 每个适配器只需实现 3 个方法：
#   - fetch_job_list():  获取岗位列表（job_key + 详情 URL）
#   - fetch_job_detail(url, job_key): 获取单条 JD 详情
#   - (可选) parse 辅助
#
# 基类负责统一处理的合规/健壮性逻辑：
#   1. robots.txt 检查（每个 URL 请求前）
#   2. 请求间隔 3~5 秒随机限速 + 站点 Crawl-delay
#   3. 单域名每日 200 条上限
#   4. User-Agent 标识
#   5. 失败重试（指数退避）
#   6. 优雅降级：单个岗位解析失败只记日志，不中断整站
# ============================================================

import random
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

import config
from crawler.rate_limiter import RateLimitExceeded, get_rate_limiter
from crawler.robots import can_fetch, extract_domain, get_crawl_delay
from utils import compute_jd_hash, compute_job_id, logger, normalize_whitespace, retry_on_exception


# ------------------------------------------------------------
# 标准化岗位数据模型（爬虫产出的统一结构）
# ------------------------------------------------------------

@dataclass
class CrawledJob:
    """一条标准化后的岗位数据（与数据库 jobs 表字段对应）"""

    company: str                # 公司名（如：字节跳动）
    company_category: str       # 公司类别：互联网大厂 / 大模型独角兽 / AI垂直龙头 / 国企AI
    job_title: str              # 岗位名
    job_type: str               # 岗位类型：AI算法 / AI工程 / AI产品 / AI应用 / 数据科学
    location: str               # 工作地（可能为空）
    salary_range: str           # 薪资区间（可能为空）
    publish_date: str           # JD 发布日 YYYY-MM-DD（可能为空）
    source_url: str             # JD 原文链接
    jd_raw_text: str            # JD 原文（去空白后的纯文本，供 LLM 结构化）
    external_job_id: str        # 站点内部的岗位 ID（用于生成稳定的 job_id）
    domain: str                 # 公司官方招聘域名（用于限速与 job_id 生成）


# ------------------------------------------------------------
# 爬虫基类
# ------------------------------------------------------------

class BaseSpider:
    """
    企业招聘页爬虫基类。
    子类必须设置 company / company_category / start_url，并实现两个 fetch 方法。
    """

    # ---------- 子类必须配置的类属性 ----------
    company: str = ""                 # 公司名
    company_category: str = ""        # 公司类别
    start_url: str = ""               # 招聘页入口 URL
    # 每日条数上限提示（基类统一从 config 读取，个别站点可覆盖）
    daily_limit: Optional[int] = None

    def __init__(self, use_playwright: bool = True):
        """
        :param use_playwright: 站点为 JS 渲染时传 True（启动浏览器）；
                               若站点有公开 JSON API 则子类可传 False 直接用 requests
        """
        self.use_playwright = use_playwright
        self.domain = extract_domain(self.start_url)
        self.rate_limiter = get_rate_limiter(self.domain)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self.logger = logger

    # ========================================================
    # 对外主入口：爬取该公司全部 AI 岗位
    # ========================================================

    def crawl(self) -> List[CrawledJob]:
        """
        爬取该公司当前可访问的所有 AI 相关岗位。
        流程：robots 检查 -> 列表页 -> 详情页 -> 返回标准化数据。
        任何单点失败都会降级（记日志跳过），不会中断整个任务。
        """
        self.logger.info("开始爬取 %s（%s）", self.company, self.start_url)

        # 1) robots.txt 合规检查（列表页路径）
        start_path = urlparse(self.start_url).path or "/"
        if not can_fetch(self.domain, start_path):
            self.logger.warning(
                "%s 的 robots.txt 禁止抓取 %s，降级为手动导入模式（详见 adapters/manual.py）",
                self.company, start_path,
            )
            return []

        jobs: List[CrawledJob] = []

        try:
            # 2) 获取岗位列表（job_key, detail_url）
            raw_list = self.fetch_job_list()
            if not raw_list:
                self.logger.warning("%s 列表为空或解析失败（站点可能改版）", self.company)
                return jobs
            self.logger.info("%s 列表共发现 %d 个岗位", self.company, len(raw_list))
        except Exception as exc:
            # 优雅降级：列表页失败记录日志，不抛异常（不中断整体任务）
            self.logger.error("%s 列表页获取失败（可能改版，请更新适配器选择器）：%s", self.company, exc)
            return jobs

        # 3) 逐条抓取详情（含限速 + 重试 + 优雅降级）
        for item in raw_list:
            # 额度检查：该域名今日已抓满则停止
            if not self.rate_limiter.can_fetch():
                self.logger.warning("%s 已达今日 %d 条上限，停止抓取", self.company, self.daily_limit or config.DAILY_MAX_JOBS_PER_DOMAIN)
                break

            try:
                job = self._fetch_one(item)
                if job is not None:
                    jobs.append(job)
                    self.rate_limiter.record_fetch()
            except RateLimitExceeded:
                break  # 额度用尽
            except Exception as exc:
                # 单条失败：记日志继续下一条（PRD 优雅降级要求）
                self.logger.error("%s 岗位详情获取失败 %s：%s", self.company, item, exc)
                continue

        self.logger.info(
            "%s 爬取完成：成功 %d 条（今日剩余额度 %d）",
            self.company, len(jobs), self.rate_limiter.remaining_today(),
        )
        return jobs

    # ========================================================
    # 子类必须实现的两个方法
    # ========================================================

    def fetch_job_list(self) -> List[dict]:
        """
        获取岗位列表。
        返回：[{"job_key": 站点内部ID, "url": 详情页URL, "title": 标题}, ...]
        页面为 JS 渲染时在此方法内启动 Playwright（参考 bytedance.py）。
        若站点有公开 API，也可以直接调用 API 返回 JSON。
        """
        raise NotImplementedError("子类必须实现 fetch_job_list()")

    def fetch_job_detail(self, url: str, job_key: str) -> Optional[dict]:
        """
        获取单条 JD 详情。
        返回 dict，至少包含：job_title / jd_raw_text / location / salary_range / publish_date
        页面为 JS 渲染时在此方法内使用 Playwright。
        """
        raise NotImplementedError("子类必须实现 fetch_job_detail()")

    # ========================================================
    # 基类提供的公共工具（子类可直接调用）
    # ========================================================

    def _fetch_one(self, item: dict) -> Optional[CrawledJob]:
        """抓取单条岗位并标准化（限速在 detail 内部请求时执行）"""
        detail = self.fetch_job_detail(item["url"], item["job_key"])
        if not detail or not detail.get("jd_raw_text"):
            return None

        jd_text = normalize_whitespace(detail.get("jd_raw_text", ""))
        if len(jd_text) < 30:
            # JD 文本过短，大概率是反爬占位页，跳过
            self.logger.debug("%s JD 文本过短，跳过：%s", self.company, item.get("title", ""))
            return None

        domain = self.domain
        job = CrawledJob(
            company=self.company,
            company_category=self.company_category,
            job_title=detail.get("job_title", item.get("title", "")).strip(),
            job_type="",  # 由 ai_filter 按标题/内容归类
            location=(detail.get("location") or "").strip(),
            salary_range=(detail.get("salary_range") or "").strip(),
            publish_date=(detail.get("publish_date") or "").strip(),
            source_url=item["url"],
            jd_raw_text=jd_text,
            external_job_id=item["job_key"],
            domain=domain,
        )
        return job

    # ---------- requests 请求（非 JS 页面 / JSON API）----------

    @retry_on_exception(extra_delay=config.CRAWL_INTERVAL_MIN)
    def http_get(self, url: str, timeout: int = 20, **kwargs) -> requests.Response:
        """带限速与重试的 GET 请求（robots 已在外层校验）"""
        with self.rate_limiter:
            resp = self.session.get(url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp

    @retry_on_exception(extra_delay=config.CRAWL_INTERVAL_MIN)
    def http_post(self, url: str, json: dict = None, timeout: int = 20, **kwargs) -> requests.Response:
        """带限速与重试的 POST 请求（mokahr / 字节等站点的 JSON API 使用）"""
        with self.rate_limiter:
            resp = self.session.post(url, json=json, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp

    # ---------- BeautifulSoup 解析工具 ----------

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        """将 HTML 字符串解析为 BeautifulSoup 对象"""
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def extract_text(node) -> str:
        """提取节点纯文本并去除多余空白"""
        return normalize_whitespace(node.get_text(" ", strip=True)) if node else ""

    # ---------- Playwright 页面工具（JS 渲染页使用）----------

    def fetch_page_html(self, url: str, wait_selector: str = None, wait_ms: int = 4000) -> Optional[str]:
        """
        用 Playwright 打开 JS 渲染页面并返回渲染后的 HTML。
        :param wait_selector: 等待某选择器出现（如 '.job-list'），出现后再提取
        :param wait_ms: 若未提供 wait_selector，则固定等待毫秒数
        返回 None 表示页面打开失败（调用方自行降级）。
        浏览器内核策略：优先 Playwright 自带 chromium；未安装时自动降级为
        系统已装的 Edge / Chrome（Windows 基本都有，免去下载内核）。
        """
        with self.rate_limiter:  # 每次页面加载同样计入限速
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = self._launch_browser(p)
                    page = browser.new_page(
                        user_agent=config.USER_AGENT,
                        viewport={"width": 1440, "height": 900},
                    )
                    try:
                        page.goto(url, timeout=config.PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
                        if wait_selector:
                            # 等待指定元素出现（最多 15 秒），超时不报错（页面可能没该元素）
                            try:
                                page.wait_for_selector(wait_selector, timeout=15000)
                            except Exception:
                                pass
                        else:
                            time.sleep(wait_ms / 1000.0)
                        # 额外滚动加载：部分站点列表懒加载，滚动几次触发加载
                        for _ in range(3):
                            page.mouse.wheel(0, 3000)
                            time.sleep(random.uniform(0.6, 1.2))
                        return page.content()
                    finally:
                        browser.close()
            except Exception as exc:
                self.logger.error("Playwright 页面加载失败 %s：%s", url, exc)
                return None

    @staticmethod
    def _launch_browser(p):
        """按可用性依次尝试：自带 chromium -> 系统 Edge -> 系统 Chrome"""
        channels = [None, "msedge", "chrome"]
        last_err = None
        for channel in channels:
            try:
                kwargs = {"headless": config.PLAYWRIGHT_HEADLESS}
                if channel:
                    kwargs["channel"] = channel
                return p.chromium.launch(**kwargs)
            except Exception as exc:
                last_err = exc
        raise last_err

    # ---------- 最终组装 ----------

    def build_job(self, external_job_id: str, source_url: str, title: str,
                  jd_text: str, location: str = "", salary: str = "", publish: str = "") -> CrawledJob:
        """子类解析完成后统一构建 CrawledJob（避免重复代码）"""
        return CrawledJob(
            company=self.company,
            company_category=self.company_category,
            job_title=title.strip(),
            job_type="",
            location=location.strip(),
            salary_range=salary.strip(),
            publish_date=publish.strip(),
            source_url=source_url,
            jd_raw_text=normalize_whitespace(jd_text),
            external_job_id=external_job_id,
            domain=self.domain,
        )
