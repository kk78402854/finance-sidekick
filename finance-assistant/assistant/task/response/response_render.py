"""
这个模块作用，使用jinja2技术实现数据渲染
"""
from jinja2 import Template
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from assistant.domain.message import BotMessage, UserMessage
from assistant.domain.state import DialogueState
from assistant.prompts.history_builder import HistoryBuilder
from assistant.task.response.models import ResponseMode, ResponseTemplate
from assistant.utils.llm import llm


class ResponseRender:
    async def render(self,
            template:ResponseTemplate,
                     state:DialogueState,
                     user_message:UserMessage)->BotMessage:
        # mode=static yaml是什么样内容，给用户返回什么样内容
        if template.mode == ResponseMode.STATIC:
            # jinja2实现数据渲染
            template = Template(template.text)
            render_text = template.render(slots=state.tasks.active.slots)
            return BotMessage(text=render_text)

        # 把yaml文件内容提交llm进行修改，修改后返回用户
        if template.mode == ResponseMode.REPHRASE:
            # jinja2实现数据渲染
            template = Template(template.text)
            render_text = template.render(slots=state.tasks.active.slots)
            # 提示词模版
            prompt = PromptTemplate.from_template(
                template.prompt,template_format="jinja2",
            )
            # 调用链
            chain = prompt | llm | StrOutputParser()
            # 调用
            result = await chain.ainvoke(
                {
                    "history": HistoryBuilder.build(state.shared.sessions[-1].turns),
                    "user_message": HistoryBuilder.render_user_message(user_message),
                    "current_response": render_text
                })
            return BotMessage(text=result)

        # 直接让llm生成返回内容
        if template.mode == ResponseMode.GENERATE:
            pass
