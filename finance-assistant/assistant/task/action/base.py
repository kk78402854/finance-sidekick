"""
这个模块 定义action需要数据模型，封装数据，返回数据
       创建Action基类，公共name属性 和 远程调用的抽象方法
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from assistant.domain.state import DialogueState


# 封装传递action属性值
@dataclass
class ActionCall:
    action_name:str

# 封装action远程调用结果
@dataclass
class ActionResult:
    slots_update:dict[str,Any]=field(default_factory=dict)

# Action基类
class Action(ABC):
    # 公共属性
    name:str=""

    # 抽象方法
    @abstractmethod
    async def run(self,state:DialogueState) -> ActionResult:
        pass