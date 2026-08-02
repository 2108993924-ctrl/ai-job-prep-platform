# ============================================================
# 冒烟测试：验证核心模块功能（不访问网络、不调用 LLM）
# 运行：python smoke_test.py
# ============================================================

import sys
import os

# 让 backend 目录可导入
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

passed = 0
failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [OK] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {detail}")

print("=== 1. 哈希工具 ===")
from utils import hash_text, compute_job_id, compute_jd_hash, normalize_whitespace
check("hash 稳定", hash_text("abc") == hash_text("abc"))
check("hash 不同", hash_text("abc") != hash_text("abd"))
check("job_id 稳定", compute_job_id("a.com", "123") == compute_job_id("a.com", "123"))
check("jd_hash 不同文本不同", compute_jd_hash("x") != compute_jd_hash("y"))
check("空白规范化", normalize_whitespace("  a\r\n\r\n\r\n  b  ") == "a\n\n b")

print("=== 2. AI 岗位过滤 ===")
from crawler.base import CrawledJob
from ai_filter import filter_and_classify, is_ai_job

j1 = CrawledJob(company="字节跳动", company_category="互联网大厂", job_title="大模型算法工程师",
                job_type="", location="北京", salary_range="", publish_date="", source_url="u1",
                jd_raw_text="负责大模型训练与推理优化，掌握 PyTorch、LoRA 微调。", external_job_id="1", domain="jobs.bytedance.com")
j2 = CrawledJob(company="腾讯", company_category="互联网大厂", job_title="产品运营",
                job_type="", location="", salary_range="", publish_date="", source_url="u2",
                jd_raw_text="负责社区活动运营与用户增长，策划线上活动。", external_job_id="2", domain="hr.tencent.com")
check("标题命中 AI 关键词", is_ai_job(j1))
check("非 AI 岗位被过滤", not is_ai_job(j2))
filtered = filter_and_classify([j1, j2])
check("过滤后仅剩 1 条", len(filtered) == 1)
check("job_type 归类为 AI算法", filtered[0].job_type == "AI算法")

print("=== 3. LLM 结果规范化 ===")
from enrichment.llm import _normalize_result, _to_string_list
result = _normalize_result({
    "project_requirements": ["基于企业文档的 RAG 问答系统，支持引用溯源", "", None],
    "tech_stack": "PyTorch, LoRA, 向量数据库",  # 模拟 LLM 输出字符串
    "business_domain": ["企业服务", "金融"],
    "interview_questions": [
        {"question": "Q1", "reference_answer": "A1"},          # 缺 category，应补全
        {"question": "Q2", "reference_answer": "A2", "category": "基础原理"},
        {"question": "Q3", "reference_answer": "A3", "category": "生产调优"},
        {"question": "Q4", "reference_answer": "A4", "category": "场景判断"},
        {"question": "Q5", "reference_answer": "A5", "category": "大模型应用"},
        {"question": "Q6", "reference_answer": "A6"},          # 超过 5 题应截断
    ],
})
check("project_requirements 过滤空值", len(result["project_requirements"]) == 1)
check("tech_stack 字符串转数组", result["tech_stack"] == ["PyTorch", "LoRA", "向量数据库"])
check("面试题截断为 5 题", len(result["interview_questions"]) == 5)
check("缺失 category 自动补全", result["interview_questions"][0]["category"] in ("基础原理","大模型应用","工程实现","生产调优","场景判断"))

print("=== 4. 适配器注册表 ===")
from crawler.adapters import REGISTRY, get_all_spiders
print(f"  已注册适配器: {list(REGISTRY.keys())}")
# mokahr_generic 是抽象基类（org_path 为空，需子类覆盖），不应直接实例化
spiders = get_all_spiders([aid for aid in REGISTRY if aid != "mokahr_generic"])
check("除抽象基类外全部可实例化", len(spiders) == len(REGISTRY) - 1)
check("注册了 8+ 个适配器", len(REGISTRY) >= 8)

print("=== 5. 手动导入（无文件时优雅返回空）===")
from crawler.adapters.manual import ManualImportSpider
m = ManualImportSpider()
jobs = m.crawl()
check("无数据文件返回空列表", jobs == [])

print("=== 6. 本地存储降级模式 ===")
from storage.supabase_store import JobStore
store = JobStore()
sample = {
    "job_id": "test_job_1",
    "company": "测试公司",
    "company_category": "互联网大厂",
    "job_title": "AI算法工程师",
    "job_type": "AI算法",
    "salary_range": "",
    "location": "北京",
    "publish_date": "2026-08-01",
    "crawl_time": "2026-08-02T00:00:00Z",
    "source_url": "https://example.com/job/1",
    "jd_raw_text": "负责大模型算法研发，熟练 PyTorch，有 RAG 经验优先。",
    "jd_hash": "hash1",
    "project_requirements": [],
    "tech_stack": [],
    "business_domain": [],
    "interview_questions": [],
    "needs_enrichment": True,
    "is_active": True,
}
stats1 = store.sync_jobs([sample])
check("首次同步插入 1 条", stats1["inserted"] == 1)
pending = store.get_jobs_needing_enrichment()
check("待结构化 1 条", len(pending) == 1)
ok = store.save_enrichment("test_job_1", {"project_requirements": ["RAG 系统"], "tech_stack": ["PyTorch"], "business_domain": [], "interview_questions": []})
check("回写结构化成功", ok)
pending2 = store.get_jobs_needing_enrichment()
check("回写后无待处理", len(pending2) == 0)
# 相同 hash 再次同步：不应重复插入
stats2 = store.sync_jobs([sample])
check("重复同步 unchanged=1", stats2["unchanged"] == 1 and stats2["inserted"] == 0)
# JD 变化后重新同步：应更新并重新标记结构化
sample["jd_hash"] = "hash2"
sample["jd_raw_text"] = "改版后的 JD 文本，要求掌握 Transformer 架构。"
stats3 = store.sync_jobs([sample])
check("JD 变化触发更新", stats3["updated"] == 1)
check("JD 变化重新标记结构化", len(store.get_jobs_needing_enrichment()) == 1)
# 清理测试数据
os.remove(os.path.join("data", "local_store.json")) if os.path.exists(os.path.join("data", "local_store.json")) else None
print("  已清理测试数据")

print()
print(f"===== 结果：{passed} 通过 / {failed} 失败 =====")
sys.exit(1 if failed else 0)
