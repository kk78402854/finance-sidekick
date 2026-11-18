from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assistant.repository.orm.base import Base


class FaqItemRecord(Base):
    __tablename__ = 'faq_items'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 标准问题
    question: Mapped[str] = mapped_column(String(255), nullable=False)
    # 标准答案
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # 逗号分隔的关键词，用于召回
    keywords: Mapped[str] = mapped_column(String(255), default='')
    # 分类，例如 loan / fee / card
    category: Mapped[str] = mapped_column(String(64), default='general')
    # 1 启用，0 停用
    enabled: Mapped[int] = mapped_column(Integer, default=1)
