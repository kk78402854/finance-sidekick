"""
这个模块作用 作为知识检索入口
意图 → 检索范围映射 → 取 provider 对象 → 并行远程取数 → LLM 生成回答。
"""
from assistant.domain.message import BotMessage, UserMessage
from assistant.domain.state import DialogueState
from assistant.knowledge.intents import KNOWLEDGE_INTENTS
from assistant.knowledge.provider import KnowledgeChunk, KnowledgeProvider
from assistant.knowledge.registry import KnowledgeProviderRegistry
from assistant.knowledge.responder import KnowledgeResponder


class KnowledgeHandler:
    def __init__(self,knowledge_registry:KnowledgeProviderRegistry,
                 knowledge_responder:KnowledgeResponder):
        self.knowledge_registry = knowledge_registry
        self.knowledge_responder = knowledge_responder

    # 1 获取llm意图识别到知识检索值  list[str]
    ##  ["loan_product_info","interest_rate"]

    # 2 根据意图识别值到知识检索范围字典获取对应答案位置
    # 找到对应的 provider_ids 值，list[str],去重
    ## ["api.loan","faq.default", "rag.default"]

    # 3 根据找到答案位置值 provider_ids，到字典找到对应provider对象

    # 4 执行对应provider对象远程调用方法，得到远程调用中台接口结果

    # 5 把调用中台接口得到结果调用模块，提交llm修改，最终返回用户

    # knowledge_intents: 意图识别结果值
    async def handle(self,
                     knowledge_intents:list[str],
                     state:DialogueState,
                     user_message:UserMessage)->list[BotMessage]:
        # 1 获取llm意图识别到知识检索值  knowledge_intents list[str]
        ##  ["loan_product_info","interest_rate"]

        # 2 根据意图识别值到知识检索范围字典获取对应答案位置
        # 找到对应的 provider_ids 值，list[str],去重
        ## ["api.loan","faq.default", "rag.default"]
        provider_ids:list[str] = self.get_provider_ids(knowledge_intents)

        # 3 根据找到答案位置值 provider_ids，到字典找到对应provider对象
        # 4 执行对应provider对象远程调用方法，得到远程调用中台接口结果
        final_result:list[KnowledgeChunk] = []
        for provider_id in provider_ids:
            provider_obj:KnowledgeProvider = (
                      self.knowledge_registry.get_provider(provider_id))
            if provider_obj is None:
                continue
            # 调用provider的方法实现远程调用
            result:list[KnowledgeChunk] = await provider_obj.execute(
                query=self._query_text(state, user_message),
                state=state,
                user_message=user_message,
            )
            # 每次调用结果合并到final_result
            final_result.extend(result)

        # 5 把调用中台接口得到结果调用模块，提交llm修改，最终返回用户
        bot_message:BotMessage = await self.knowledge_responder.respond(
            chunks=final_result,
            state=state,
            user_message=user_message,
        )
        return [bot_message]

    # 根据意图识别值到知识检索范围字典获取对应答案位置
    # 意图识别结果：["interest_rate","fee_rule"]
    #                      |
    ## 答案位置：  ["faq.default","rag.default"]
    def get_provider_ids(self,
                knowledge_intents:list[str])->list[str]:
        final_provider_ids:list[str]=[]
        # 遍历意图识别结果列表
        for intent in knowledge_intents:
            # LLM 可能给出未登记的意图，未知意图直接跳过，避免 KeyError
            knowledge_intent = KNOWLEDGE_INTENTS.get(intent)
            if not knowledge_intent:
                continue
            # 拿着遍历之后每个intent到字典找到对应 provider_ids
            final_provider_ids.extend(knowledge_intent.provider_ids)

        # dict.fromkeys() 去重，同时保证列表顺序（即 provider 优先级）
        return list(dict.fromkeys(final_provider_ids))

    @staticmethod
    def _query_text(state: DialogueState, user_message: UserMessage) -> str:
        return str(user_message.text or "")
