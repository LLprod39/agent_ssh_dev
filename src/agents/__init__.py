"""
Agents module for SSH Agent with LLM integration.

This module contains all agent classes responsible for task planning,
execution, and error handling.
"""

from .task_master_integration import TaskMasterIntegration
from .task_agent import TaskAgent, TaskPlanningContext
from .subtask_agent import SubtaskAgent, Subtask, SubtaskPlanningContext, SubtaskPlanningResult

# Импорты других агентов будут добавлены по мере их создания
# from .executor import Executor
from .error_handler import ErrorHandler, ErrorReport, ServerSnapshot, ErrorPattern, ErrorReportType, ServerSnapshotType

__all__ = [
    "TaskMasterIntegration",
    "TaskAgent",
    "TaskPlanningContext",
    "SubtaskAgent",
    "Subtask",
    "SubtaskPlanningContext",
    "SubtaskPlanningResult",
    "ErrorHandler",
    "ErrorReport",
    "ServerSnapshot",
    "ErrorPattern",
    "ErrorReportType",
    "ServerSnapshotType",
    # "Executor"
]
