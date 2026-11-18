from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from assistant.domain.state import DialogueState
from assistant.repository.orm.dialogue_state import DialogueStateRecord

"""
这个模块作用：用于操作mysql数据库
"""
# 类型适配器，对象  json字符串互相转换
# json字符串 -- 对象：validate_json()
# 对象 -- json字符串：dump_json()
dialogue_state_adapter = TypeAdapter(DialogueState)

class DialogueRepository:

    # 注入操作数据库session对象
    def __init__(self,session:AsyncSession):
        self.session = session

    # 根据sender_id查询
    async def load_state(self,
                     sender_id:str)->DialogueState:
        # 第一种 编写sql语句
        # sql = "select * from dialogue_states where sender_id = :sid"
        # result = await self.session.execute(sql,{"sid":sender_id})

        # 第二种 orm思想
        # 不需要编写sql语句，对象形式操作
        ## 第一步 构建语句
        sql = select(DialogueStateRecord).where(
                     DialogueStateRecord.sender_id == sender_id)

        ## 第二步 调用session方法执行语句
        result = await self.session.execute(sql)

        ## 第三步 得到最终结果
        record = result.scalar_one_or_none()

        ## 结果处理
        if record: # 查询到结果，把查询json字符串 转换 DialogueState对象
            state = dialogue_state_adapter.validate_json(record.state_json)
            return state
        else: # 没有查询到结果 none
            return DialogueState(sender_id=sender_id)

    # 保存数据库
    ## 不存在添加，存在更新
    async def save_state(self, state:DialogueState):
        # 第一步 state对象 转换 json字符串  dump_json()
        state_json = dialogue_state_adapter.dump_json(state).decode("utf-8")

        # 第二步 构建sql语句
        ## 判断表里面存在数据更新，不存在添加
        # insert into dialogue_states values(1,'{....}')
        # update dialogue_states set state_json=? where sender_id=1

        # 如果只是想实现基本添加操作，导入通用 或者方言mysql依赖都可以的
        ## 标准sql   方言sql
        # 因为现在逻辑：存在数据更新，不存在添加
        ## 如果原始方式：先查询数据，有更新，没有添加
        ## 但是使用sqlalchemy封装这个实现，只需要导入方言insert依赖，直接调用方法实现这个逻辑
        ### from sqlalchemy.dialects.mysql import insert
        sql = insert(DialogueStateRecord).values(
            sender_id=state.sender_id,
            state_json=state_json
        )
        # 存在数据更新，不存在添加
        on_duplicate_key = sql.on_duplicate_key_update(
            state_json=state_json
        )

        # 第三步 执行语句
        await self.session.execute(on_duplicate_key)
        await self.session.commit()