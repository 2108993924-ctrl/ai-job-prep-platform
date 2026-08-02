# ============================================================
# adapters 包：每个文件对应一家（或一类）企业的官方招聘页适配器
#
# 新增公司的步骤（详见 README「如何扩展公司清单」）：
#   1. 在 adapters/ 下新建 xxx.py，继承 crawler.base.BaseSpider
#   2. 配置 company / company_category / start_url
#   3. 实现 fetch_job_list() 与 fetch_job_detail()
#   4. 在下方 REGISTRY 字典注册（key 为任意唯一 id）
# ============================================================

from typing import Dict, List, Type

from crawler.base import BaseSpider

# 公司适配器注册表：{适配器 id: 适配器类}
# 运行时按此清单顺序逐个爬取；某家失败不会影响其他家（优雅降级）
REGISTRY: Dict[str, Type[BaseSpider]] = {}


def register(adapter_id: str):
    """装饰器：把适配器类注册到 REGISTRY"""
    def _wrap(cls: Type[BaseSpider]) -> Type[BaseSpider]:
        REGISTRY[adapter_id] = cls
        return cls
    return _wrap


def get_all_spiders(adapter_ids: List[str] = None) -> List[BaseSpider]:
    """
    实例化全部（或指定）适配器。
    :param adapter_ids: 只运行指定 id（用于调试，如只爬字节跳动）；None 表示全部
    """
    ids = adapter_ids if adapter_ids else list(REGISTRY.keys())
    spiders = []
    for aid in ids:
        cls = REGISTRY.get(aid)
        if cls is None:
            continue
        try:
            spiders.append(cls())
        except Exception as exc:
            # 某家初始化失败不影响整体
            from utils import logger
            logger.error("适配器 %s 初始化失败：%s", aid, exc)
    return spiders


# 导入并注册各企业适配器（顺序即执行顺序）
from crawler.adapters import bytedance, tencent, meituan  # noqa: F401,E402
from crawler.adapters import mokahr  # noqa: F401,E402
from crawler.adapters import official_site  # noqa: F401,E402（MiniMax/智谱AI/科大讯飞）
from crawler.adapters import manual  # noqa: F401,E402
