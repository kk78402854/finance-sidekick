"""
FAQ 种子数据初始化。

首次启动且 faq_items 为空时，从 seeds/faq_items.json 导入默认问答，
让知识检索在未接入外部 RAG 的情况下也能直接工作。
重复启动不会重复写入。
"""
import json
import logging
from pathlib import Path

from sqlalchemy import func, select

from assistant.repository.orm.faq import FaqItemRecord

logger = logging.getLogger(__name__)

# finance-assistant/seeds/faq_items.json
SEED_FILE = Path(__file__).parents[2] / "seeds" / "faq_items.json"


async def seed_default_faqs() -> int:
    """表为空时导入种子数据，返回实际写入条数。"""
    if not SEED_FILE.is_file():
        logger.warning("FAQ 种子文件不存在，跳过初始化: %s", SEED_FILE)
        return 0

    items = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    if not items:
        return 0

    # async_session 在 init_db_engine() 之后才存在，这里延迟导入
    from assistant.utils.db import async_session

    async with async_session() as session:
        existing = await session.scalar(
            select(func.count()).select_from(FaqItemRecord)
        )
        if existing:
            return 0

        session.add_all([
            FaqItemRecord(
                question=str(item["question"]),
                answer=str(item["answer"]),
                keywords=str(item.get("keywords", "")),
                category=str(item.get("category", "general")),
                enabled=1,
            )
            for item in items
        ])
        await session.commit()

    logger.info("FAQ 种子数据已导入，共 %d 条", len(items))
    return len(items)
