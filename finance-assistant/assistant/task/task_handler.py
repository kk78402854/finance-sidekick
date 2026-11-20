"""
这个模块作用：任务流程对外入口
调用TaskHandler三个组件
commandProcessor：更新state状态
tasklifecycle：生成中文提示
flowExecutor：按照步骤推进
把最终结果合并，返回用户
"""
from assistant.domain.message import BotMessage, UserMessage
from assistant.domain.state import DialogueState
from assistant.lifecycle.models import TaskEvent
from assistant.plan.command import Command
from assistant.task.command.command_processor import CommandProcessor
from assistant.task.flow.models import FlowCatalog
from assistant.task.flowexecutor.flow_executor import FlowExecutor
from assistant.task.tasklifecycle.task_lifecycle import TaskLifecycleResponder


class TaskHandler:
    # 注入需要对象
    def __init__(self, command_processor:CommandProcessor,
                 task_lifecycle:TaskLifecycleResponder,
                 flow_catalog:FlowCatalog,
                 flow_executor: FlowExecutor,):
        self.command_processor = command_processor
        self.task_lifecycle = task_lifecycle
        self.flow_catalog = flow_catalog
        self.flow_executor = flow_executor

    # 入口方法
    async def handle(self, commands:list[Command],
                      state:DialogueState,
                     user_message:UserMessage)->list[BotMessage]:
        # 1 调用commandProcessor更新state状态数据
        events:list[TaskEvent] = \
            await self.command_processor.process_command(
                commands=commands,
                state=state,
                flow_catelog=self.flow_catalog
            )

        # 2 根据commandProcessor执行返回结果调用tasklifecycle
        ## 根据不同状态对象生成不同中文提示
        messages:list[BotMessage] = await self.task_lifecycle.respond(
            events=events,
        )

        #  3 调用FlowExecutor组件推进步骤实现
        bot_messages:list[BotMessage] = await self.flow_executor.executor(
            state=state,
            user_message=user_message,
            flow_catalog=self.flow_catalog,
        )

        # 合并前两个阶段产生的消息。
        messages.extend(bot_messages)
        return messages
