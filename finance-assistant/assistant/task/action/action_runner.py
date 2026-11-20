"""
这个模块是action调用入口模块，
在flowExecutor的action步骤里面进行调用
"""
from assistant.domain.state import DialogueState
from assistant.task.action.base import Action, ActionCall, ActionResult
from assistant.task.action.registry import ActionRegistry


class ActionRunner:

    def __init__(self,action_registry:ActionRegistry):
        self.action_registry = action_registry

    # action_call: 接收flowExecutor传入的action属性值对象
    async def run(self,action_call:ActionCall,
                  state:DialogueState)->ActionResult:
        # 1根据action值到字典找到对应action对象
        action_name = action_call.action_name
        action:Action = self.action_registry.get_action(action_name)

        # 2调用action对象里面run方法进行远程调用，返回结果
        action_result:ActionResult = await action.run(state=state)
        return action_result


