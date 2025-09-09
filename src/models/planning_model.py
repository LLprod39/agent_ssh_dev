"""
Модели данных для планирования задач
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum
from datetime import datetime
import uuid


class TaskStatus(Enum):
    """Статус задачи"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Статус шага"""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Priority(Enum):
    """Приоритет задачи"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskStep:
    """Шаг выполнения задачи"""
    
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    priority: Priority = Priority.MEDIUM
    estimated_duration: Optional[int] = None  # в минутах
    dependencies: List[str] = field(default_factory=list)  # ID зависимых шагов
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    error_count: int = 0
    max_errors: int = 4
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_ready_to_execute(self, completed_steps: List[str]) -> bool:
        """Проверка готовности к выполнению"""
        return all(dep in completed_steps for dep in self.dependencies)
    
    def can_retry(self) -> bool:
        """Проверка возможности повторной попытки"""
        return self.error_count < self.max_errors
    
    def mark_started(self):
        """Отметить начало выполнения"""
        self.status = StepStatus.EXECUTING
        self.started_at = datetime.now()
    
    def mark_completed(self):
        """Отметить завершение"""
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def mark_failed(self):
        """Отметить неудачу"""
        self.status = StepStatus.FAILED
        self.error_count += 1
    
    def add_subtask(self, subtask: Dict[str, Any]):
        """Добавить подзадачу"""
        self.subtasks.append(subtask)
    
    def get_duration(self) -> Optional[float]:
        """Получить длительность выполнения в минутах"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() / 60
        return None


@dataclass
class Task:
    """Основная задача"""
    
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.MEDIUM
    steps: List[TaskStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_estimated_duration: Optional[int] = None  # в минутах
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)  # Контекст для LLM
    
    def add_step(self, step: TaskStep) -> str:
        """Добавить шаг к задаче"""
        self.steps.append(step)
        return step.step_id
    
    def get_step(self, step_id: str) -> Optional[TaskStep]:
        """Получить шаг по ID"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_pending_steps(self) -> List[TaskStep]:
        """Получить ожидающие шаги"""
        return [step for step in self.steps if step.status == StepStatus.PENDING]
    
    def get_ready_steps(self) -> List[TaskStep]:
        """Получить готовые к выполнению шаги"""
        completed_step_ids = [step.step_id for step in self.steps if step.status == StepStatus.COMPLETED]
        return [step for step in self.get_pending_steps() if step.is_ready_to_execute(completed_step_ids)]
    
    def get_failed_steps(self) -> List[TaskStep]:
        """Получить неудачные шаги"""
        return [step for step in self.steps if step.status == StepStatus.FAILED]
    
    def get_completed_steps(self) -> List[TaskStep]:
        """Получить завершенные шаги"""
        return [step for step in self.steps if step.status == StepStatus.COMPLETED]
    
    def is_completed(self) -> bool:
        """Проверка завершения задачи"""
        return all(step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for step in self.steps)
    
    def is_failed(self) -> bool:
        """Проверка неудачи задачи"""
        return any(step.status == StepStatus.FAILED and not step.can_retry() for step in self.steps)
    
    def get_progress(self) -> Dict[str, Any]:
        """Получить прогресс выполнения"""
        total_steps = len(self.steps)
        completed_steps = len(self.get_completed_steps())
        failed_steps = len(self.get_failed_steps())
        pending_steps = len(self.get_pending_steps())
        
        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "pending_steps": pending_steps,
            "progress_percentage": (completed_steps / total_steps * 100) if total_steps > 0 else 0,
            "is_completed": self.is_completed(),
            "is_failed": self.is_failed()
        }
    
    def mark_started(self):
        """Отметить начало выполнения"""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()
    
    def mark_completed(self):
        """Отметить завершение"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def mark_failed(self):
        """Отметить неудачу"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
    
    def get_duration(self) -> Optional[float]:
        """Получить длительность выполнения в минутах"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() / 60
        return None


@dataclass
class PlanningResult:
    """Результат планирования"""
    
    success: bool
    task: Optional[Task] = None
    error_message: Optional[str] = None
    planning_duration: Optional[float] = None  # в секундах
    llm_usage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        result = {
            "success": self.success,
            "error_message": self.error_message,
            "planning_duration": self.planning_duration,
            "llm_usage": self.llm_usage,
            "metadata": self.metadata
        }
        
        if self.task:
            result["task"] = {
                "task_id": self.task.task_id,
                "title": self.task.title,
                "description": self.task.description,
                "status": self.task.status.value,
                "priority": self.task.priority.value,
                "steps": [
                    {
                        "step_id": step.step_id,
                        "title": step.title,
                        "description": step.description,
                        "status": step.status.value,
                        "priority": step.priority.value,
                        "dependencies": step.dependencies,
                        "estimated_duration": step.estimated_duration
                    }
                    for step in self.task.steps
                ],
                "progress": self.task.get_progress()
            }
        
        return result


@dataclass
class StepExecutionResult:
    """Результат выполнения шага"""
    
    step_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    duration: Optional[float] = None  # в секундах
    retry_count: int = 0
    autocorrection_applied: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "step_id": self.step_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "retry_count": self.retry_count,
            "autocorrection_applied": self.autocorrection_applied,
            "metadata": self.metadata
        }


@dataclass
class TaskExecutionResult:
    """Результат выполнения задачи"""
    
    task_id: str
    success: bool
    completed_steps: List[StepExecutionResult] = field(default_factory=list)
    failed_steps: List[StepExecutionResult] = field(default_factory=list)
    total_duration: Optional[float] = None  # в секундах
    error_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "completed_steps": [step.to_dict() for step in self.completed_steps],
            "failed_steps": [step.to_dict() for step in self.failed_steps],
            "total_duration": self.total_duration,
            "error_summary": self.error_summary,
            "metadata": self.metadata
        }
