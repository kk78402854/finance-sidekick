"""
这个模块作用调用llm
把远程调用中台接口返回数据提交llm进行修改
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from assistant.domain.message import BotMessage, UserMessage
from assistant.domain.state import DialogueState
from assistant.knowledge.provider import KnowledgeChunk
from assistant.prompts.history_builder import HistoryBuilder
from assistant.prompts.loader import load_prompt
from assistant.utils.llm import llm


class KnowledgeResponder:
    async def respond(self,
                      chunks: list[KnowledgeChunk],
                      state:DialogueState,
                      user_message:UserMessage)->BotMessage:
        # 创建提示词模版
        text = load_prompt("knowledge_respond")
        prompt = PromptTemplate.from_template(
            text,template_format="jinja2",
        )

        chain = prompt | llm | StrOutputParser()

        result = await chain.ainvoke(
            input={
                "user_message":HistoryBuilder.render_user_message(user_message),
                "history":HistoryBuilder.build(
                    state.shared.sessions[-1].turns
                ),
                "knowledge_content":'\n'.join(
                    [  chunk.content
                        for chunk in chunks
                    ]
                )
            }
        )
        return BotMessage(text=result)
