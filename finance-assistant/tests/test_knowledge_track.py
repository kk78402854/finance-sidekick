"""
知识轨道回归测试：空检索不编造答案、新增意图能正确路由、FAQ 种子数据完整。

测试不连数据库、不调 LLM，可在 CI 离线运行。
"""
import json
import os
from pathlib import Path

# 在导入 assistant 模块前提供最小配置，保证无 .env 的 CI 环境也能导入
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")
os.environ.setdefault("DATABASE_URL", "mysql+aiomysql://u:p@127.0.0.1:3306/test")
os.environ.setdefault("APP_HOST", "127.0.0.1")
os.environ.setdefault("APP_PORT", "18083")

from assistant.domain.message import MessageType, UserMessage  # noqa: E402
from assistant.domain.state import DialogueState  # noqa: E402
from assistant.knowledge.knowledge_handler import KnowledgeHandler  # noqa: E402
from assistant.knowledge.provider import KnowledgeChunk  # noqa: E402
from assistant.knowledge.responder import KNOWLEDGE_EMPTY_REPLY, KnowledgeResponder  # noqa: E402

SEED_FILE = Path(__file__).parents[1] / "seeds" / "faq_items.json"


def _state() -> DialogueState:
    state = DialogueState(sender_id="S1")
    state.shared.create_session()
    return state


def _user_message() -> UserMessage:
    return UserMessage(
        sender_id="S1",
        message_id="m1",
        type=MessageType.TEXT,
        text="查询知识库里的银行信息",
    )


async def test_empty_chunks_returns_deterministic_fallback() -> None:
    result = await KnowledgeResponder().respond(
        chunks=[], state=_state(), user_message=_user_message(),
    )
    assert result.text == KNOWLEDGE_EMPTY_REPLY
    assert "暂未查询到" in result.text


async def test_blank_chunks_returns_deterministic_fallback() -> None:
    result = await KnowledgeResponder().respond(
        chunks=[KnowledgeChunk(content="   "), KnowledgeChunk(content="")],
        state=_state(),
        user_message=_user_message(),
    )
    assert result.text == KNOWLEDGE_EMPTY_REPLY


def test_bank_intents_route_to_faq_and_rag() -> None:
    handler = KnowledgeHandler(knowledge_registry=None, knowledge_responder=None)
    assert handler.get_provider_ids(["bank_branch_info"]) == ["faq.default", "rag.default"]
    assert handler.get_provider_ids(["account_service_info"]) == ["faq.default", "rag.default"]
    # 未知意图不应抛异常
    assert handler.get_provider_ids(["not_exists"]) == []


def test_faq_seed_file_is_complete() -> None:
    items = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    assert len(items) >= 15

    questions = {item["question"] for item in items}
    assert len(questions) == len(items), "FAQ 种子问题不能重复"

    for item in items:
        assert item["question"].strip()
        assert item["answer"].strip()
        assert item["keywords"].strip()
        assert item["category"].strip()
