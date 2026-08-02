# ============================================================
# LLM 结构化抽取模块（Phase 2 核心，产品差异化价值所在）
#
# 对每条 JD 原文调用一次 LLM，输出：
#   project_requirements : 候选人应能独立完成的具体项目（列表）
#   tech_stack           : JD 明确要求的技术/框架/算法（列表）
#   business_domain      : 业务领域（电商/金融/机器人... 最多 2 个）
#   interview_questions  : 5 道针对性面试题（含参考答案）
#
# 缓存策略（PRD 要求）：
#   - 同一 JD 原文 hash 不变，绝不重复调用 LLM
#   - hash 变化（JD 被企业修改）才重新调用
# ============================================================

import json
import re
import time
from typing import Any, Dict, List, Optional

import config
from utils import logger, safe_json_loads

# ------------------------------------------------------------
# 业务领域枚举（PRD 数据模型定义）
# ------------------------------------------------------------

BUSINESS_DOMAINS = [
    "电商", "本地生活", "金融", "医疗", "内容", "机器人",
    "自动驾驶", "企业服务", "文娱", "教育", "智能硬件", "通用",
]

# 面试题维度（PRD 定义的五类）
QUESTION_CATEGORIES = ["基础原理", "大模型应用", "工程实现", "生产调优", "场景判断"]


# ------------------------------------------------------------
# Prompt 模板（PRD 第五节指定框架，不可随意改动核心结构）
# ------------------------------------------------------------

PROMPT_TEMPLATE = """你是一位资深 AI 应用工程师面试官。给定以下企业 JD 原文：
---
{jd_raw_text}
---
请输出 JSON，包含：
1. project_requirements: 字符串数组，每条描述"候选人应能独立完成的一个具体项目"，
   例如"基于企业文档的 RAG 问答系统，支持引用溯源"
2. tech_stack: 字符串数组，抽取 JD 中明确要求了解/掌握的技术、框架、算法
3. business_domain: 从下列枚举中选择最匹配的 1-2 个：{business_domains}
4. interview_questions: 5 道题的数组，每题覆盖不同维度
   （基础原理/大模型应用/工程实现/生产调优/场景判断），
   每题包含 question 与 reference_answer 字段
仅输出 JSON，不要解释。"""

# 输出 JSON 的字段结构校验（缺失的字段用默认值兜底）
_DEFAULT_RESULT = {
    "project_requirements": [],
    "tech_stack": [],
    "business_domain": [],
    "interview_questions": [],
}


# ------------------------------------------------------------
# 核心函数：单条 JD 的结构化抽取
# ------------------------------------------------------------

def enrich_jd(
    jd_raw_text: str,
    api_key: str = None,
    base_url: str = None,
    model: str = None,
) -> Optional[Dict[str, Any]]:
    """
    对一条 JD 原文调用 LLM，返回结构化结果。

    :param jd_raw_text: JD 原文（去空白后的纯文本）
    :param api_key:     OpenAI 兼容 API Key（默认取 config）
    :param base_url:    API 地址（默认取 config，可指向 DeepSeek 等兼容服务）
    :param model:       模型名（默认取 config）
    :return: {
        "project_requirements": [...],
        "tech_stack": [...],
        "business_domain": [...],
        "interview_questions": [{question, category, reference_answer}...],
    }
    :raises: 连续重试仍失败时返回 None（由调用方记录日志并跳过）
    """
    api_key = api_key or config.OPENAI_API_KEY
    base_url = base_url or config.OPENAI_BASE_URL
    model = model or config.LLM_MODEL

    if not api_key:
        logger.error("未配置 OPENAI_API_KEY，无法执行 JD 结构化")
        return None

    # 组装 prompt（PRD 指定框架 + 枚举注入）
    prompt = PROMPT_TEMPLATE.format(
        jd_raw_text=jd_raw_text[:8000],  # 截断超长 JD，避免 token 超限
        business_domains="、".join(BUSINESS_DOMAINS),
    )

    # 带重试调用（网络抖动 / 限流时指数退避）
    raw_output = _call_llm_with_retry(prompt, api_key, base_url, model)
    if raw_output is None:
        return None

    # 解析 LLM 输出（容错：可能带 ```json 包裹或多余文字）
    parsed = safe_json_loads(raw_output)
    if not isinstance(parsed, dict):
        logger.warning("LLM 输出无法解析为 JSON，已跳过：%s", str(raw_output)[:200])
        return None

    return _normalize_result(parsed)


# ------------------------------------------------------------
# LLM 调用与结果规范化
# ------------------------------------------------------------

def _call_llm_with_retry(prompt: str, api_key: str, base_url: str, model: str) -> Optional[str]:
    """
    调用 OpenAI 兼容 Chat Completions 接口，失败自动重试（指数退避）。
    """
    # 延迟导入 openai：未安装依赖时，至少能让爬虫部分正常工作
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("未安装 openai 库，请执行 pip install -r requirements.txt")
        return None

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=config.LLM_TIMEOUT_S)

    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=config.LLM_TEMPERATURE,
                messages=[
                    {"role": "system", "content": "你是严谨的 AI 招聘分析师，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
            )
            content = resp.choices[0].message.content
            if content:
                return content
        except Exception as exc:
            logger.warning(
                "LLM 调用失败（第 %d/%d 次）：%s，%.0f 秒后重试",
                attempt, config.LLM_MAX_RETRIES, exc, 2 ** attempt * 5,
            )
            time.sleep(2 ** attempt * 5)  # 5s, 10s, 20s 指数退避
    logger.error("LLM 调用连续 %d 次失败，放弃本条", config.LLM_MAX_RETRIES)
    return None


def _normalize_result(parsed: dict) -> Dict[str, Any]:
    """
    规范化 LLM 输出：
      - 缺失字段补默认值
      - 类型强转（防止 LLM 返回字符串而非数组）
      - 面试题补 category 字段（PRD 要求五维度，LLM 可能漏给）
      - 过滤异常条目（空字符串、过长文本等）
    """
    result: Dict[str, Any] = {
        "project_requirements": _to_string_list(parsed.get("project_requirements")),
        "tech_stack": _to_string_list(parsed.get("tech_stack")),
        "business_domain": _to_string_list(parsed.get("business_domain")),
        "interview_questions": _normalize_questions(parsed.get("interview_questions")),
    }
    # 限制长度，防止 LLM 输出失控
    result["project_requirements"] = result["project_requirements"][:10]
    result["tech_stack"] = result["tech_stack"][:20]
    result["business_domain"] = result["business_domain"][:2]
    result["interview_questions"] = result["interview_questions"][:5]
    return result


def _to_string_list(value: Any) -> List[str]:
    """将任意值转为字符串数组（LLM 偶尔把数组写成逗号分隔字符串）"""
    if value is None:
        return []
    if isinstance(value, list):
        # 过滤 None 与空字符串（str(None) 为 'None'，必须先判 None）
        items = [str(v).strip() for v in value if v is not None and str(v).strip()]
        return items
    if isinstance(value, str):
        # 尝试 JSON 字符串数组；失败则按逗号/分号/换行拆分
        parsed = safe_json_loads(value)
        if isinstance(parsed, list):
            return _to_string_list(parsed)
        parts = re.split(r"[,;，；\n]+", value)
        return [v.strip() for v in parts if v.strip()]
    return []


def _normalize_questions(value: Any) -> List[Dict[str, str]]:
    """规范化面试题数组：每道题至少含 question 与 reference_answer，并补 category"""
    if not isinstance(value, list):
        return []
    # 五种维度循环分配（LLM 漏标 category 时按顺序补全）
    questions: List[Dict[str, str]] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("reference_answer", item.get("answer", ""))).strip()
        if not question:
            continue
        category = str(item.get("category", "")).strip()
        if not category or category not in QUESTION_CATEGORIES:
            # 按五维度顺序补全缺失的类别标签
            category = QUESTION_CATEGORIES[idx % len(QUESTION_CATEGORIES)]
        questions.append({
            "question": question,
            "category": category,
            "reference_answer": answer,
        })
    return questions
