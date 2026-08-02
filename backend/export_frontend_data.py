# ============================================================
# 将本地爬取数据导出为前端可用的静态 JSON
#
# 前端未配置 Supabase 时，页面会从 /data/jobs.json 读取数据，
# 本地预览无需数据库。每次爬取后运行本脚本即可刷新前端数据：
#     python backend/export_frontend_data.py
# ============================================================

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "local_store.json"
DST = ROOT / "frontend" / "public" / "data" / "jobs.json"


def main() -> None:
    if not SRC.exists():
        print(f"未找到 {SRC}，请先运行爬虫（python backend/main.py）")
        return
    data = json.loads(SRC.read_text(encoding="utf-8"))
    jobs = list(data.values()) if isinstance(data, dict) else data
    # 按最近抓取时间倒序（前端默认展示最新）
    jobs.sort(key=lambda j: j.get("crawl_time", ""), reverse=True)
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已导出 {len(jobs)} 条岗位 -> {DST}")


if __name__ == "__main__":
    main()
