"""
这个模块澄清回复组件
"""
import json
from dataclasses import asdict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from assistant.domain.message import UserMessage, BotMessage
from assistant.domain.state import DialogueState
from assistant.prompts.history_builder import HistoryBuilder
from assistant.prompts.loader import load_prompt
from assistant.prompts.models import ClarifyReason
from assistant.utils.llm import llm


class ClarifyResponse:
    async def response(self,reason: ClarifyReason,
                       state:DialogueState,
                       user_message:UserMessage)->list[BotMessage]:
        prompt_text = load_prompt("clarify_respond")
        prompt = PromptTemplate.from_template(
            prompt_text,template_format="jinja2"
        )

        chain = prompt | llm | StrOutputParser()

        # 根据失败原因，生成 中文提示
        clarify_message = self.build_reason(reason, state)
        res = await chain.ainvoke(
            input={
                "reason":reason.value,
                "clarify_message":clarify_message,
                "focused_object": json.dumps(
                    asdict(state.shared.focused_object)
                    if state.shared.focused_object else None),
                "history": HistoryBuilder.build(state.shared.sessions[-1].turns),
                "user_message": HistoryBuilder.render_user_message(user_message)
            }
        )
        return [BotMessage(text=res)]


    def build_reason(self, reason, state):
        if reason is ClarifyReason.MULTIPLE_TRACKS:
            return (
                "你这次同时提到了多个方向。我们先处理一个，"
                "你想先办业务还是先咨询信息呢？")

        if reason is ClarifyReason.MISSING_FOCUSED_OBJECT:
            return "请先发送你想咨询的账户、银行卡或交易，我再继续帮你看。"

        if reason is ClarifyReason.MISSING_KNOWLEDGE_INTENT:
            return (
                "你是想了解贷款产品、理财收益，"
                "还是手续费和还款规则呢？"
            )

        if reason is ClarifyReason.MISSING_TRACK:
            return "你是想先办理业务，还是先咨询产品信息呢？"

        if reason is ClarifyReason.MISSING_TASK_COMMANDS:
            return (
                "你这次是想办理什么业务呢？"
                "比如查余额、查流水、申请贷款、挂失信用卡或提交投诉。"
            )

        if reason is ClarifyReason.INVALID_TASK_COMMAND:
            return (
                "当前任务状态不支持这个操作，"
                "请告诉我你想开始、继续还是取消哪个任务。"
            )

        if reason is ClarifyReason.UNKNOWN_KNOWLEDGE_INTENT:
            return (
                "我暂时无法识别这个咨询方向，"
                "你可以具体说说想了解的产品、利率或办理规则。"
            )

        if reason is ClarifyReason.OBJECT_REQUIRES_INTENT:
            focused_object = state.shared.focused_object
            if focused_object is not None and focused_object.type == "account":
                return (
                    "我已经收到这个账户了。你想查余额、查交易流水，"
                    "还是咨询账户相关问题呢？"
                )
            if focused_object is not None and focused_object.type == "card":
                return (
                    "我已经收到这张卡了。你想查余额、查流水，"
                    "还是办理挂失呢？"
                )
            if focused_object is not None and focused_object.type == "transaction":
                return (
                    "我已经收到这笔交易了。你想了解交易详情，"
                    "还是对这笔记账发起投诉呢？"
                )

        return (
            "我还需要再确认一下你的意思，"
            "你可以换个更具体的说法告诉我。"
        )