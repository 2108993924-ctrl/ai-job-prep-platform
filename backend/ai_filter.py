# ============================================================
# AI 岗位过滤模块（Phase 1 核心逻辑之一）
#
# 职责：
#   1. 从爬取到的全部岗位中，过滤出 AI 相关岗位
#      （标题或 JD 文本命中 AI 关键词）
#   2. 为岗位归类 job_type（AI算法 / AI工程 / AI产品 / AI应用 / 数据科学）
#
# 过滤关键词覆盖 PRD 要求的：AI / 大模型 / LLM / 算法 / 智能体 /
# RAG / 多模态 / 机器学习，并补充常见的工程词（提示词、向量、AIGC）。
# ============================================================

import re
from typing import List, Optional

from crawler.base import CrawledJob
from utils import logger

# ------------------------------------------------------------
# AI 岗位过滤关键词（命中任一即视为 AI 岗位）
# 注意：词频高、范围宽（如"算法"），命中率由标题+正文双通道保证
# ------------------------------------------------------------

# 强关键词：标题命中即可判定（AI 特征明显）
STRONG_TITLE_KEYWORDS = [
    "AI", "人工智能", "大模型", "LLM", "AGI", "智能体", "Agent",
    "多模态", "AIGC", "机器学习", "深度学习", "CV", "NLP", "自然语言",
    "算法", "RAG", "检索增强", "提示词", "Prompt", "推理", "SFT",
    "LoRA", "微调", "向量", "Embedding", "Diffusion", "扩散模型",
    "生成式", "SLAM", "自动驾驶", "机器人", "推荐系统", "数据挖掘",
]

# 弱关键词：正文命中才判定（避免把"运营算法活动"误判为 AI 岗位）
WEAK_BODY_KEYWORDS = [
    "大模型", "多模态", "智能体", "AIGC", "机器学习", "深度学习",
    "自然语言", "LLM", "PyTorch", "Transformer", "提示词工程",
    "RAG", "检索增强生成", "模型训练", "模型推理", "LoRA",
]

# ------------------------------------------------------------
# job_type 归类关键词映射（按优先级从上到下匹配）
# ------------------------------------------------------------

JOB_TYPE_RULES = [
    # (job_type, 命中关键词列表)
    ("AI算法", ["算法", "机器学习", "深度学习", "研究", "模型训练", "多模态", "CV", "NLP", "自然语言", "大模型", "SLAM", "推荐", "数据挖掘", "预训练", "SFT"]),
    ("AI工程", ["开发工程师", "后端", "工程", "架构", "平台", "推理引擎", "部署", "MLOps", "Infra", "系统", "AI平台", "模型服务", "训练平台"]),
    ("AI产品", ["产品经理", "产品", "产品运营"]),
    ("AI应用", ["应用", "解决方案", "场景", "落地", "Prompt", "提示词", "智能体应用", "应用工程师", "Agent开发"]),
    ("数据科学", ["数据分析", "数据科学", "数据挖掘", "BI", "数据开发", "数仓", "统计"]),
]

# 岗位标题里的强词，优先用标题归类；标题不明确时再看正文
def _classify_job_type(title: str, jd_text: str) -> str:
    """根据标题与 JD 正文关键词，将岗位归入 PRD 定义的 5 类之一"""
    # 先看标题（标题信息密度高）
    text = title
    for job_type, keywords in JOB_TYPE_RULES:
        for kw in keywords:
            if kw in text:
                return job_type
    # 标题未命中再看正文前 2000 字（正文太长含噪声）
    text = jd_text[:2000]
    for job_type, keywords in JOB_TYPE_RULES:
        for kw in keywords:
            if kw in text:
                return job_type
    # 兜底：AI 岗位但无法细分（极少见）
    return "AI应用"


def is_ai_job(job: CrawledJob) -> bool:
    """
    判断岗位是否为 AI 相关岗位。
    策略：
      - 标题命中强关键词 -> 是 AI 岗位
      - 标题未命中但正文命中弱关键词 -> 是 AI 岗位
      - 两者都未命中 -> 不是 AI 岗位（丢弃）
    """
    title = job.job_title or ""
    jd_text = job.jd_raw_text or ""

    # 标题命中强关键词（大小写不敏感）
    for kw in STRONG_TITLE_KEYWORDS:
        if kw.lower() in title.lower():
            return True

    # 正文命中弱关键词（正文较长，只取前 3000 字符判断）
    body_head = jd_text[:3000].lower()
    for kw in WEAK_BODY_KEYWORDS:
        if kw.lower() in body_head:
            return True

    return False


def filter_and_classify(jobs: List[CrawledJob]) -> List[CrawledJob]:
    """
    过滤 + 归类主入口。
    输入：某公司爬取到的全部岗位
    输出：仅 AI 相关岗位，且已填充 job_type 字段
    """
    result: List[CrawledJob] = []
    dropped = 0
    for job in jobs:
        if not is_ai_job(job):
            dropped += 1
            continue
        job.job_type = _classify_job_type(job.job_title, job.jd_raw_text)
        result.append(job)

    logger.info(
        "AI 岗位过滤完成：%d 条命中（丢弃 %d 条非 AI 岗位）",
        len(result), dropped,
    )
    return result


def guess_job_type_from_title(title: str) -> Optional[str]:
    """仅凭标题快速归类（供前端展示兜底使用，后端入库以 filter_and_classify 为准）"""
    text = title or ""
    for job_type, keywords in JOB_TYPE_RULES:
        for kw in keywords:
            if kw in text:
                return job_type
    return None
