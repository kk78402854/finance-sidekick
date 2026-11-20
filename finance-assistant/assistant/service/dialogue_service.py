"""
这个模块是service业务逻辑层，负责调用其他层实现
调用repository操作数据库
调用engine处理消息
"""
from assistant.domain.message import ProcessResult, UserMessage
from assistant.domain.state import DialogueState
from assistant.engine.dialogue_engine import DialogueEngine
from assistant.repository.dialogue_repository import DialogueRepository


class DialogueService:

    def __init__(self, repository: DialogueRepository,
                      engine: DialogueEngine):
        self.repository = repository
        self.engine = engine

    async def run(self, user_message:UserMessage)->ProcessResult:
        # 1 注入要调用层对象，repository对象（操作数据库） 和 engine对象（处理消息）
        # 2 根据sender_id获取当前用户历史消息处理数据
        sender_id = user_message.sender_id
        # 调用repository层方法进行查询
        state:DialogueState = await self.repository.load_state(sender_id)

        # 2.1 前端切换了身份：把客户号写入会话，后续 Action 都按这个客户调用中台
        if user_message.customer_no:
            state.shared.customer_no = user_message.customer_no

        # 3 调用engine层方法处理当前消息
        process_result:ProcessResult = (
            await self.engine.process_message(state, user_message))

        # 4 把处理消息之后最新处理数据保存数据库里面
        await self.repository.save_state(state)

        # 5 返回engine处理结果
        return process_result

    async def get_history_data_sender_id(self, sender_id):
        state:DialogueState = await self.repository.load_state(sender_id)
        return state
