"""
这个模块实现闲聊处理器
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from assistant.domain.message import UserMessage, BotMessage
from assistant.domain.state import DialogueState
from assistant.prompts.history_builder import HistoryBuilder
from assistant.prompts.loader import load_prompt
from assistant.utils.llm import llm


class ChitChatHandler:

    async def chit_chat(self,
                        state:DialogueState,
                        user_message:UserMessage)->list[BotMessage]:
        # 构建提示词模版
        text = load_prompt("chitchat_respond")
        prompt = PromptTemplate.from_template(
            text,template_format="jinja2",
        )
        # 调用链
        chain = prompt | llm | StrOutputParser()
        # 调用
        history = HistoryBuilder.build(state.shared.sessions[-1].turns)
        result = await chain.ainvoke(
            input={
                "history":history,
                "user_message":HistoryBuilder.render_user_message(user_message),
            }
        )

        return [BotMessage(text=result)]