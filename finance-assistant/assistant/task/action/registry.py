"""
这个模块 创建字典，为了action注册
提供两个方法，向字典添加数据   从字典获取数据
"""
from assistant.task.action.base import Action


class ActionRegistry:
    def __init__(self):
        self.actions:dict[str, Action] = {}

    # 向字典添加数据 注册action调用方法
    def register(self,action:Action):
        self.actions[action.name] = action

    # 从字典获取数据 根据name获取action对象
    def get_action(self,name:str) -> Action:
        return self.actions[name]
