"""
Система эскалации - Шаг 4.2

Этот модуль отвечает за:
- Отправку логов планировщику при превышении порога
- Механизм пересмотра планов
- Систему эскалации к человеку-оператору
- Координацию между агентами при эскалации
"""
import time
import json
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from ..config.agent_config import AgentConfig
from ..agents.error_handler import ErrorHandler, ErrorReport, ErrorReportType
from ..agents.task_agent import TaskAgent
from ..agents.subtask_agent import SubtaskAgent
from ..models.planning_model import Task, TaskStep, StepStatus
from ..utils.logger import StructuredLogger


class EscalationType(Enum):
    """Тип эскалации"""
    PLANNER_NOTIFICATION = "planner_notification"
    PLAN_REVISION = "plan_revision"
    HUMAN_ESCALATION = "human_escalation"
    EMERGENCY_STOP = "emergency_stop"


class EscalationStatus(Enum):
    """Статус эскалации"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EscalationRequest:
    """Запрос на эскалацию"""
    
    escalation_id: str
    escalation_type: EscalationType
    step_id: str
    task_id: str
    reason: str
    error_count: int
    threshold_exceeded: int
    timestamp: datetime
    error_details: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    status: EscalationStatus = EscalationStatus.PENDING
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "escalation_id": self.escalation_id,
            "escalation_type": self.escalation_type.value,
            "step_id": self.step_id,
            "task_id": self.task_id,
            "reason": self.reason,
            "error_count": self.error_count,
            "threshold_exceeded": self.threshold_exceeded,
            "timestamp": self.timestamp.isoformat(),
            "error_details": self.error_details,
            "context": self.context,
            "status": self.status.value,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata
        }


@dataclass
class PlanRevisionRequest:
    """Запрос на пересмотр плана"""
    
    revision_id: str
    task_id: str
    step_id: str
    original_plan: Dict[str, Any]
    error_analysis: Dict[str, Any]
    suggested_changes: List[str]
    priority: str
    timestamp: datetime
    status: EscalationStatus = EscalationStatus.PENDING
    revised_plan: Optional[Dict[str, Any]] = None
    revision_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "revision_id": self.revision_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "original_plan": self.original_plan,
            "error_analysis": self.error_analysis,
            "suggested_changes": self.suggested_changes,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "revised_plan": self.revised_plan,
            "revision_reason": self.revision_reason,
            "metadata": self.metadata
        }


class EscalationSystem:
    """
    Система эскалации
    
    Основные возможности:
    - Отправка логов планировщику при превышении порога
    - Механизм пересмотра планов
    - Система эскалации к человеку-оператору
    - Координация между агентами при эскалации
    """
    
    def __init__(self, config: AgentConfig, error_handler: ErrorHandler,
                 task_agent: TaskAgent, subtask_agent: SubtaskAgent):
        """
        Инициализация системы эскалации
        
        Args:
            config: Конфигурация агентов
            error_handler: Обработчик ошибок
            task_agent: Агент планирования задач
            subtask_agent: Агент планирования подзадач
        """
        self.config = config
        self.error_handler = error_handler
        self.task_agent = task_agent
        self.subtask_agent = subtask_agent
        self.logger = StructuredLogger("EscalationSystem")
        
        # Хранилище эскалаций
        self.escalation_requests: Dict[str, EscalationRequest] = {}
        self.plan_revision_requests: Dict[str, PlanRevisionRequest] = {}
        
        # Колбэки для уведомлений
        self.human_escalation_callbacks: List[Callable[[EscalationRequest], None]] = []
        self.plan_revision_callbacks: List[Callable[[PlanRevisionRequest], None]] = []
        
        # Статистика
        self.escalation_stats = {
            "total_escalations": 0,
            "planner_notifications": 0,
            "plan_revisions": 0,
            "human_escalations": 0,
            "emergency_stops": 0,
            "resolved_escalations": 0,
            "failed_escalations": 0
        }
        
        # Настройки эскалации
        self.escalation_config = {
            "planner_notification_threshold": config.error_handler.error_threshold_per_step,
            "plan_revision_threshold": config.error_handler.error_threshold_per_step + 1,
            "human_escalation_threshold": config.error_handler.human_escalation_threshold,
            "emergency_stop_threshold": config.error_handler.human_escalation_threshold + 2,
            "escalation_cooldown_minutes": config.error_handler.escalation_cooldown_minutes,
            "max_concurrent_escalations": 5,
            "auto_resolve_timeout_hours": 24
        }
        
        self.logger.info(
            "Система эскалации инициализирована",
            planner_threshold=self.escalation_config["planner_notification_threshold"],
            human_threshold=self.escalation_config["human_escalation_threshold"],
            cooldown_minutes=self.escalation_config["escalation_cooldown_minutes"]
        )
    
    def register_human_escalation_callback(self, callback: Callable[[EscalationRequest], None]):
        """Регистрация колбэка для эскалации к человеку"""
        self.human_escalation_callbacks.append(callback)
        self.logger.info("Колбэк эскалации к человеку зарегистрирован")
    
    def register_plan_revision_callback(self, callback: Callable[[PlanRevisionRequest], None]):
        """Регистрация колбэка для пересмотра планов"""
        self.plan_revision_callbacks.append(callback)
        self.logger.info("Колбэк пересмотра планов зарегистрирован")
    
    def handle_escalation(self, step_id: str, task: Task, error_count: int, 
                         error_details: Dict[str, Any]) -> Optional[EscalationRequest]:
        """
        Обработка эскалации
        
        Args:
            step_id: ID шага с ошибками
            task: Задача, содержащая шаг
            error_details: Детали ошибок
            
        Returns:
            Запрос на эскалацию если требуется
        """
        self.logger.info("Обработка эскалации", step_id=step_id, task_id=task.task_id, error_count=error_count)
        
        # Определяем тип эскалации
        escalation_type = self._determine_escalation_type(error_count)
        
        if escalation_type == EscalationType.PLANNER_NOTIFICATION:
            return self._handle_planner_notification(step_id, task, error_count, error_details)
        elif escalation_type == EscalationType.PLAN_REVISION:
            return self._handle_plan_revision(step_id, task, error_count, error_details)
        elif escalation_type == EscalationType.HUMAN_ESCALATION:
            return self._handle_human_escalation(step_id, task, error_count, error_details)
        elif escalation_type == EscalationType.EMERGENCY_STOP:
            return self._handle_emergency_stop(step_id, task, error_count, error_details)
        
        return None
    
    def _determine_escalation_type(self, error_count: int) -> Optional[EscalationType]:
        """Определение типа эскалации на основе количества ошибок"""
        if error_count >= self.escalation_config["emergency_stop_threshold"]:
            return EscalationType.EMERGENCY_STOP
        elif error_count >= self.escalation_config["human_escalation_threshold"]:
            return EscalationType.HUMAN_ESCALATION
        elif error_count >= self.escalation_config["plan_revision_threshold"]:
            return EscalationType.PLAN_REVISION
        elif error_count >= self.escalation_config["planner_notification_threshold"]:
            return EscalationType.PLANNER_NOTIFICATION
        
        return None
    
    def _handle_planner_notification(self, step_id: str, task: Task, error_count: int,
                                   error_details: Dict[str, Any]) -> EscalationRequest:
        """Обработка уведомления планировщика"""
        escalation_id = f"planner_notification_{step_id}_{int(time.time() * 1000)}"
        
        # Проверяем cooldown
        if self._is_in_cooldown(step_id, EscalationType.PLANNER_NOTIFICATION):
            self.logger.info("Эскалация к планировщику в cooldown", step_id=step_id)
            return None
        
        escalation_request = EscalationRequest(
            escalation_id=escalation_id,
            escalation_type=EscalationType.PLANNER_NOTIFICATION,
            step_id=step_id,
            task_id=task.task_id,
            reason=f"Превышен порог ошибок для планировщика: {error_count}/{self.escalation_config['planner_notification_threshold']}",
            error_count=error_count,
            threshold_exceeded=self.escalation_config["planner_notification_threshold"],
            timestamp=datetime.now(),
            error_details=error_details,
            context={
                "task_title": task.title,
                "step_title": task.get_step(step_id).title if task.get_step(step_id) else "Unknown",
                "escalation_level": "planner"
            }
        )
        
        # Сохраняем запрос
        self.escalation_requests[escalation_id] = escalation_request
        self.escalation_stats["total_escalations"] += 1
        self.escalation_stats["planner_notifications"] += 1
        
        # Отправляем отчет планировщику через Error Handler
        error_report = self.error_handler.handle_step_error(step_id, task, error_details)
        
        if error_report:
            escalation_request.status = EscalationStatus.IN_PROGRESS
            escalation_request.metadata["error_report_id"] = error_report.report_id
            
            self.logger.info(
                "Уведомление планировщика отправлено",
                escalation_id=escalation_id,
                step_id=step_id,
                error_report_id=error_report.report_id
            )
        else:
            escalation_request.status = EscalationStatus.FAILED
            self.escalation_stats["failed_escalations"] += 1
            
            self.logger.error(
                "Не удалось отправить уведомление планировщику",
                escalation_id=escalation_id,
                step_id=step_id
            )
        
        return escalation_request
    
    def _handle_plan_revision(self, step_id: str, task: Task, error_count: int,
                            error_details: Dict[str, Any]) -> EscalationRequest:
        """Обработка пересмотра плана"""
        escalation_id = f"plan_revision_{step_id}_{int(time.time() * 1000)}"
        
        # Проверяем cooldown
        if self._is_in_cooldown(step_id, EscalationType.PLAN_REVISION):
            self.logger.info("Пересмотр плана в cooldown", step_id=step_id)
            return None
        
        # Анализируем ошибки для пересмотра плана
        error_analysis = self._analyze_errors_for_revision(step_id, error_details)
        
        # Создаем запрос на пересмотр плана
        revision_request = PlanRevisionRequest(
            revision_id=f"revision_{escalation_id}",
            task_id=task.task_id,
            step_id=step_id,
            original_plan=self._extract_plan_data(task, step_id),
            error_analysis=error_analysis,
            suggested_changes=self._generate_plan_changes(error_analysis),
            priority="high" if error_count >= self.escalation_config["human_escalation_threshold"] else "medium",
            timestamp=datetime.now(),
            metadata={
                "escalation_id": escalation_id,
                "error_count": error_count
            }
        )
        
        # Создаем запрос на эскалацию
        escalation_request = EscalationRequest(
            escalation_id=escalation_id,
            escalation_type=EscalationType.PLAN_REVISION,
            step_id=step_id,
            task_id=task.task_id,
            reason=f"Требуется пересмотр плана: {error_count} ошибок",
            error_count=error_count,
            threshold_exceeded=self.escalation_config["plan_revision_threshold"],
            timestamp=datetime.now(),
            error_details=error_details,
            context={
                "task_title": task.title,
                "step_title": task.get_step(step_id).title if task.get_step(step_id) else "Unknown",
                "escalation_level": "plan_revision",
                "revision_request_id": revision_request.revision_id
            }
        )
        
        # Сохраняем запросы
        self.escalation_requests[escalation_id] = escalation_request
        self.plan_revision_requests[revision_request.revision_id] = revision_request
        self.escalation_stats["total_escalations"] += 1
        self.escalation_stats["plan_revisions"] += 1
        
        # Уведомляем колбэки
        for callback in self.plan_revision_callbacks:
            try:
                callback(revision_request)
            except Exception as e:
                self.logger.error("Ошибка в колбэке пересмотра плана", error=str(e))
        
        escalation_request.status = EscalationStatus.IN_PROGRESS
        
        self.logger.info(
            "Запрос на пересмотр плана создан",
            escalation_id=escalation_id,
            revision_id=revision_request.revision_id,
            step_id=step_id,
            suggested_changes=len(revision_request.suggested_changes)
        )
        
        return escalation_request
    
    def _handle_human_escalation(self, step_id: str, task: Task, error_count: int,
                               error_details: Dict[str, Any]) -> EscalationRequest:
        """Обработка эскалации к человеку"""
        escalation_id = f"human_escalation_{step_id}_{int(time.time() * 1000)}"
        
        # Проверяем cooldown
        if self._is_in_cooldown(step_id, EscalationType.HUMAN_ESCALATION):
            self.logger.info("Эскалация к человеку в cooldown", step_id=step_id)
            return None
        
        escalation_request = EscalationRequest(
            escalation_id=escalation_id,
            escalation_type=EscalationType.HUMAN_ESCALATION,
            step_id=step_id,
            task_id=task.task_id,
            reason=f"КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ: {error_count} ошибок требуют вмешательства человека",
            error_count=error_count,
            threshold_exceeded=self.escalation_config["human_escalation_threshold"],
            timestamp=datetime.now(),
            error_details=error_details,
            context={
                "task_title": task.title,
                "step_title": task.get_step(step_id).title if task.get_step(step_id) else "Unknown",
                "escalation_level": "human",
                "urgent": True
            }
        )
        
        # Сохраняем запрос
        self.escalation_requests[escalation_id] = escalation_request
        self.escalation_stats["total_escalations"] += 1
        self.escalation_stats["human_escalations"] += 1
        
        # Уведомляем человека-оператора
        for callback in self.human_escalation_callbacks:
            try:
                callback(escalation_request)
            except Exception as e:
                self.logger.error("Ошибка в колбэке эскалации к человеку", error=str(e))
        
        escalation_request.status = EscalationStatus.IN_PROGRESS
        
        self.logger.error(
            "КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ",
            escalation_id=escalation_id,
            step_id=step_id,
            task_id=task.task_id,
            error_count=error_count
        )
        
        return escalation_request
    
    def _handle_emergency_stop(self, step_id: str, task: Task, error_count: int,
                             error_details: Dict[str, Any]) -> EscalationRequest:
        """Обработка экстренной остановки"""
        escalation_id = f"emergency_stop_{step_id}_{int(time.time() * 1000)}"
        
        escalation_request = EscalationRequest(
            escalation_id=escalation_id,
            escalation_type=EscalationType.EMERGENCY_STOP,
            step_id=step_id,
            task_id=task.task_id,
            reason=f"ЭКСТРЕННАЯ ОСТАНОВКА: {error_count} ошибок - система нестабильна",
            error_count=error_count,
            threshold_exceeded=self.escalation_config["emergency_stop_threshold"],
            timestamp=datetime.now(),
            error_details=error_details,
            context={
                "task_title": task.title,
                "step_title": task.get_step(step_id).title if task.get_step(step_id) else "Unknown",
                "escalation_level": "emergency",
                "critical": True,
                "stop_execution": True
            }
        )
        
        # Сохраняем запрос
        self.escalation_requests[escalation_id] = escalation_request
        self.escalation_stats["total_escalations"] += 1
        self.escalation_stats["emergency_stops"] += 1
        
        # Уведомляем человека-оператора
        for callback in self.human_escalation_callbacks:
            try:
                callback(escalation_request)
            except Exception as e:
                self.logger.error("Ошибка в колбэке экстренной остановки", error=str(e))
        
        escalation_request.status = EscalationStatus.IN_PROGRESS
        
        self.logger.critical(
            "ЭКСТРЕННАЯ ОСТАНОВКА СИСТЕМЫ",
            escalation_id=escalation_id,
            step_id=step_id,
            task_id=task.task_id,
            error_count=error_count
        )
        
        return escalation_request
    
    def _is_in_cooldown(self, step_id: str, escalation_type: EscalationType) -> bool:
        """Проверка cooldown для эскалации"""
        cooldown_minutes = self.escalation_config["escalation_cooldown_minutes"]
        cutoff_time = datetime.now() - timedelta(minutes=cooldown_minutes)
        
        # Ищем недавние эскалации того же типа для того же шага
        for escalation in self.escalation_requests.values():
            if (escalation.step_id == step_id and 
                escalation.escalation_type == escalation_type and
                escalation.timestamp >= cutoff_time and
                escalation.status in [EscalationStatus.PENDING, EscalationStatus.IN_PROGRESS]):
                return True
        
        return False
    
    def _analyze_errors_for_revision(self, step_id: str, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ ошибок для пересмотра плана"""
        # Получаем статистику ошибок
        error_summary = self.error_handler.get_error_summary(step_id)
        
        # Анализируем паттерны ошибок
        recent_errors = self.error_handler.error_tracker.get_recent_errors(step_id, 24)
        
        error_patterns = {}
        for error in recent_errors:
            pattern = self._classify_error_pattern(error.error_message)
            error_patterns[pattern] = error_patterns.get(pattern, 0) + 1
        
        return {
            "error_count": error_summary.get("error_count", 0),
            "success_rate": error_summary.get("success_rate", 0),
            "error_patterns": error_patterns,
            "recent_errors": [
                {
                    "timestamp": error.timestamp.isoformat(),
                    "command": error.command,
                    "error_message": error.error_message[:200],
                    "severity": error.severity.value
                }
                for error in recent_errors[-5:]  # Последние 5 ошибок
            ],
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def _classify_error_pattern(self, error_message: str) -> str:
        """Классификация паттерна ошибки"""
        error_lower = error_message.lower()
        
        if any(pattern in error_lower for pattern in ["permission denied", "access denied"]):
            return "permission_denied"
        elif any(pattern in error_lower for pattern in ["command not found", "no such file"]):
            return "command_not_found"
        elif any(pattern in error_lower for pattern in ["connection refused", "timeout"]):
            return "connection_error"
        elif any(pattern in error_lower for pattern in ["syntax error", "invalid option"]):
            return "syntax_error"
        elif any(pattern in error_lower for pattern in ["file not found", "directory not found"]):
            return "file_not_found"
        elif any(pattern in error_lower for pattern in ["package not found", "unable to locate"]):
            return "package_error"
        else:
            return "unknown"
    
    def _extract_plan_data(self, task: Task, step_id: str) -> Dict[str, Any]:
        """Извлечение данных плана для пересмотра"""
        step = task.get_step(step_id)
        if not step:
            return {}
        
        return {
            "task_id": task.task_id,
            "task_title": task.title,
            "step_id": step.step_id,
            "step_title": step.title,
            "step_description": step.description,
            "step_priority": step.priority.value,
            "step_status": step.status.value,
            "estimated_duration": step.estimated_duration,
            "dependencies": step.dependencies,
            "metadata": step.metadata,
            "extraction_timestamp": datetime.now().isoformat()
        }
    
    def _generate_plan_changes(self, error_analysis: Dict[str, Any]) -> List[str]:
        """Генерация предложений по изменению плана"""
        changes = []
        
        error_patterns = error_analysis.get("error_patterns", {})
        success_rate = error_analysis.get("success_rate", 0)
        
        # Предложения на основе паттернов ошибок
        if "permission_denied" in error_patterns:
            changes.extend([
                "Добавить проверку прав доступа перед выполнением команд",
                "Использовать sudo для команд, требующих повышенных прав",
                "Проверить владельца файлов и директорий"
            ])
        
        if "command_not_found" in error_patterns:
            changes.extend([
                "Добавить проверку установки необходимых пакетов",
                "Обновить PATH переменную окружения",
                "Установить отсутствующие зависимости"
            ])
        
        if "connection_error" in error_patterns:
            changes.extend([
                "Добавить проверку сетевого соединения",
                "Увеличить timeout для сетевых операций",
                "Добавить retry логику для сетевых команд"
            ])
        
        if "syntax_error" in error_patterns:
            changes.extend([
                "Проверить синтаксис команд",
                "Убедиться в корректности параметров",
                "Проверить версию используемых инструментов"
            ])
        
        # Общие предложения на основе успешности
        if success_rate < 50:
            changes.extend([
                "Разбить шаг на более мелкие подзадачи",
                "Добавить дополнительные проверки перед выполнением",
                "Увеличить timeout для команд",
                "Добавить более детальные health-check команды"
            ])
        
        return list(set(changes))  # Убираем дубликаты
    
    def resolve_escalation(self, escalation_id: str, resolution: str, 
                          revised_plan: Optional[Dict[str, Any]] = None) -> bool:
        """
        Разрешение эскалации
        
        Args:
            escalation_id: ID эскалации
            resolution: Описание разрешения
            revised_plan: Пересмотренный план (если применимо)
            
        Returns:
            True если эскалация успешно разрешена
        """
        if escalation_id not in self.escalation_requests:
            self.logger.warning("Эскалация не найдена", escalation_id=escalation_id)
            return False
        
        escalation = self.escalation_requests[escalation_id]
        escalation.status = EscalationStatus.RESOLVED
        escalation.resolution = resolution
        escalation.resolved_at = datetime.now()
        
        # Если есть пересмотренный план, обновляем соответствующий запрос
        if revised_plan and escalation.escalation_type == EscalationType.PLAN_REVISION:
            revision_id = escalation.context.get("revision_request_id")
            if revision_id and revision_id in self.plan_revision_requests:
                revision_request = self.plan_revision_requests[revision_id]
                revision_request.status = EscalationStatus.RESOLVED
                revision_request.revised_plan = revised_plan
                revision_request.revision_reason = resolution
        
        self.escalation_stats["resolved_escalations"] += 1
        
        self.logger.info(
            "Эскалация разрешена",
            escalation_id=escalation_id,
            escalation_type=escalation.escalation_type.value,
            resolution=resolution
        )
        
        return True
    
    def get_escalation_status(self, escalation_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса эскалации"""
        if escalation_id not in self.escalation_requests:
            return None
        
        escalation = self.escalation_requests[escalation_id]
        return escalation.to_dict()
    
    def get_active_escalations(self) -> List[Dict[str, Any]]:
        """Получение активных эскалаций"""
        active_statuses = [EscalationStatus.PENDING, EscalationStatus.IN_PROGRESS]
        return [
            escalation.to_dict()
            for escalation in self.escalation_requests.values()
            if escalation.status in active_statuses
        ]
    
    def get_escalation_stats(self) -> Dict[str, Any]:
        """Получение статистики эскалаций"""
        return {
            **self.escalation_stats,
            "active_escalations": len(self.get_active_escalations()),
            "total_escalation_requests": len(self.escalation_requests),
            "total_revision_requests": len(self.plan_revision_requests),
            "escalation_config": self.escalation_config
        }
    
    def cleanup_old_escalations(self, days: int = 7):
        """Очистка старых эскалаций"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # Очищаем старые эскалации
        old_escalations = [
            escalation_id for escalation_id, escalation in self.escalation_requests.items()
            if escalation.timestamp < cutoff_time and escalation.status == EscalationStatus.RESOLVED
        ]
        
        for escalation_id in old_escalations:
            del self.escalation_requests[escalation_id]
        
        # Очищаем старые запросы на пересмотр
        old_revisions = [
            revision_id for revision_id, revision in self.plan_revision_requests.items()
            if revision.timestamp < cutoff_time and revision.status == EscalationStatus.RESOLVED
        ]
        
        for revision_id in old_revisions:
            del self.plan_revision_requests[revision_id]
        
        self.logger.info(
            "Старые эскалации очищены",
            escalations_removed=len(old_escalations),
            revisions_removed=len(old_revisions)
        )
