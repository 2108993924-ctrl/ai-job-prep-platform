# ============================================================
# robots.txt 合规检查模块（PRD「合规边界」第 1 条）
#
# 规则：
#   1. 每个域名只探测一次 /robots.txt 并缓存 24 小时
#   2. 匹配我们的 User-Agent（或 * 通配）下的 Disallow 规则
#   3. 路径被 Disallow 时，爬虫必须跳过该路径
#   4. 尊重 Crawl-delay 指令（若比我们的限速更严格则采用站点要求）
# ============================================================

import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from urllib.robotparser import RobotFileParser

import config
from utils import logger

# 内存缓存：域名 -> (检查时间戳, 规则解析器)
# 每次运行只探测一次 robots.txt，避免频繁请求
_robots_cache: Dict[str, Tuple[float, RobotFileParser]] = {}

# robots.txt 缓存有效期（秒）：24 小时
_CACHE_TTL_SECONDS: int = 24 * 60 * 60


class RobotsTxtError(Exception):
    """robots.txt 获取失败（网络问题 / 非 200），按「无法确认允许则保守跳过」处理"""


def _get_robots_parser(domain: str) -> RobotFileParser:
    """
    获取某个域名的 robots 解析器（带缓存）。
    域名统一转为小写；若域名无合法结构则抛出异常。
    """
    domain = domain.lower()
    now = time.time()

    # 命中缓存且未过期，直接返回
    cached = _robots_cache.get(domain)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    robots_url = f"https://{domain}/robots.txt"
    try:
        # 使用标准 requests 探测 robots.txt（轻量，不启动浏览器）
        resp = requests.get(
            robots_url,
            headers={
                "User-Agent": config.USER_AGENT,
                "Accept": "text/plain",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RobotsTxtError(f"robots.txt 获取失败 {robots_url}: {exc}") from exc

    parser = RobotFileParser()
    if resp.status_code == 200:
        # 有些服务器对 text/plain 返回 HTML 错误页，仍按文本解析即可
        parser.parse(resp.text.splitlines())
    else:
        # 404 表示站点未提供 robots.txt：按惯例视为「允许」，但不记录缓存过久
        # 仍缓存，避免每次请求都重试
        parser.parse([])
        logger.info("域名 %s 无 robots.txt（HTTP %d），视为全部允许", domain, resp.status_code)

    _robots_cache[domain] = (now, parser)
    logger.info("已加载 %s 的 robots.txt 规则", domain)
    return parser


def can_fetch(domain: str, path: str) -> bool:
    """
    判断目标路径是否允许抓取。
    返回 False 的情况：
      - robots.txt 获取失败（保守策略：不确定就禁止）
      - 该路径被 Disallow
    """
    try:
        parser = _get_robots_parser(domain)
    except RobotsTxtError as exc:
        logger.warning("robots.txt 不可用，保守跳过 %s%s：%s", domain, path, exc)
        return False

    # RobotFileParser.can_fetch 依据我们构造的 User-Agent 匹配规则（含 * 通配）
    return parser.can_fetch(config.USER_AGENT, path)


def get_crawl_delay(domain: str) -> float:
    """
    读取站点要求的 Crawl-delay（秒）。
    若站点未声明，返回我们的默认下限 CRAWL_INTERVAL_MIN。
    若站点声明的间隔比我们更严格（更大），则采用站点值——合规优先。
    """
    try:
        parser = _get_robots_parser(domain)
    except RobotsTxtError:
        return config.CRAWL_INTERVAL_MIN

    delay = parser.crawl_delay(config.USER_AGENT)
    if delay is None:
        # 针对具体 UA 未声明时，尝试通配规则
        delay = parser.crawl_delay("*")
    if delay is None:
        return config.CRAWL_INTERVAL_MIN
    return max(float(delay), config.CRAWL_INTERVAL_MIN)


def extract_domain(url: str) -> str:
    """从 URL 提取域名（不含端口），如 https://jobs.bytedance.com/xxx -> jobs.bytedance.com"""
    return urlparse(url).netloc.lower().split(":")[0]
