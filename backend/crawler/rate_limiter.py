# ============================================================
# 速率限制器（PRD「合规边界」第 2 条）
#
# 双层限制：
#   1. 间隔限制：同一域名两次请求之间至少间隔 random(3, 5) 秒
#   2. 数量限制：同一域名每日抓取条数 ≤ DAILY_MAX_JOBS_PER_DOMAIN（默认 200）
#
# 实现为按域名隔离的记账对象，适配器通过 with RateLimiter(domain) 使用，
# 配合 robots.get_crawl_delay 取站点声明的更严格值。
# ============================================================

import random
import threading
import time
from typing import Dict

import config
from utils import logger


class RateLimiter:
    """按域名限速的记账对象（线程安全）"""

    def __init__(self, domain: str, min_interval: float = None, max_interval: float = None, daily_limit: int = None):
        """
        :param domain: 目标域名（小写）
        :param min_interval: 最小请求间隔（秒），默认取 config
        :param max_interval: 最大请求间隔（秒），默认取 config
        :param daily_limit: 单域名每日抓取上限，默认取 config
        """
        self.domain = domain.lower()
        self.min_interval = min_interval or config.CRAWL_INTERVAL_MIN
        self.max_interval = max_interval or config.CRAWL_INTERVAL_MAX
        self.daily_limit = daily_limit or config.DAILY_MAX_JOBS_PER_DOMAIN

        # 上次请求时间戳（0 表示从未请求过）
        self._last_request_at: float = 0.0
        # 今日已抓取条数
        self._fetched_count: int = 0
        # 当日日期字符串（YYYY-MM-DD），跨天自动清零
        self._today: str = time.strftime("%Y-%m-%d")
        # 线程锁：GitHub Actions 单线程运行，这里加锁保证本地多线程调试安全
        self._lock = threading.Lock()

    def wait_if_needed(self) -> None:
        """
        请求前调用：若距上次请求不足间隔，则补足等待。
        间隔在 [min_interval, max_interval] 内随机取，避免固定节奏。
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_at
            # 随机间隔：每次取不同值，更像真人浏览
            interval = random.uniform(self.min_interval, self.max_interval)
            if elapsed < interval:
                sleep_time = interval - elapsed
                logger.debug(
                    "限速：等待 %.1f 秒（%s 当前间隔 %.1f 秒）",
                    sleep_time, self.domain, interval,
                )
                time.sleep(sleep_time)
            self._last_request_at = time.time()

    def can_fetch(self) -> bool:
        """
        检查今日是否还有抓取额度（条数上限）。
        跨天时自动重置计数。
        """
        with self._lock:
            today = time.strftime("%Y-%m-%d")
            if today != self._today:
                # 新的一天：清零计数与时间戳
                self._today = today
                self._fetched_count = 0
                self._last_request_at = 0.0
            return self._fetched_count < self.daily_limit

    def record_fetch(self) -> None:
        """成功抓取一条后调用，累计当日计数"""
        with self._lock:
            self._fetched_count += 1

    def remaining_today(self) -> int:
        """返回今日剩余额度，便于日志展示"""
        with self._lock:
            return max(0, self.daily_limit - self._fetched_count)

    def __enter__(self) -> "RateLimiter":
        """with 语法入口：自动检查额度"""
        if not self.can_fetch():
            raise RateLimitExceeded(
                f"{self.domain} 今日抓取已超过上限 {self.daily_limit} 条，跳过"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """with 语法出口：请求前补足间隔（无论成败都执行）"""
        self.wait_if_needed()
        # 返回 False：异常继续向上传播
        return False


# 全局限速器注册表：域名 -> RateLimiter（单例，跨适配器共享计数）
_limiters: Dict[str, RateLimiter] = {}


def get_rate_limiter(domain: str) -> RateLimiter:
    """获取某个域名的限速器（同一域名全局共享一个，保证计数准确）"""
    domain = domain.lower()
    if domain not in _limiters:
        _limiters[domain] = RateLimiter(domain)
    return _limiters[domain]


class RateLimitExceeded(Exception):
    """今日额度用尽，应停止该域名的抓取并继续下一个域名"""
