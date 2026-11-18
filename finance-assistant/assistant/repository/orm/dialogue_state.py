from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from assistant.repository.orm.base import Base


class DialogueStateRecord(Base):
    __tablename__ = 'dialogue_states'
    # 类属性和表字段对应关系
    sender_id:Mapped[str] = mapped_column(String(255),primary_key=True)
    state_json:Mapped[str] = mapped_column(Text,nullable=False)