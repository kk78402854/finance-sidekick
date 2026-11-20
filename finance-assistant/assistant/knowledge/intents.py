"""
这个模块作用定义知识检索范围。

intent.id 由 LLM 输出，provider_ids 决定去哪些数据源取数，
provider_id 必须与 assistant/knowledge/provider.py 里注册的一致。
"""
from dataclasses import dataclass, field


# 定义知识检索范围，不同范围对应不同答案位置
@dataclass
class KnowledgeIntent:
    id: str  # 意图识别值，例如 account_info
    description: str  # 让 llm 更好理解 id 含义
    # 问题答案位置，对应 Provider 类里的 provider_id
    provider_ids: list[str] = field(default_factory=list)
    # 需要业务对象时，值必须与对象消息的 type 一致
    requires_object: str | None = None


KNOWLEDGE_INTENTS: dict[str, KnowledgeIntent] = {
    # ---------- 需要业务对象的意图 ----------
    "account_info": KnowledgeIntent(
        id="account_info",
        description="账户、余额、可用余额、冻结金额咨询",
        provider_ids=["api.account"],
        requires_object="account",
    ),
    "transaction_info": KnowledgeIntent(
        id="transaction_info",
        description="交易流水、消费记录、收支明细咨询",
        provider_ids=["api.transaction"],
        requires_object="transaction",
    ),
    "card_info": KnowledgeIntent(
        id="card_info",
        description="银行卡、信用卡信息咨询",
        provider_ids=["api.account"],
        requires_object="card",
    ),

    # ---------- 产品咨询 ----------
    "loan_product_info": KnowledgeIntent(
        id="loan_product_info", description="贷款产品、利率、期限咨询",
        provider_ids=["api.loan", "faq.default", "rag.default"],
    ),
    "wealth_product_info": KnowledgeIntent(
        id="wealth_product_info", description="理财产品咨询",
        provider_ids=["api.wealth", "faq.default", "rag.default"],
    ),
    "fund_product_info": KnowledgeIntent(
        id="fund_product_info", description="基金产品咨询",
        provider_ids=["api.wealth", "faq.default", "rag.default"],
    ),
    "deposit_product_info": KnowledgeIntent(
        id="deposit_product_info", description="存款、账户产品咨询",
        provider_ids=["api.deposit", "faq.default", "rag.default"],
    ),
    "credit_card_info": KnowledgeIntent(
        id="credit_card_info", description="信用卡年费、权益、额度咨询",
        provider_ids=["faq.default", "rag.default"],
    ),

    # ---------- FAQ / 知识库 ----------
    "bank_branch_info": KnowledgeIntent(
        id="bank_branch_info",
        description="开户行、网点地址、营业时间、联系电话、银行基本信息咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    "account_service_info": KnowledgeIntent(
        id="account_service_info",
        description="转账限额、短信通知、账户功能与收费标准咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    "interest_rate": KnowledgeIntent(
        id="interest_rate", description="利率说明",
        provider_ids=["faq.default", "rag.default"],
    ),
    "fee_rule": KnowledgeIntent(
        id="fee_rule", description="手续费规则",
        provider_ids=["faq.default", "rag.default"],
    ),
    "early_repayment": KnowledgeIntent(
        id="early_repayment", description="提前还款政策",
        provider_ids=["faq.default", "rag.default"],
    ),
    "credit_card_repayment": KnowledgeIntent(
        id="credit_card_repayment", description="信用卡还款规则",
        provider_ids=["faq.default", "rag.default"],
    ),
    "risk_disclosure": KnowledgeIntent(
        id="risk_disclosure", description="风险提示与合规说明",
        provider_ids=["faq.default", "rag.default"],
    ),
    "product_intro": KnowledgeIntent(
        id="product_intro", description="金融产品介绍",
        provider_ids=["rag.default"],
    ),
    "usage_guide": KnowledgeIntent(
        id="usage_guide", description="业务办理和使用指南",
        provider_ids=["rag.default"],
    ),
    "finance_policy": KnowledgeIntent(
        id="finance_policy", description="金融政策和监管规则",
        provider_ids=["rag.default"],
    ),
    "general_finance_info": KnowledgeIntent(
        id="general_finance_info", description="通用金融信息、知识库资料、银行综合服务咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
}
