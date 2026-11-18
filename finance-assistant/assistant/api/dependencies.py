from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from assistant.engine.builder import build_engine
from assistant.engine.dialogue_engine import DialogueEngine
from assistant.plan.turn_plan_validator import TurnPlanValidator
from assistant.plan.turn_planner import TurnPlanner
from assistant.repository.dialogue_repository import DialogueRepository
from assistant.service.dialogue_service import DialogueService
from assistant.utils import db


# 创建获取数据库操作session对象方法
async def get_session():
    async with db.async_session() as session:
        yield session

# 创建repository对象
async def get_repository(session:AsyncSession=Depends(get_session)):
    return DialogueRepository(
        session=session,
    )

def init_dialogue_engine():
    global _dialogue_engine
    _dialogue_engine = build_engine()

# 创建engine对象
async def get_engine():
    return _dialogue_engine

# async def get_engine():
#     return build_engine()

async def get_dialogue_service(
        repository:DialogueRepository=Depends(get_repository),
        engine:DialogueEngine=Depends(get_engine)):
    return DialogueService(
        repository=repository,
        engine=engine,
    )