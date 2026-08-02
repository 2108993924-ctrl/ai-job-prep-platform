# ============================================================
# 存储层：Supabase（正式）+ 本地 JSON（降级）
#
# 职责：
#   1. upsert 岗位（增量更新：同 job_id 比对 jd_hash，变化才更新）
#   2. 查询需要 AI 结构化的岗位（新插入 / JD 有变化的）
#   3. 回写结构化结果
#   4. 记录爬取日志
#
# 降级策略（新手友好）：
#   未配置 SUPABASE_URL 时自动使用本地 JSON 文件（data/local_store.json），
#   先跑通爬虫 + enrichment，配置好 Supabase 后自动切换，无需改代码。
# ============================================================

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import config
from utils import compute_jd_hash, compute_job_id, logger


class JobStore:
    """
    岗位数据存储接口（Supabase 实现）。
    所有方法都有本地 JSON 降级版本，保证未配置数据库也能完整跑通。
    """

    def __init__(self):
        self._supabase = None
        # 本地降级数据统一存放在项目根目录 data/ 下（与手动导入文件同目录）
        self._local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "local_store.json",
        )
        self._local_data: Dict[str, dict] = self._load_local()
        self._using_local = not config.is_supabase_configured()
        if not self._using_local:
            self._init_supabase()

    # --------------------------------------------------------
    # 初始化
    # --------------------------------------------------------

    def _init_supabase(self) -> None:
        """初始化 Supabase 客户端（连接失败时降级为本地 JSON）"""
        try:
            from supabase import create_client
            self._supabase = create_client(
                config.SUPABASE_URL,
                config.SUPABASE_SERVICE_ROLE_KEY,
            )
            logger.info("已连接 Supabase：%s", config.SUPABASE_URL)
        except Exception as exc:
            logger.error("Supabase 连接失败，降级为本地 JSON 存储：%s", exc)
            self._using_local = True

    def _load_local(self) -> Dict[str, dict]:
        """加载本地 JSON 数据（不存在则返回空字典）"""
        if os.path.exists(self._local_path):
            try:
                with open(self._local_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_local(self) -> None:
        """保存本地 JSON 数据"""
        os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
        with open(self._local_path, "w", encoding="utf-8") as f:
            json.dump(self._local_data, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------
    # 核心：批量同步岗位（增量更新核心逻辑）
    # --------------------------------------------------------

    def sync_jobs(self, jobs: List[dict]) -> Dict[str, int]:
        """
        同步一批岗位到存储：
        - 新岗位  -> 插入（is_active=true, needs_enrichment=true）
        - 已有且 JD 未变 -> 跳过（不更新，不重复调用 LLM）
        - 已有且 JD 变化 -> 更新原文并标记 needs_enrichment=true

        :param jobs: 标准化的岗位 dict 列表（含 job_id/jd_hash 等）
        :return: {"inserted": n, "updated": n, "unchanged": n}
        """
        if self._using_local:
            return self._sync_local(jobs)
        return self._sync_supabase(jobs)

    def _sync_local(self, jobs: List[dict]) -> Dict[str, int]:
        """本地 JSON 版本的增量同步"""
        inserted = updated = unchanged = 0
        for job in jobs:
            job_id = job["job_id"]
            existing = self._local_data.get(job_id)
            if existing is None:
                # 新岗位：完整写入（存副本，避免外部修改本 dict 影响已存数据）
                job["is_active"] = True
                job["needs_enrichment"] = True
                job["crawl_time"] = datetime.now(timezone.utc).isoformat()
                self._local_data[job_id] = dict(job)
                inserted += 1
            elif existing.get("jd_hash") != job["jd_hash"]:
                # JD 原文变化：更新基础字段并标记重新结构化
                job["is_active"] = True
                job["needs_enrichment"] = True
                job["crawl_time"] = datetime.now(timezone.utc).isoformat()
                # 保留已生成的结构化结果字段（由 enrichment 阶段决定是否重算）
                for key in ("project_requirements", "tech_stack", "business_domain", "interview_questions"):
                    if key in existing:
                        job[key] = existing[key]
                self._local_data[job_id] = dict(job)
                updated += 1
            else:
                # JD 未变化：仅刷新活跃状态与抓取时间
                existing["is_active"] = True
                existing["crawl_time"] = datetime.now(timezone.utc).isoformat()
                unchanged += 1
        self._save_local()
        logger.info("本地同步：新增 %d / 更新 %d / 未变 %d", inserted, updated, unchanged)
        return {"inserted": inserted, "updated": updated, "unchanged": unchanged}

    def _sync_supabase(self, jobs: List[dict]) -> Dict[str, int]:
        """Supabase 版本：先查现有 hash，再分批 upsert"""
        inserted = updated = unchanged = 0
        # 1) 查询现有岗位的 hash 映射（job_id -> jd_hash）
        existing_hashes: Dict[str, str] = {}
        try:
            # 分页拉取全部（每日 200 条上限下，总量可控）
            offset = 0
            page_size = 1000
            while True:
                resp = self._supabase.table("jobs").select("job_id, jd_hash").range(offset, offset + page_size - 1).execute()
                rows = resp.data or []
                for row in rows:
                    existing_hashes[row["job_id"]] = row["jd_hash"]
                if len(rows) < page_size:
                    break
                offset += page_size
        except Exception as exc:
            logger.error("查询现有岗位失败：%s", exc)
            return {"inserted": 0, "updated": 0, "unchanged": 0}

        # 2) 分类
        to_insert: List[dict] = []
        to_update: List[dict] = []
        for job in jobs:
            job_id = job["job_id"]
            if job_id not in existing_hashes:
                to_insert.append(job)
                inserted += 1
            elif existing_hashes[job_id] != job["jd_hash"]:
                to_update.append(job)
                updated += 1
            else:
                unchanged += 1

        # 3) 批量写入（upsert 按 job_id 主键冲突则更新）
        rows_to_write = to_insert + to_update
        for i in range(0, len(rows_to_write), 100):  # 每次最多 100 条，避免请求体过大
            batch = rows_to_write[i : i + 100]
            try:
                self._supabase.table("jobs").upsert(batch).execute()
            except Exception as exc:
                logger.error("批量写入失败（%d 条）：%s", len(batch), exc)
        logger.info("Supabase 同步：新增 %d / 更新 %d / 未变 %d", inserted, updated, unchanged)
        return {"inserted": inserted, "updated": updated, "unchanged": unchanged}

    # --------------------------------------------------------
    # 查询需要 AI 结构化的岗位
    # --------------------------------------------------------

    def get_jobs_needing_enrichment(self, limit: int = 50) -> List[dict]:
        """返回 needs_enrichment=true 的岗位（新插入或 JD 有变化的），最多 limit 条"""
        if self._using_local:
            result = [j for j in self._local_data.values() if j.get("needs_enrichment")]
            return result[:limit]
        try:
            resp = (
                self._supabase.table("jobs")
                .select("job_id, jd_raw_text")
                .eq("needs_enrichment", True)
                .limit(limit)
                .execute()
            )
            return resp.data or []
        except Exception as exc:
            logger.error("查询待结构化岗位失败：%s", exc)
            return []

    # --------------------------------------------------------
    # 回写 AI 结构化结果
    # --------------------------------------------------------

    def save_enrichment(self, job_id: str, enriched: dict) -> bool:
        """将 enrich_jd() 的结构化结果写回，并清除 needs_enrichment 标记"""
        now = datetime.now(timezone.utc).isoformat()
        payload = dict(enriched)
        payload["enriched_at"] = now
        payload["needs_enrichment"] = False

        if self._using_local:
            job = self._local_data.get(job_id)
            if job is None:
                return False
            job.update(payload)
            self._save_local()
            return True

        try:
            self._supabase.table("jobs").update(payload).eq("job_id", job_id).execute()
            return True
        except Exception as exc:
            logger.error("回写结构化结果失败（%s）：%s", job_id, exc)
            return False

    # --------------------------------------------------------
    # 爬取日志（便于排查问题）
    # --------------------------------------------------------

    def log_crawl(self, company: str, status: str, message: str = "") -> None:
        """记录一次公司爬取的结果日志（status: success / failed / skipped）"""
        entry = {
            "company": company,
            "status": status,
            "message": message[:500],
            "crawl_time": datetime.now(timezone.utc).isoformat(),
        }
        if self._using_local:
            # 本地日志直接打印（数据量小，不落盘）
            logger.info("[爬取日志] %s %s %s", company, status, message)
            return
        try:
            self._supabase.table("crawl_logs").insert(entry).execute()
        except Exception as exc:
            logger.warning("爬取日志写入失败：%s", exc)
