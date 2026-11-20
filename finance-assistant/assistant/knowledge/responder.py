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

# 没有检索到任何资料时的确定性回复：不让 LLM 在空上下文上编造答案
KNOWLEDGE_EMPTY_REPLY = (
    "暂未查询到与您问题相关的资料。您可以换个更具体的说法，例如：\n"
    "· 贷款利率是多少\n"
    "· 提前还款收违约金吗\n"
    "· 信用卡年费怎么免\n"
    "· 网点营业时间和地址\n"
    "也可以直接告诉我产品名称或业务名称，我再帮您查询。"
)


class KnowledgeResponder:
    async def respond(self,
                      chunks: list[KnowledgeChunk],
                      state:DialogueState,
                      user_message:UserMessage)->BotMessage:
        # 0 检索结果为空（或只有空白内容）时直接兜底，避免模型凭空描述“已接入知识库”
        contents = [
            chunk.content.strip()
            for chunk in chunks
            if chunk.content and chunk.content.strip()
        ]
        if not contents:
            return BotMessage(text=KNOWLEDGE_EMPTY_REPLY)

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
                "knowledge_content":'\n'.join(contents)
            }
        )
        return BotMessage(text=result)
