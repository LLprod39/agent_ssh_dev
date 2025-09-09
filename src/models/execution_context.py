"""
Контекст выполнения команд
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable

from ..agents.subtask_agent import Subtask
from ..agents.task_master_integration import TaskMasterIntegration


@dataclass
class ExecutionContext:
    """Контекст выполнения"""
    
    subtask: Subtask
    ssh_connection: Any  # SSHConnector или мок объект
    server_info: Dict[str, Any]
    environment: Dict[str, Any]
    progress_callback: Optional[Callable] = None
    task_master: Optional[TaskMasterIntegration] = None

