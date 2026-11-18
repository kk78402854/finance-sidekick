"""
FAQ 数据访问。
"""
from sqlalchemy import select

from assistant.repository.orm.faq import FaqItemRecord
from assistant.utils.db import async_session


async def fetch_faq_rows() -> list[dict]:
    """读取所有启用的 FAQ，返回 question/answer/keywords/category。"""
    async with async_session() as session:
        result = await session.execute(
            select(FaqItemRecord).where(FaqItemRecord.enabled == 1)
        )
        records = result.scalars().all()

    return [
        {
            "question": record.question,
            "answer": record.answer,
            "keywords": record.keywords,
            "category": record.category,
        }
        for record in records
    ]
