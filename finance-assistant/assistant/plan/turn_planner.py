import json
from dataclasses import asdict
from datetime import date, timedelta

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from assistant.domain.message import UserMessage
from assistant.domain.state import DialogueState, Turn
from assistant.knowledge.intents import KNOWLEDGE_INTENTS
from assistant.prompts.history_builder import HistoryBuilder
from assistant.prompts.loader import load_prompt
from assistant.prompts.models import TurnPlan
from assistant.task.flow.models import FlowCatalog, Flow
from assistant.utils.llm import llm

"""
这个模块作用：根据用户文本消息调用llm进行意图识别
"""
class TurnPlanner:

    async def plan(self,state:DialogueState,
                   user_message:UserMessage,
                   flow_catalog:FlowCatalog)->TurnPlan:
        # 1 创建提示词模版
        prompt_text = load_prompt("turn_plan")
        prompt = PromptTemplate.from_template(
            prompt_text,
            template_format="jinja2"
        )

        # 2 创建调用链
        chain = prompt | llm | JsonOutputParser()

        # 获取user_message
        user_message = HistoryBuilder.render_user_message(user_message)
        # 获取conversation_history 历史
        turns:list[Turn] = state.shared.sessions[-1].turns
        conversation_history = HistoryBuilder.build(turns)

        # 获取focused_object_json
        focused_object_json = json.dumps(
            asdict(state.shared.focused_object)
            if state.shared.focused_object else None,
        )

        # 获取所有流程数据 flows_json
        # FlowCatalog
        flows:dict[str,Flow] = flow_catalog.flows
        # 把所有流程里面步骤部分数据去掉
        # llm只是做意图识别，没有推进步骤，不需要步骤数据，如果传递步骤数据造成llm幻觉
        # flows_json = [
        #     {
        #         "flow_id":flow.id,
        #         "name":flow.name,
        #         "description":flow.description
        #     }
        #     for flow in flows.values()
        # ]

        flows_json = [
            {k:v for k,v in asdict(flow).items()
               if k != "steps"
            }
            for flow in flows.values()
        ]

        task_state_json = json.dumps(
            asdict(state.tasks) if state.tasks else None,)

        # 构建知识检索范围数据
        knowledge_intents_json = json.dumps(
            [   {
                "id":intent.id,
                "description":intent.description
            }
                for intent in KNOWLEDGE_INTENTS.values()
            ],ensure_ascii=False
        )

        # 3 调用方法执行，方法里面传入提示词需要数据
        today = date.today()
        result = await chain.ainvoke(input={
            "user_message":user_message,
            "conversation_history":conversation_history,
            "focused_object_json":focused_object_json,
            "flows_json":json.dumps(flows_json, ensure_ascii=False),
            "task_state_json":task_state_json,
            "knowledge_intents_json":knowledge_intents_json,
            # 相对时间（昨天、最近一周）需要模型知道今天是哪天
            "current_date":today.isoformat(),
            "week_ago":(today - timedelta(days=7)).isoformat(),
        })

        # 4 把llm返回json结构转换对象
        return TurnPlan.from_dict(result)