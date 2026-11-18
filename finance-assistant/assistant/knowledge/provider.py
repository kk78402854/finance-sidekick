"""
这个模块作用定义知识检索的能力。

每个 Provider 负责一类数据源：
- api.*  直接调用金融中台接口，答案需要登录客户身份
- faq.*  查客服工程自己库里的 FAQ 表
- rag.*  调用外部知识库检索服务

Provider 统一返回 list[KnowledgeChunk]，由 knowledge_handler 拼成一段文本。
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from assistant.conf.config import settings
from assistant.domain.message import UserMessage
from assistant.domain.state import DialogueState
from assistant.utils.finance_client import (
    FinanceError,
    finance_request,
    money,
    resolve_customer_no,
    to_decimal,
)


@dataclass
class KnowledgeChunk:
    content: str
    source: str = ""


# 知识检索能力父类
class KnowledgeProvider(ABC):
    provider_id: str = ""

    async def execute(self, query: str, state: DialogueState,
                      user_message: UserMessage) -> list[KnowledgeChunk]:
        try:
            return await self.fetch(query=query, state=state, user_message=user_message)
        except FinanceError as exc:
            return [KnowledgeChunk(content=str(exc), source="系统")]
        except Exception:
            # 单个数据源异常不影响其他数据源
            return []

    @abstractmethod
    async def fetch(self, query: str, state: DialogueState,
                    user_message: UserMessage) -> list[KnowledgeChunk]:
        raise NotImplementedError


def _focused_account_no(state: DialogueState) -> str:
    focused = state.shared.focused_object
    if not focused:
        return ""
    if focused.type == "account":
        return str(focused.id or "")
    attributes = focused.attributes or {}
    return str(attributes.get("account_no") or "")


class ApiAccountProvider(KnowledgeProvider):
    provider_id = "api.account"

    async def fetch(self, query, state, user_message):
        customer_no = resolve_customer_no(state)
        account_no = _focused_account_no(state)
        try:
            if account_no:
                data = await finance_request("GET", f"/accounts/{account_no}",
                                             customer_no=customer_no)
                return [KnowledgeChunk(
                    content=json.dumps({"account_no": account_no, **data}, ensure_ascii=False),
                    source="银行核心-账户明细",
                )]
            data = await finance_request("GET", f"/customers/{customer_no}/accounts",
                                         customer_no=customer_no)
        except FinanceError as exc:
            return [KnowledgeChunk(content=str(exc), source="银行核心-账户")]
        return [KnowledgeChunk(content=json.dumps(data, ensure_ascii=False),
                               source="银行核心-账户列表")]


class ApiTransactionProvider(KnowledgeProvider):
    provider_id = "api.transaction"

    async def fetch(self, query, state, user_message):
        account_no = _focused_account_no(state)
        if not account_no:
            return [KnowledgeChunk(
                content="没有定位到要查询的账户，请提供账户号或先选择账户。",
                source="银行核心-交易流水",
            )]
        start = (date.today() - timedelta(days=30)).isoformat()
        end = date.today().isoformat()
        try:
            data = await finance_request(
                "GET",
                f"/accounts/{account_no}/transactions",
                customer_no=resolve_customer_no(state),
                params={
                    "start_time": f"{start}T00:00:00",
                    "end_time": f"{end}T23:59:59",
                    "page_no": 1,
                    "page_size": 20,
                },
            )
        except FinanceError as exc:
            return [KnowledgeChunk(content=str(exc), source="银行核心-交易流水")]
        return [KnowledgeChunk(
            content=json.dumps({"account_no": account_no, "start": start, "end": end, **data},
                               ensure_ascii=False),
            source="银行核心-交易流水",
        )]


class ApiLoanProvider(KnowledgeProvider):
    provider_id = "api.loan"

    async def fetch(self, query, state, user_message):
        customer_no = resolve_customer_no(state)
        try:
            data = await finance_request("GET", "/loan/products", customer_no=customer_no)
        except FinanceError as exc:
            return [KnowledgeChunk(content=str(exc), source="贷款产品")]

        products = (data.get("list") or [])[:8]
        details = []
        for product in products:
            code = product.get("product_code")
            if not code:
                continue
            try:
                detail_data = await finance_request(
                    "GET", f"/loan/products/{code}", customer_no=customer_no)
            except FinanceError:
                continue
            detail = detail_data.get("product_detail") or {}
            details.append({
                "product_code": code,
                "product_name": detail.get("product_name", ""),
                "loan_type": detail.get("loan_type", ""),
                "rate_range": product.get("rate_range", ""),
                "term_range": product.get("term_range", ""),
                "min_amount": detail.get("min_amount"),
                "max_amount": detail.get("max_amount"),
                "repayment_method": detail.get("repayment_method", ""),
            })

        if not details:
            return []
        return [KnowledgeChunk(
            content=json.dumps({"loan_products": details}, ensure_ascii=False),
            source="贷款产品库",
        )]


class ApiWealthProvider(KnowledgeProvider):
    provider_id = "api.wealth"

    async def fetch(self, query, state, user_message):
        try:
            data = await finance_request("GET", "/wealth/products",
                                         customer_no=resolve_customer_no(state))
        except FinanceError as exc:
            return [KnowledgeChunk(content=str(exc), source="理财产品")]

        records = (data.get("list") or [])[:10]
        for item in records:
            # 只有金额字段做千分位；收益率保持原值，避免把 4.5% 格式化成金额
            for key in ("min_amount", "max_amount"):
                if key in item and item[key] is not None:
                    item[key] = money(item[key])
        return [KnowledgeChunk(content=json.dumps({"wealth_products": records},
                                                  ensure_ascii=False),
                               source="理财产品库")]


class ApiDepositProvider(KnowledgeProvider):
    provider_id = "api.deposit"

    async def fetch(self, query, state, user_message):
        try:
            data = await finance_request("GET", "/foundation/account-products",
                                         customer_no=resolve_customer_no(state))
        except FinanceError as exc:
            return [KnowledgeChunk(content=str(exc), source="存款产品")]

        records = (data.get("list") or [])[:10]
        for item in records:
            for key in ("min_amount", "max_amount"):
                if key in item and item[key] is not None:
                    item[key] = money(item[key])
        return [KnowledgeChunk(content=json.dumps({"deposit_products": records},
                                                  ensure_ascii=False),
                               source="存款产品库")]


def _bigrams(text: str) -> set[str]:
    text = "".join(str(text or "").split())
    return {text[i:i + 2] for i in range(max(len(text) - 1, 0))}


class FaqProvider(KnowledgeProvider):
    """FAQ 存在客服工程自己的库里，按关键词和二元组重叠打分召回。"""

    provider_id = "faq.default"

    async def fetch(self, query, state, user_message):
        from assistant.repository.faq_repository import fetch_faq_rows

        rows = await fetch_faq_rows()
        if not rows:
            return []

        query_grams = _bigrams(query)
        scored: list[tuple[float, dict]] = []
        for row in rows:
            keywords = [item.strip() for item in str(row.get("keywords") or "")
                        .replace("，", ",").replace("、", ",").split(",") if item.strip()]
            keyword_hit = sum(2.0 for word in keywords if word in query)
            gram_hit = 0.5 * len(query_grams & _bigrams(f"{row.get('question', '')}"))
            score = keyword_hit + gram_hit
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        chunks = []
        for _, row in scored[:3]:
            chunks.append(KnowledgeChunk(
                content=f"问：{row.get('question', '')}\n答：{row.get('answer', '')}",
                source="客服FAQ",
            ))
        return chunks


class RagProvider(KnowledgeProvider):
    provider_id = "rag.default"

    async def fetch(self, query, state, user_message):
        base_url = (settings.finance_rag_base_url or "").rstrip("/")
        if not base_url:
            return []
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{base_url}/retrieve",
                                     json={"query": query, "top_k": 3})
            resp.raise_for_status()
            payload = resp.json()
        chunks = (payload.get("data") or {}).get("chunks") or []
        return [KnowledgeChunk(
            content=str(item.get("content") or ""),
            source=str(item.get("source") or "知识库"),
        ) for item in chunks if item.get("content")]


def register_default_providers() -> dict[str, KnowledgeProvider]:
    """注册顺序就是答案的优先级顺序。"""
    providers: list[KnowledgeProvider] = [
        ApiAccountProvider(),
        ApiTransactionProvider(),
        ApiLoanProvider(),
        ApiWealthProvider(),
        ApiDepositProvider(),
        FaqProvider(),
        RagProvider(),
    ]
    return {provider.provider_id: provider for provider in providers}
