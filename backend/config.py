# ============================================================
# 全局配置模块
# 所有可调参数集中在这里管理，避免散落在各文件中。
# 敏感信息（API Key 等）从根目录 .env 文件读取（不会提交到 git）。
# ============================================================

import os
from typing import Optional

from dotenv import load_dotenv

# 加载根目录下的 .env 文件（若不存在则静默跳过，使用默认值）
load_dotenv()

# ------------------------------------------------------------
# 爬虫合规配置（本项目最重要的约束，见 PRD「合规边界」）
# ------------------------------------------------------------

# 爬虫 User-Agent：必须明确标识项目名与联系方式，方便网站管理员联系
# 格式：{项目名}/{版本号} (+contact: {邮箱})
def _build_user_agent() -> str:
    """根据 .env 中的 CONTACT_EMAIL 构建合规的 User-Agent"""
    email: str = os.getenv("CONTACT_EMAIL", "").strip()
    if email:
        return f"AI-JD-Aggregator/1.0 (+contact: {email})"
    # 邮箱未配置时使用通用标识，避免暴露虚假联系方式
    return "AI-JD-Aggregator/1.0 (educational project, no personal data collected)"


USER_AGENT: str = _build_user_agent()

# 单域名每日抓取上限（条）：严格遵循 PRD 合规约束
DAILY_MAX_JOBS_PER_DOMAIN: int = int(os.getenv("DAILY_MAX_JOBS_PER_DOMAIN", "200"))

# 单次请求间隔（秒）：在区间内随机取值，避免固定节奏被识别为机器行为
CRAWL_INTERVAL_MIN: float = float(os.getenv("CRAWL_INTERVAL_MIN", "3"))
CRAWL_INTERVAL_MAX: float = float(os.getenv("CRAWL_INTERVAL_MAX", "5"))

# 浏览器启动参数：headless 无头模式（不弹出浏览器窗口）
PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

# 页面加载等待时间（秒）：给 JS 渲染留足时间
PAGE_LOAD_TIMEOUT_MS: int = 30000

# ------------------------------------------------------------
# LLM 配置（AI 结构化抽取）
# ------------------------------------------------------------

OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY") or None
# 默认 OpenAI 官方；可改为 DeepSeek（https://api.deepseek.com/v1）等兼容接口
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
# LLM 温度：结构化抽取任务希望输出稳定，温度设低
LLM_TEMPERATURE: float = 0.2
# 单次 LLM 调用超时（秒）
LLM_TIMEOUT_S: int = 90
# LLM 失败重试次数
LLM_MAX_RETRIES: int = 3

# ------------------------------------------------------------
# Supabase 数据库配置
# ------------------------------------------------------------

SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL") or None
# 服务端密钥：仅后端爬虫使用，绝不可暴露给前端
SUPABASE_SERVICE_ROLE_KEY: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or None

# ------------------------------------------------------------
# 告警配置（爬取失败时通知）
# ------------------------------------------------------------

FEISHU_WEBHOOK: Optional[str] = os.getenv("FEISHU_WEBHOOK") or None
SLACK_WEBHOOK: Optional[str] = os.getenv("SLACK_WEBHOOK") or None

# ------------------------------------------------------------
# 重试策略（网络抖动 / 站点反爬时自动重试）
# ------------------------------------------------------------

# 每次请求最大重试次数
REQUEST_MAX_RETRIES: int = 3
# 重试等待时间（秒）：按 2^n 指数退避，n 为第几次重试
REQUEST_BACKOFF_BASE: float = 5.0

# ------------------------------------------------------------
# 环境检测辅助函数
# ------------------------------------------------------------

def is_llm_configured() -> bool:
    """检查 LLM 是否已配置（未配置时跳过 enrichment 阶段，只爬取不结构化）"""
    return bool(OPENAI_API_KEY)

def is_supabase_configured() -> bool:
    """检查 Supabase 是否已配置（未配置时爬取结果写入本地 JSON，便于先跑通爬虫）"""
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
