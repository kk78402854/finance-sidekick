"""
这个模块作用，根据commandProcessor组件返回任务状态变化对象列表生成不同中文提示
"""

from assistant.domain.message import BotMessage
from assistant.lifecycle.models import TaskCanceled, TaskEvent, TaskResumed, TaskStarted, TaskSwitched
from assistant.task.flow.models import Flow, FlowCatalog


class TaskLifecycleResponder:

    def __init__(self,flow_catalog:FlowCatalog):
        self.flow_catalog = flow_catalog
    #把 CommandProcessor 产出的「任务状态变化事件」翻译成给用户看的中文回复。
    async def respond(self,events:list[TaskEvent])->list[BotMessage]:
        messages: list[BotMessage] = []
        # 遍历list[TaskEvent]
        for event in events:
            messages.append(self.execute_event_data(event))
        return messages

    # 根据流程id获取流程名称
    def _get_flow_name(self,flow_id:str)->str:
        flow:Flow = self.flow_catalog.get_flow_by_id(flow_id)
        return flow.name

    # 根据event不同类型生成不同中文提示
    def execute_event_data(self, event:TaskEvent)->BotMessage:
        if isinstance(event, TaskStarted):
            flow_name = self._get_flow_name(event.task.flow_id)
            return BotMessage(text=f"好的，现在开始执行{flow_name}")

        if isinstance(event, TaskSwitched):
            pre_flow_name = self._get_flow_name(event.previous.flow_id)
            current_flow_name = self._get_flow_name(event.current.flow_id)
            return BotMessage(text=f"好的，现在把{pre_flow_name}暂停 "
                                   f" 现在开始执行{current_flow_name}")

        if isinstance(event, TaskResumed):
            flow_name = self._get_flow_name(event.task.flow_id)
            return BotMessage(text=f"好的，继续刚才{flow_name}操作")

        if isinstance(event, TaskCanceled):
            flow_name = self._get_flow_name(event.task.flow_id)
            return BotMessage(text=f"好的，取消{flow_name}操作")
        return BotMessage(text="兜底数据")
