"""
维护engine层注入关系
"""
from pathlib import Path

from assistant.chitchat import chit_chat
from assistant.chitchat.chit_chat import ChitChatHandler
from assistant.clarify.clarify_response import ClarifyResponse
from assistant.engine.dialogue_engine import DialogueEngine
from assistant.knowledge.knowledge_handler import KnowledgeHandler
from assistant.knowledge.provider import register_default_providers
from assistant.knowledge.registry import KnowledgeProviderRegistry
from assistant.knowledge.responder import KnowledgeResponder
from assistant.plan.turn_plan_validator import TurnPlanValidator
from assistant.plan.turn_planner import TurnPlanner
from assistant.task.action.action_runner import ActionRunner
from assistant.task.action.builder import register_custom_action
from assistant.task.action.registry import ActionRegistry
from assistant.task.command.command_processor import CommandProcessor
from assistant.task.flow.loader import FlowLoader
from assistant.task.flow.models import FlowCatalog
from assistant.task.flowexecutor.flow_executor import FlowExecutor
from assistant.task.response.response_render import ResponseRender
from assistant.task.task_handler import TaskHandler
from assistant.task.tasklifecycle.task_lifecycle import TaskLifecycleResponder


def build_engine()->DialogueEngine:

    # 创建FlowCatalog对象
    flow_path = Path(__file__).parents[2]/'flow_config'/'user_flows.yml'
    flow_catalog:FlowCatalog =FlowLoader().load(flow_path)

    # 意图识别对象
    turn_planner = TurnPlanner()
    # 校验
    turn_plan_validator = TurnPlanValidator()

    # 任务流程
    command_processor = CommandProcessor()
    task_lifycycle = TaskLifecycleResponder(
        flow_catalog=flow_catalog,
    )

    response_render = ResponseRender()
    action_registry = ActionRegistry()
    # 调用方法，扫描 custom/ 目录自动注册所有 Action
    register_custom_action(action_registry=action_registry,)

    action_runner = ActionRunner(action_registry=action_registry,)

    flow_executor = FlowExecutor(
        response_render=response_render,
        action_runner=action_runner,
    )
    task_handler = TaskHandler(
        command_processor=command_processor,
        task_lifecycle=task_lifycycle,
        flow_catalog=flow_catalog,
        flow_executor=flow_executor,
    )

    chit_chat = ChitChatHandler()
    clarify_response = ClarifyResponse()

    knowledge_registry = KnowledgeProviderRegistry(
        provider_objects=list(register_default_providers().values())
    )

    knowledge_handler = KnowledgeHandler(
        knowledge_responder=KnowledgeResponder(),
        knowledge_registry=knowledge_registry
    )
    return DialogueEngine(
        turn_planner=turn_planner,
        turn_plan_validator=turn_plan_validator,
        task_handler=task_handler,
        chit_chat=chit_chat,
        clarify_response=clarify_response,
        knowledge_handler=knowledge_handler
    )