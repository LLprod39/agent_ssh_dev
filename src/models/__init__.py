"""
Models module for SSH Agent.

This module contains data models and LLM integration classes.
"""

# Новые модели планирования
from .planning_model import (
    Task,
    TaskStep,
    PlanningResult,
    StepExecutionResult,
    TaskExecutionResult,
    TaskStatus,
    StepStatus,
    Priority
)

# Интерфейс LLM
from .llm_interface import (
    LLMInterface,
    LLMRequest,
    LLMResponse,
    OpenAIInterface,
    MockLLMInterface,
    LLMInterfaceFactory,
    LLMRequestBuilder
)

# Execution Model
from .execution_model import (
    ExecutionModel,
    SubtaskExecutionResult
)
from .command_result import CommandResult, ExecutionStatus
from .execution_context import ExecutionContext

try:
    from .data_models import (
        ServerInfo,
        Step,
        Subtask,
        CommandResult,
        ExecutionResult,
        ErrorReport,
        TaskResult
    )
except ImportError:
    # Если старые модели не существуют, создаем заглушки
    ServerInfo = Step = Subtask = CommandResult = ExecutionResult = ErrorReport = TaskResult = None

__all__ = [
    # Новые модели планирования
    "Task",
    "TaskStep", 
    "PlanningResult",
    "StepExecutionResult",
    "TaskExecutionResult",
    "TaskStatus",
    "StepStatus",
    "Priority",
    
    # LLM интерфейс
    "LLMInterface",
    "LLMRequest",
    "LLMResponse", 
    "OpenAIInterface",
    "MockLLMInterface",
    "LLMInterfaceFactory",
    "LLMRequestBuilder",
    
    # Execution Model
    "ExecutionModel",
    "ExecutionStatus",
    "CommandResult",
    "SubtaskExecutionResult", 
    "ExecutionContext",
    
    # Старые модели (для совместимости)
    "ServerInfo",
    "Step",
    "Subtask",
    "ExecutionResult",
    "ErrorReport",
    "TaskResult"
]
