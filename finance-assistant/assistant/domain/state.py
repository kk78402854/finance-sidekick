import time
import uuid
from dataclasses import dataclass, field

from assistant.domain.message import BotMessage, UserMessage
from assistant.lifecycle.models import TaskCanceled, TaskEvent, TaskRef, TaskResumed, TaskStarted, TaskSwitched


# 一轮对话，一个问题对应一个或者多个回答
@dataclass
class Turn:
    turn_id: str
    # 用户提问
    user_message: UserMessage
    # 客服回复
    bot_message: list[BotMessage]=field(default_factory=list)

# 会话对象
@dataclass
class Session:
    # session的id，区别不同session
    session_id: str
    # session创建时间戳
    started_at: float
    # session最后一次活跃时间
    last_activity_at: float
    # 关闭时间
    closed_at: float | None = None
    # 每个session会话多轮对话
    turns:list[Turn]=field(default_factory=list)

# 对象类型消息
@dataclass
class FocusedObject:
    type:str #  order   product
    id:str
    title:str | None=None
    attributes:dict=field(default_factory=dict)

# 三种能力都有数据：任务流程、知识问答、闲聊
@dataclass
class SharedState:
    # 当前会话登录的客户号，由前端身份切换传入；为空时回落到 .env 默认客户
    customer_no: str | None = None
    # 对象类型消息
    focused_object: FocusedObject | None = None
    # 多个会话数据
    sessions: list[Session] = field(default_factory=list)

    # 创建session，放到列表
    def create_session(self):
        now = time.time()
        session = Session(
            session_id=str(uuid.uuid4()),
            started_at=now,
            last_activity_at=now,
        )
        # 放到sessions: list[Session]
        self.sessions.append(session)

# 某个任务流程步骤相关数据
@dataclass
class TaskInstance:
    # 流程id，对应yaml文件  refund_request
    flow_id: str
    # 步骤id ,比如 start
    step_id: str | None = None
    # 当前任务id
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # task_id: str | None = None
    # 槽位数据字典  {order_number : a10098765}
    slots: dict= field(default_factory=dict)

    def get_task_ref(self)->TaskRef:
        return TaskRef(
            task_id=self.task_id,
            flow_id=self.flow_id,
        )


# 任务流程特有数据，流程步骤数据
@dataclass
class TaskState:
    # 当前正在运行（活跃）的任务
    active: TaskInstance | None = None
    # 中断（暂停）的任务
    paused: list[TaskInstance] = field(default_factory=list)

    # {"command": "start_flow", "flow": "<flow_id>"},
    ## 判断当前是否有active，如果没有直接放
    ## 如果有，把当前任务暂停，把新任务放到active里面
    def start_task(self, task)->TaskEvent:
        ## 当前有active
        if self.active:
            previous = self.active.get_task_ref()
            # 把当前活跃任务暂停
            self.paused.append(self.active)
            # 把新任务做为活跃
            self.active = task
            current = self.active.get_task_ref()
            return TaskSwitched(
                # 暂停任务
                previous=previous,
                # 当前活跃任务
                current=current
            )
        else: # 没有活跃任务
            self.active = task
            return TaskStarted(
                task=self.active.get_task_ref(),
            )

    # 恢复任务
    def resume_task(self,task_id)->TaskEvent:
        target_task_ref = None
        target_task = None
        # 1 从中断列表获取要恢复任务
        for index,task in enumerate(self.paused):
            if task.task_id == task_id:
                target_task_ref = task.get_task_ref()
                target_task = self.paused.pop(index)
                break

        # 2 判断恢复任务是否找到
        if target_task is None:
            raise Exception("Task not found in paused tasks")

        # 3 如果找到恢复任务
        ## 判断当前是否活跃任务
        if self.active:
            previous = self.active.get_task_ref()

            self.paused.append(self.active)
            self.active = target_task

            return TaskSwitched(
                previous=previous,
                current=target_task_ref
            )
        else:
            self.active = target_task
            return TaskResumed(
                task=self.active.get_task_ref(),
            )

    # 取消任务
    def cancel_task(self,task_id)->TaskEvent:
        # 1 判断当前活跃任务是否要取消任务
        if self.active is not None and self.active.task_id == task_id:
            target_task = self.active.get_task_ref()
            # 取消
            self.active = None
            return TaskCanceled(#记录这次取消的是哪个任务
                task=target_task
            )
        # 2 到中断列表找到取消任务
        else:
            for paused_task in self.paused:
                # 中断列表任务id和传入任务id相同
                if paused_task.task_id == task_id:
                    target_task = paused_task.get_task_ref()
                    # 找到取消任务
                    self.paused.remove(paused_task)
                    return TaskCanceled(
                        task=target_task
                    )

            raise Exception("Task not found in paused tasks")


@dataclass
class DialogueState:
    # 用户id
    sender_id: str
    # 三种能力都有数据：任务流程、知识问答、闲聊
    shared: SharedState=field(default_factory=SharedState)
    # 任务流程特有数据，流程步骤数据
    tasks: TaskState=field(default_factory=TaskState)

    # 清空任务数据
    def clear_task(self):
        self.shared.focused_object = None
        self.tasks.active = None
        self.tasks.paused.clear()
