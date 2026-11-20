"""
创建路由
"""
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, Header

from assistant.api.dependencies import get_dialogue_service
from assistant.api.schemas import ChatMessage, ChatObject, ChatRequest, ChatResponse, HistoryMessage, HistoryResponse
from assistant.domain.message import MessageObject, MessageType, ProcessResult, UserMessage
from assistant.domain.state import DialogueState, Session, Turn
from assistant.service.dialogue_service import DialogueService

chat_router = APIRouter()


@chat_router.post("/api/chat")
async def chat(chat_request:ChatRequest,
       dialogue_service:DialogueService=Depends(get_dialogue_service),
       x_customer_no: str | None = Header(default=None, alias="X-Customer-No")
                                    )->ChatResponse:
    # 1 chat_request 封装前端提交过来的数据
    ## fastapi封装
    # 2 注入service对象
    # Depends
    # 3 调用service方法实现

    # 1 数据模型转换过程
    # 调用service方法，把api层数据模型 转换 service层数据模型
    # ChatRequest -->  UserMessage
    user_message:UserMessage = _build_user_message(chat_request, x_customer_no)

    # 2 调用service方法实现
    process_result:ProcessResult = await dialogue_service.run(user_message)

    # 3 把service层返回数据 ProcessResult --> api层类型 ChatResponse
    chat_response:ChatResponse = _build_response_message(process_result)
    return chat_response

    # 返回模拟数据，流程跑通
    # return ChatResponse(
    #     sender_id=chat_request.sender_id,
    #     message_id=str(uuid.uuid4()),
    #     messages=[ChatMessage(
    #         text="hello",
    #         object=None
    #     )],
    # )

# 调用service方法，把api层数据模型 转换 service层数据模型
    # ChatRequest -->  UserMessage
def _build_user_message(chat_request:ChatRequest,
                        x_customer_no: str | None = None)->UserMessage:
    return UserMessage(
        sender_id=chat_request.sender_id,
        # 消息id，判断存在使用，不存在生成
        message_id=chat_request.message_id
               if chat_request.message_id else str(uuid.uuid4()),
        type=MessageType.TEXT if chat_request.text
                              else MessageType.OBJECT,
        text=chat_request.text,
        # 请求头优先于请求体，方便前端统一在拦截器里带身份
        customer_no=x_customer_no or chat_request.customer_no,
        object=MessageObject(
            id=chat_request.object.id,
            type=chat_request.object.type,
            title=chat_request.object.title,
            attributes=chat_request.object.attributes,
        ) if chat_request.object else None
    )


# 3 把service层返回数据 ProcessResult --> api层类型 ChatResponse
# ProcessResult -->  ChatResponse
def _build_response_message(process_result:ProcessResult)->ChatResponse:
    # list[BotMessage] --》 list[ChatMessage]
    return ChatResponse(
        sender_id=process_result.sender_id,
        message_id=process_result.message_id,
        messages=[
            # ChatMessage对象
            ChatMessage(
                text=bot_message.text,
                object=ChatObject(
                    **asdict(bot_message.object)
                ) if bot_message.object else None
            )
            for bot_message in process_result.messages
        ]
    )


# 接口：根据当前用户id查询用户历史会话记录
@chat_router.get("/api/chat/history")
async def chat_history(sender_id:str,
            dialogue_service:DialogueService=Depends(get_dialogue_service)
                       )->HistoryResponse:
    # 1 获取当前用户id sender_id
    # 2 调用service方法根据sender_id查询用户历史消息数据
    history_data:DialogueState = (
        await dialogue_service.get_history_data_sender_id(sender_id))

    # 3 把数据查返回history_data:DialogueState，封装HistoryResponse对象
    ## 从history_data获取所有sessions列表
    sessions:list[Session] = history_data.shared.sessions

    # 遍历sessions列表得到每个session会话对象
    messages:list[HistoryMessage] = []
    for session in sessions:
        # 每个session对象获取turns列表
        turns:list[Turn] = session.turns
        # 遍历turns列表得到每个turn
        for turn in turns:
            # 封装用户提问
            messages.append(HistoryMessage(
                ## 用户提问 user  客服回复 bot
                role="user",
                text=turn.user_message.text,
                object=ChatObject(
                    **asdict(turn.user_message.object)
                ) if turn.user_message.object else None
            ))

            # 封装客服回复 回复有多个，列表形式
            messages.extend([
                    HistoryMessage(
                        role="bot",
                        text=bot_message.text,
                        object=None
                    )
                    for bot_message in turn.bot_message
                ]
            )

    return HistoryResponse(
        sender_id=sender_id,
        messages= messages
    )
