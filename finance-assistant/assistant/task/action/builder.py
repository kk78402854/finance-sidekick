"""
这个模块 把所有 action 注册到字典里面。

register_custom_action 会扫描 assistant/task/action/custom/ 这一层的 .py 文件，
自动实例化并注册其中定义在本模块的 Action 子类。
新增 Action 时，只需要在 custom/ 下新增文件，不用改这里。
"""
import importlib
import inspect
import pkgutil

from assistant.task.action.base import Action
from assistant.task.action.registry import ActionRegistry


def register_custom_action(action_registry: ActionRegistry):
    # 1 拿到要扫描的包对象，后面用它的 __path__ 给 pkgutil 扫描
    package = importlib.import_module("assistant.task.action.custom")

    # 2 遍历包下一层的模块，prefix 让模块名变成完整点分路径
    for _, module_name, is_package in pkgutil.iter_modules(
            package.__path__,
            prefix=f"{package.__name__}."):
        # 只扫直接放在 custom/ 下的 py 文件，子包不递归
        if is_package:
            continue

        # 3 真正导入模块，才能拿到里面的类
        module = importlib.import_module(module_name)

        # 4 反射拿到模块里的所有类，逐个过滤
        for _, action_class in inspect.getmembers(module, inspect.isclass):
            # 必须是 Action 子类，且不能是基类本身
            if not issubclass(action_class, Action) or action_class is Action:
                continue

            # 只注册"定义在本模块"的类，避免 import 进来的类被重复注册
            if action_class.__module__ != module.__name__:
                continue

            action_registry.register(action_class())
