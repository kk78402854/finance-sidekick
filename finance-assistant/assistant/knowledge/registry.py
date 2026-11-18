"""
这个模块作用，把所有provider对象注册到字典里面
"""
from assistant.knowledge.provider import KnowledgeProvider


class KnowledgeProviderRegistry:
    # 传入所有的provider对象，把这些provider对象放到字典里面
    # 例如：
    # {
    #     "api.account": <ApiAccountProvider>,
    #     "api.transaction": <ApiTransactionProvider>,
    #     "faq.default": <FaqProvider>,
    #     "rag.default": <RagProvider>,
    # }
    def __init__(self, provider_objects:list[KnowledgeProvider]):
        self.providers_dict = {
            provider_obj.provider_id : provider_obj
             for provider_obj in provider_objects
        }

    # 从字典获取数据 根据provider_id获取provider对象
    def get_provider(self, provider_id:str) -> KnowledgeProvider:
        return self.providers_dict.get(provider_id)
