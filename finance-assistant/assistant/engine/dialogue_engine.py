import time
import uuid
from dataclasses import asdict
from pathlib import Path

from assistant.chitchat.chit_chat import ChitChatHandler
from assistant.clarify.clarify_response import ClarifyResponse
from assistant.domain.message import UserMessage, ProcessResult, BotMessage, MessageType
from assistant.domain.object_slots import can_fill_slot, object_slot_values
from assistant.domain.state import DialogueState, Turn, FocusedObject
from assistant.knowledge.knowledge_handler import KnowledgeHandler
from assistant.plan.command import SetSlotsCommand
from assistant.plan.turn_plan_validator import TurnPlanValidator
from assistant.plan.turn_planner import TurnPlanner
from assistant.prompts.models import TurnPlan, TurnPlanValidationResult, ClarifyReason
from assistant.task.flow.loader import FlowLoader
from assistant.task.flow.models import FlowCatalog, Flow
from assistant.task.flow.steps import FlowStep, CollectSlotStep
from assistant.task.task_handler import TaskHandler

"""
这个模块作用：用于处理消息
"""
class DialogueEngine:

    def __init__(self,turn_planner:TurnPlanner,
                 turn_plan_validator:TurnPlanValidator,
                 task_handler:TaskHandler,
                 chit_chat:ChitChatHandler,
                 clarify_response:ClarifyResponse,
                 knowledge_handler:KnowledgeHandler):
        self.turn_planner = turn_planner
        self.turn_plan_validator = turn_plan_validator
        self.task_handler = task_handler
        self.chit_chat = chit_chat
        self.clarify_response = clarify_response
        self.knowledge_handler = knowledge_handler#day07加入的

    async def process_message(self,
                    state:DialogueState,
                              user_message:UserMessage)->ProcessResult:
        # 1 准备 session
        ## 获取当前session
        ### 如果获取不到，创建新session
        ### 如果获取到，判断session是否过期（60分钟不活跃）
        ####          如果没有过期，使用当前session
        ####          如果session过期，创建新的session，清空过期session任务
        # 2 封装一轮对象 （用户提问）
        # 3 判断消息类型：文本 或者 对象类型消息
        # 3.1 如果消息：文本类型
        ## * 使用llm意图识别：识别文本执行哪个能力：任务流程、知识检索、闲聊
        ##                   如果识别任务流程，流程id识别到
        ## * 对llm意图识别结果校验，保证正常往后执行
        ### 识别能力最多一个，流程id在yaml文件是否存在......
        ## * 校验失败，执行澄清回复组件
        ## * 校验成功，根据识别方向，调用不同方向处理器
        # 4 封装处理结果，返回用户
        # 3.2 如果对象类型消息
        ## * 封装到focused_object对象里面
        ## * 判断当前执行任务里面是否有可以匹配槽位数据
        ## * 如果没有匹配，执行 澄清回复
        ## * 可以匹配，从对象消息获取数据，执行后续流程

        # 1 准备当前session
        self._prepare_current_session(state)

        # 2 判断消息类型
        ## 文本类型消息
        if user_message.type==MessageType.TEXT:
            messages:list[BotMessage] = \
                await self._execute_text_message(state, user_message)

        else: # 对象类型消息
            messages:list[BotMessage] = await self._execute_object_message(
                state=state,
                user_message=user_message
            )

        ## 3 提交本轮对象
        turn = Turn(
            turn_id=str(uuid.uuid4()),
            # 用户提问
            user_message=user_message,
            # 客服回复
            bot_message=messages
        )
        # 把本轮对象turn对象放到state里面
        state.shared.sessions[-1].turns.append(turn)

        # 返回数据
        return ProcessResult(
            sender_id = user_message.sender_id,
            message_id = user_message.message_id,
            messages=messages
        )

    # 准备当前session
    def _prepare_current_session(self, state:DialogueState):
        # 1 判断state是否存在session，如果不存在创建新session
        if not state.shared.sessions:
            # 创建新session对象
            state.shared.create_session()
        # 2 如果state里面存在session，获取最近session
        else:
            current_session = state.shared.sessions[-1]
            # 3 判断获取session是否过期，
            # 使用当前时间 - session最后一次活跃时间 大于60分钟
            now = time.time()
            # 1970 1 1  秒
            if now - current_session.last_activity_at > 60*60:
                # session过期，清空session任务数据
                state.clear_task()
                # 如果过期创建新session
                state.shared.create_session()
            # 没有过期使用，更新时间数据
            else:
                # 更新最后一次活跃时间
                current_session.last_activity_at = now


    # 文本类型消息处理
    async def _execute_text_message(self, state, user_message)->list[BotMessage]:
        # 获取yaml所有流程数据
        path = Path(__file__).parents[2]/'flow_config'/'user_flows.yml'
        flow_catalog:FlowCatalog = FlowLoader().load(path)
        # 1 对文本消息意图识别
        turn_plan:TurnPlan= await self.turn_planner.plan(
            state=state,
            user_message=user_message,
            flow_catalog=flow_catalog )

        # 2 对意图识别结果校验
        validation:TurnPlanValidationResult = (
            self.turn_plan_validator.validate(turn_plan=turn_plan,
                                          state=state,
                                          flow_catelog=flow_catalog))

        # 对校验结果判定，失败
        if not validation.valid:
            # 执行澄清回复组件
            return await self.clarify_response.response(
                reason=validation.reason,
                state=state,
                user_message=user_message,
            )

        # 成功，根据识别方向执行不同处理器
        if turn_plan.task: # 任务流程方向
            messages:list[BotMessage]= await self.task_handler.handle(
                state=state,
                user_message=user_message,
                commands=turn_plan.task.commands
            )
            return messages

        if turn_plan.knowledge: # 知识检索方向
            messages:list[BotMessage] = await self.knowledge_handler.handle(
                knowledge_intents=turn_plan.knowledge.intents,
                state=state,
                user_message=user_message
            )
            return messages

        else: # 闲聊方向
            return await self.chit_chat.chit_chat(
                state=state,
                user_message=user_message,
            )

    # 对象类型消息处理
    async def _execute_object_message(self, state,
                                      user_message:UserMessage)->list[BotMessage]:
        # 0 既没有文本也没有对象，按澄清处理，避免空请求打崩
        if user_message.object is None:
            return await self.clarify_response.response(
                reason=ClarifyReason.MISSING_FOCUSED_OBJECT,
                state=state,
                user_message=user_message,
            )

        # 1 把对象类型消息封装state里面focused_object里面
        state.shared.focused_object = FocusedObject(
            **asdict(user_message.object)
        )

        # 2 判断当前对象类型消息是否可以匹配任务槽位数据
        if self._is_can_fill_slots(state): # 可以匹配
            slots = object_slot_values(user_message.object)
            if not slots:
                return await self.clarify_response.response(
                    reason=ClarifyReason.OBJECT_REQUIRES_INTENT,
                    state=state,
                    user_message=user_message,
                )
            # 创建commands
            # # | `set_slots`   | `{"command": "set_slots", "slots": {"<slot_name>": "<value>"}}`
            command = SetSlotsCommand(
                command="set_slots",
                slots=slots
            )

            # 执行任务流程处理器
            return await self.task_handler.handle(
                commands=[command],
                state=state,
                user_message=user_message,
            )
        else:  # 没有匹配
            return await self.clarify_response.response(
                reason=ClarifyReason.OBJECT_REQUIRES_INTENT,
                state=state,
                user_message=user_message,
            )

    # 判断当前对象类型消息是否可以匹配任务槽位数据
    def _is_can_fill_slots(self, state:DialogueState)->bool:
        # 1 判断当前正在运行任务,如果没有，返回False
        active_task = state.tasks.active
        if not active_task:
            return False

        # 2 如果有正在运行任务，进行判断
        # 获取yaml所有流程数据
        path = Path(__file__).parents[2] / 'flow_config' / 'user_flows.yml'
        flow_catalog: FlowCatalog = FlowLoader().load(path)
        # 根据action里面flow_id获取flow对象
        flow:Flow = flow_catalog.get_flow_by_id(active_task.flow_id)
        # flow对象方法：根据active里面step_id获取当前step对象
        step_id = active_task.step_id
        step:FlowStep = flow.get_step_by_id(step_id)
        # 当前步骤类型 需要 collect步骤
        if not isinstance(step,CollectSlotStep):
            return False

        ## 判断聚焦对象类型与当前 collect 槽位是否匹配
        ### 获取collect步骤 slot_name槽位名称
        slot_name = step.slot_name
        ### 获取对象类型消息 account/card/credit_card/transaction/loan
        object_type = state.shared.focused_object.type

        # 匹配判断，映射表见 assistant/domain/object_slots.py
        return can_fill_slot(object_type, slot_name)