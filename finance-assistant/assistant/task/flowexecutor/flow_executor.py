"""
这个模块作用：根据state里面active的步骤开始推进流程实现
"""
from assistant.domain.message import BotMessage, UserMessage
from assistant.domain.object_slots import object_slot_values
from assistant.domain.state import DialogueState
from assistant.task.action.action_runner import ActionRunner
from assistant.task.action.base import ActionCall, ActionResult
from assistant.task.flow.links import ConditionalLink, FallbackLink, FlowStepLink
from assistant.task.flow.models import Flow, FlowCatalog
from assistant.task.flow.steps import (
    ActionFlowStep,
    CollectSlotStep,
    EndFlowStep,
    FlowStep,
    ResponseFlowStep,
    StartFlowStep,
)
from assistant.task.response.response_render import ResponseRender


class FlowExecutor:

    def __init__(self,response_render:ResponseRender,
                  action_runner:ActionRunner):
        self.response_render = response_render
        self.action_runner = action_runner

    async def executor(self,state:DialogueState,
                       user_message:UserMessage,
                       flow_catalog:FlowCatalog)->list[BotMessage]:
        # 定义变量，封装最终返回数据
        bot_messages:list[BotMessage] = []
        # 判断state是否存在活跃任务
        if not state.tasks.active:
            return bot_messages

        # 如果当前有活跃任务
        for _ in range(100):
            # 根据active里面step_id获取对应步骤对象
            flow_id = state.tasks.active.flow_id
            flow:Flow = flow_catalog.get_flow_by_id(flow_id)

            step_id = state.tasks.active.step_id
            step:FlowStep = flow.get_step_by_id(step_id)

            # 根据step步骤不同类型判断，做不同处理
            """
            start步骤：本身不做业务处理，推进到下一步
            """
            if isinstance(step,StartFlowStep):
                self._run_next_step(step,state)
                continue

            """
            response步骤：数据渲染，把action步骤查询结果在这个步骤组装
            使用技术 jinja2
            """
            if isinstance(step,ResponseFlowStep):
                # response_render进行数据渲染
                # 返回渲染之后内容，类型 BotMessage
                bot_message:BotMessage = \
                    await self.response_render.render(
                        template=step.template,
                        state=state,
                        user_message=user_message,
                )
                # 把渲染数据放到bot_messages，为了 最后返回给用户
                bot_messages.append(bot_message)
                # 推进到下一步
                self._run_next_step(step,state)
                continue

            """
            collect步骤：收集槽位数据
            # 到active找槽位数据，如果找不到到对象类型消息找
            # 如果两个地方都没有找到槽位数据，等待用户输入
            ## 如果上面两个地方可以找到槽位数据，推进到下一步
            """
            if isinstance(step,CollectSlotStep):
                # 调用方法，返回bool，true表示有槽位数据推进到下一步
                #                  false表示没有槽位数据，给用户返回提示信息
                is_collect:bool = await self._get_collect_data(
                         step=step, state=state, user_message=user_message,
                         bot_messages=bot_messages)
                if is_collect: # true 有槽位数据
                    # 推进到下一步
                    self._run_next_step(step,state)
                    continue
                else:  # 没有槽位数据
                    return bot_messages

            """
            action步骤：执行具体业务方法，调用中台接口方法得到结果
            使用技术 httpx
            """
            if isinstance(step,ActionFlowStep):
                #获取yaml文件action属性值，封装ActionCall对象
                action_name = step.action
                action_call = ActionCall(action_name=action_name)
                # 调用action_runner方法
                action_result:ActionResult = await self.action_runner.run(
                    action_call=action_call,
                    state=state,
                )
                # 把action_result里面字典放到slots槽位里面
                # 为了下一步做数据渲染使用
                state.tasks.active.slots.update(
                    action_result.slots_update
                )
                # 推进到下一步
                self._run_next_step(step,state)
                continue

            """
            end步骤：表示流程结束，不需要到下一步，清空active返回数据
            """
            if isinstance(step,EndFlowStep):
                # 把state里面active清空
                state.tasks.active = None
                return bot_messages


    # 1 推进到下一步方法
    def _run_next_step(self, step:FlowStep,
                       state:DialogueState):
        # 获取当前步骤的next属性值
        ## 无条件 和 有条件跳转
        next_step_id = self._get_next_value(step.next,state)
        # 把next值设置state里面active里面
        state.tasks.active.step_id = next_step_id

    # 获取当前步骤的next属性值
    ## 无条件 和 有条件跳转
    def _get_next_value(self, next:list[FlowStepLink],
                        state:DialogueState)->str:
        # 无条件跳转，返回next属性值
        if len(next) == 1:
            return next[0].target
        # 有条件跳转，根据if判断 eval方法，返回不同值
        for link in next:
            # ConditionalLink 是if then
            if isinstance(link,ConditionalLink):
                # 判断if里面表达式
                result = bool(eval(link.condition,{},
                          {"slots":state.tasks.active.slots}))
                if result: # 表达式成立
                    return link.target
                continue
            if isinstance(link,FallbackLink):
                return link.target

    # 2 返回bool，true表示有槽位数据推进到下一步
    #      false表示没有槽位数据，给用户返回提示信息
    async def _get_collect_data(self, step:CollectSlotStep,
                          state:DialogueState,
                          user_message:UserMessage,
                          bot_messages:list[BotMessage])->bool:
        # 1 从state的active获取槽位数据
        slots:dict = state.tasks.active.slots
        slot_value = slots.get(step.slot_name)

        # 2 如果state的active获取不到，从对象类型消息获取
        if not slot_value:
            # 从对象类型消息获取,如果获取到放到state的active里面
            self.get_slot_data_from_object_message(step,state)

        # 3 如果两个地方都没有获取到，更新bot_messages添加提示信息，返回false
        slot_value = state.tasks.active.slots.get(step.slot_name)
        if not slot_value:
            bot_message = await self.response_render.render(
                template=step.template,
                state=state,
                user_message=user_message
            )
            bot_messages.append(bot_message)
            # bot_messages.append(BotMessage(text=step.template.text))
            return False
        # 4 如果两个地方获取到槽位数据，返回true
        else:
            return True

    # 从对象类型消息获取,如果获取到放到state的active里面
    def get_slot_data_from_object_message(self, step, state):
        # 约定，发送对象类型消息，这个消息首先放到state里面FocusedObject
        if not state.shared.focused_object:
            return

        # 对象 -> 槽位映射见 assistant/domain/object_slots.py
        values = object_slot_values(state.shared.focused_object)
        if step.slot_name in values:
            state.tasks.active.slots[step.slot_name] = values[step.slot_name]

