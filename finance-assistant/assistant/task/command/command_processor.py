"""
这个模块作用：根据意图识别结果commands 更新state数据
"""
import uuid

from assistant.domain.state import DialogueState, TaskInstance
from assistant.lifecycle.models import TaskEvent
from assistant.plan.command import CancelTaskCommand, Command, ResumeTaskCommand, SetSlotsCommand, StartFlowCommand
from assistant.task.flow.models import Flow, FlowCatalog
from assistant.task.flow.steps import FlowStep


class CommandProcessor:
    ## 第一步 执行 Commands，修改任务状态。
    ## 修改state里面任务状态数据 active  或者 paused
    ## commands:list[Command],意图识别结果列表
    async def process_command(self,
                      commands:list[Command],
                      state:DialogueState,
                      flow_catelog:FlowCatalog) -> list[TaskEvent]:
        # 遍历 list[Command]得到每个command，根据command类型做不同数据state更新
        events:list[TaskEvent] = []
        for command in commands:
            event: TaskEvent = self._execute_command(command, state, flow_catelog)
            if event:
                events.append(event)
        return events

    # 处理每个command，根据不同类型
    def _execute_command(self,
                  command:Command,
                  state:DialogueState,
                  flow_catelog:FlowCatalog) -> TaskEvent:
        # {"command": "start_flow", "flow": "<flow_id>"},
        if isinstance(command, StartFlowCommand):
            # 原则：向state里面active设置数据
            # 新任务，创建TaskInstance对象，放到active里面
            # 流程id
            flow_id = command.flow
            # 获取当前流程start步骤类型的id值
            ## 根据流程id获取流程对象
            flow:Flow = flow_catelog.get_flow_by_id(flow_id)
            ## 得到Flow对象所有步骤，获取步骤start类型步骤
            start_step:FlowStep = flow.get_start_step()
            step_id = start_step.id
            # 创建TaskInstance对象
            task = TaskInstance(
                flow_id=flow_id,
                step_id=step_id,
                task_id=str(uuid.uuid4()),
            )

            # 把创建task任务放到state里面active里面
            ## 判断当前是否有active，如果没有直接放
            ## 如果有，把当前任务暂停，把新任务放到active里面
            event:TaskEvent = state.tasks.start_task(task)
            return event

        # {"command": "set_slots", "slots": {"<slot_name>": "<value>"}},
        # 设置槽位数据，没有任务状态变化
        # 把意图识别槽位数据放到state里面active槽位里面
        if isinstance(command, SetSlotsCommand):
            # state slots  {a:1, b:2}
            # command.slots  {order_name: 1001}
            ## {a:1, b:2 , order_name: 1001}

            # # [1,2,3]  append  [4]  =》 [1,2,3,[4]]
            # a:list[str] = []
            # a.append("1")
            # # # [1,2,3]  extend  [4]  =》 [1,2,3,4]
            # a.extend("1")
            state.tasks.active.slots.update(command.slots)
            return None

        # {"command": "resume_task", "task_id": "<task_id>"},
        if isinstance(command, ResumeTaskCommand):
            task_id = command.task_id
            event: TaskEvent = state.tasks.resume_task(task_id)
            return event

        # {"command": "cancel_task", "task_id": "<task_id>"}
        # 根据task_id找到对应任务，把取消
        ## 从当前活跃任务 或者 中断列表找
        if isinstance(command, CancelTaskCommand):
            task_id = command.task_id
            event: TaskEvent = state.tasks.cancel_task(task_id)
            return event
