# ============================================================
# 通用工具模块
# 提供：日志初始化、哈希计算、网络重试装饰器、Webhook 告警
# ============================================================

import hashlib
import json
import logging
import random
import sys
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

import requests

from config import (
    FEISHU_WEBHOOK,
    REQUEST_BACKOFF_BASE,
    REQUEST_MAX_RETRIES,
    SLACK_WEBHOOK,
)

# ------------------------------------------------------------
# 日志初始化
# ------------------------------------------------------------

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    初始化全局日志，输出格式带时间与级别，便于排查爬取问题。
    - INFO  : 正常流程记录（开始爬取某公司、入库 N 条等）
    - WARNING: 可恢复异常（某站点禁用爬取、某条 JD 解析失败）
    - ERROR : 严重问题（整站爬取失败），会触发告警通知
    """
    logger = logging.getLogger("ai_jd_aggregator")
    # 避免重复添加 handler（模块被多次 import 时）
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# 全局唯一 logger，各模块直接 from utils import logger 使用
logger = setup_logging()


# ------------------------------------------------------------
# 哈希工具（用于 job_id 与 JD 原文指纹）
# ------------------------------------------------------------

def hash_text(text: str, length: int = 16) -> str:
    """
    对任意文本计算短哈希（SHA-256 前 length 位）。
    用途一：job_id = 公司域名 + 岗位ID 拼接后哈希，保证同一岗位 ID 稳定
    用途二：jd_hash = JD 原文哈希，用于增量更新时判断 JD 是否变化
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:length]


def compute_job_id(company_domain: str, external_job_id: str) -> str:
    """生成稳定的岗位唯一 ID：域名 + 站点内部岗位 ID 共同决定"""
    return hash_text(f"{company_domain}|{external_job_id}")


def compute_jd_hash(jd_raw_text: str) -> str:
    """计算 JD 原文指纹：原文一字不变则指纹不变，用于跳过 LLM 重复调用"""
    return hash_text(jd_raw_text, length=32)


# ------------------------------------------------------------
# 网络重试装饰器（指数退避）
# ------------------------------------------------------------

def retry_on_exception(
    max_retries: int = REQUEST_MAX_RETRIES,
    backoff_base: float = REQUEST_BACKOFF_BASE,
    retryable_exceptions: tuple = (requests.RequestException, TimeoutError, ConnectionError),
    extra_delay: float = 0.0,
):
    """
    网络请求重试装饰器。
    行为：失败后等待 backoff_base * 2^n 秒再试（n 为失败次数），
    超过 max_retries 次后抛出最后一次异常。
    参数 extra_delay 用于叠加合规限速（请求间隔 3~5 秒），
    保证「每次请求」之间都有合规间隔。
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                # 1) 合规限速：每次真实请求前随机等待 extra_delay（3~5 秒）
                if extra_delay > 0 and attempt == 0:
                    time.sleep(random.uniform(0, extra_delay))
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    attempt += 1
                    if attempt > max_retries:
                        # 重试耗尽，抛出异常由上层记录并告警
                        raise exc
                    wait_time = backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        "请求失败（第 %d/%d 次）：%s，%.1f 秒后重试",
                        attempt, max_retries, exc, wait_time,
                    )
                    time.sleep(wait_time)
        return wrapper

    return decorator


# ------------------------------------------------------------
# 告警通知（飞书 / Slack Webhook）
# ------------------------------------------------------------

def send_alert(title: str, message: str) -> None:
    """
    发送告警到已配置的 Webhook（飞书优先，其次 Slack）。
    两者都未配置时仅记录日志——保证本地开发不报错。
    """
    if FEISHU_WEBHOOK:
        _send_feishu(FEISHU_WEBHOOK, title, message)
    elif SLACK_WEBHOOK:
        _send_slack(SLACK_WEBHOOK, title, message)
    else:
        logger.warning("[告警未送达（未配置 webhook）] %s: %s", title, message)


def _send_feishu(webhook: str, title: str, message: str) -> None:
    """发送飞书自定义机器人消息（text 类型，最多 30KB）"""
    payload: Dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": f"{title}\n{message}"},
    }
    try:
        resp = requests.post(webhook, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("飞书告警已发送")
    except Exception as exc:  # 告警失败不影响主流程
        logger.error("飞书告警发送失败：%s", exc)


def _send_slack(webhook: str, title: str, message: str) -> None:
    """发送 Slack Incoming Webhook 消息"""
    payload: Dict[str, Any] = {"text": f"*{title}*\n{message}"}
    try:
        resp = requests.post(webhook, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Slack 告警已发送")
    except Exception as exc:
        logger.error("Slack 告警发送失败：%s", exc)


# ------------------------------------------------------------
# 文本清理工具
# ------------------------------------------------------------

def normalize_whitespace(text: str) -> str:
    """
    清理 JD 文本中的空白：合并连续空白、去除首尾空白。
    JD 原文常带大量换行缩进，入库前统一规范化，便于 LLM 阅读与 hash 比对。
    """
    if not text:
        return ""
    # 先把 \r\n 统一成 \n，再合并多余空白
    import re
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_json_loads(text: str) -> Optional[Any]:
    """
    安全解析 JSON：LLM 输出偶尔会带 ```json 代码块包裹或前后说明文字，
    这里做容错处理，解析失败返回 None。
    """
    if not text:
        return None
    text = text.strip()
    # 去除 ```json ... ``` 代码块包裹
    if text.startswith("```"):
        text = text.strip("`")
        text = text.strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试截取第一个 { 到最后一个 } 之间的内容
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None
