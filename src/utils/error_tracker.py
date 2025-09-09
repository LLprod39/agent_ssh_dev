"""
Система подсчета ошибок и трекинга попыток

Этот модуль содержит:
- Счетчик ошибок на уровне шага
- Пороговые значения для эскалации
- Систему трекинга попыток
- Анализ паттернов ошибок
- Статистику выполнения
"""
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from ..models.planning_model import TaskStep, StepStatus
from ..models.command_result import CommandResult, ExecutionStatus
from ..utils.logger import StructuredLogger


class ErrorSeverity(Enum):
    """Уровень серьезности ошибки"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EscalationLevel(Enum):
    """Уровень эскалации"""
    NONE = "none"
    RETRY = "retry"
    AUTOCORRECTION = "autocorrection"
    PLANNER_NOTIFICATION = "planner_notification"
    HUMAN_ESCALATION = "human_escalation"


@dataclass
class ErrorRecord:
    """Запись об ошибке"""
    
    error_id: str
    step_id: str
    command: str
    error_message: str
    severity: ErrorSeverity
    timestamp: datetime
    exit_code: Optional[int] = None
    retry_count: int = 0
    autocorrection_applied: bool = False
    escalation_level: EscalationLevel = EscalationLevel.NONE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttemptRecord:
    """Запись о попытке выполнения"""
    
    attempt_id: str
    step_id: str
    command: str
    timestamp: datetime
    success: bool
    duration: float
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    autocorrection_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepErrorStats:
    """Статистика ошибок для шага"""
    
    step_id: str
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    error_count: int = 0
    autocorrection_count: int = 0
    total_duration: float = 0.0
    last_error_timestamp: Optional[datetime] = None
    error_patterns: Dict[str, int] = field(default_factory=dict)
    escalation_history: List[EscalationLevel] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Процент успешных попыток"""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_attempts / self.total_attempts) * 100
    
    @property
    def failure_rate(self) -> float:
        """Процент неудачных попыток"""
        return 100.0 - self.success_rate
    
    @property
    def average_duration(self) -> float:
        """Средняя длительность выполнения"""
        if self.total_attempts == 0:
            return 0.0
        return self.total_duration / self.total_attempts


class ErrorTracker:
    """
    Система подсчета ошибок и трекинга попыток
    
    Основные возможности:
    - Подсчет ошибок на уровне шага
    - Пороговые значения для эскалации
    - Трекинг попыток выполнения
    - Анализ паттернов ошибок
    - Статистика выполнения
    """
    
    def __init__(self, error_threshold: int = 4, escalation_threshold: int = 3, 
                 max_retention_days: int = 7):
        """
        Инициализация Error Tracker
        
        Args:
            error_threshold: Порог ошибок для эскалации к планировщику
            escalation_threshold: Порог для эскалации к человеку
            max_retention_days: Максимальное количество дней хранения записей
        """
        self.error_threshold = error_threshold
        self.escalation_threshold = escalation_threshold
        self.max_retention_days = max_retention_days
        self.logger = StructuredLogger("ErrorTracker")
        
        # Хранилище данных
        self.error_records: Dict[str, List[ErrorRecord]] = {}  # step_id -> List[ErrorRecord]
        self.attempt_records: Dict[str, List[AttemptRecord]] = {}  # step_id -> List[AttemptRecord]
        self.step_stats: Dict[str, StepErrorStats] = {}  # step_id -> StepErrorStats
        
        # Статистика
        self.global_stats = {
            "total_errors": 0,
            "total_attempts": 0,
            "escalations_to_planner": 0,
            "escalations_to_human": 0,
            "autocorrections_applied": 0,
            "autocorrections_successful": 0
        }
        
        self.logger.info(
            "Error Tracker инициализирован",
            error_threshold=error_threshold,
            escalation_threshold=escalation_threshold,
            max_retention_days=max_retention_days
        )
    
    def record_attempt(self, step_id: str, command: str, success: bool, 
                      duration: float, exit_code: Optional[int] = None,
                      error_message: Optional[str] = None, 
                      autocorrection_used: bool = False,
                      metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Запись попытки выполнения
        
        Args:
            step_id: ID шага
            command: Выполненная команда
            success: Успешность выполнения
            duration: Длительность выполнения
            exit_code: Код выхода
            error_message: Сообщение об ошибке
            autocorrection_used: Использовалась ли автокоррекция
            metadata: Дополнительные метаданные
            
        Returns:
            ID записи о попытке
        """
        attempt_id = f"{step_id}_{int(time.time() * 1000)}"
        
        attempt_record = AttemptRecord(
            attempt_id=attempt_id,
            step_id=step_id,
            command=command,
            timestamp=datetime.now(),
            success=success,
            duration=duration,
            exit_code=exit_code,
            error_message=error_message,
            autocorrection_used=autocorrection_used,
            metadata=metadata or {}
        )
        
        # Добавляем запись
        if step_id not in self.attempt_records:
            self.attempt_records[step_id] = []
        self.attempt_records[step_id].append(attempt_record)
        
        # Обновляем статистику шага
        self._update_step_stats(step_id, attempt_record)
        
        # Обновляем глобальную статистику
        self.global_stats["total_attempts"] += 1
        if autocorrection_used:
            self.global_stats["autocorrections_applied"] += 1
            if success:
                self.global_stats["autocorrections_successful"] += 1
        
        # Если попытка неудачная, записываем ошибку
        if not success:
            self.record_error(step_id, command, error_message or "Неизвестная ошибка", 
                            exit_code, autocorrection_used, metadata)
        
        self.logger.debug(
            "Попытка выполнения записана",
            step_id=step_id,
            attempt_id=attempt_id,
            success=success,
            duration=duration,
            autocorrection_used=autocorrection_used
        )
        
        return attempt_id
    
    def record_error(self, step_id: str, command: str, error_message: str,
                    exit_code: Optional[int] = None, autocorrection_applied: bool = False,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Запись ошибки
        
        Args:
            step_id: ID шага
            command: Команда, которая вызвала ошибку
            error_message: Сообщение об ошибке
            exit_code: Код выхода
            autocorrection_applied: Применялась ли автокоррекция
            metadata: Дополнительные метаданные
            
        Returns:
            ID записи об ошибке
        """
        error_id = f"error_{step_id}_{int(time.time() * 1000)}"
        
        # Определяем серьезность ошибки
        severity = self._determine_error_severity(error_message, exit_code)
        
        # Определяем уровень эскалации
        escalation_level = self._determine_escalation_level(step_id)
        
        error_record = ErrorRecord(
            error_id=error_id,
            step_id=step_id,
            command=command,
            error_message=error_message,
            severity=severity,
            timestamp=datetime.now(),
            exit_code=exit_code,
            autocorrection_applied=autocorrection_applied,
            escalation_level=escalation_level,
            metadata=metadata or {}
        )
        
        # Добавляем запись
        if step_id not in self.error_records:
            self.error_records[step_id] = []
        self.error_records[step_id].append(error_record)
        
        # Обновляем статистику шага
        self._update_error_stats(step_id, error_record)
        
        # Обновляем глобальную статистику
        self.global_stats["total_errors"] += 1
        
        # Проверяем необходимость эскалации
        if escalation_level == EscalationLevel.PLANNER_NOTIFICATION:
            self.global_stats["escalations_to_planner"] += 1
        elif escalation_level == EscalationLevel.HUMAN_ESCALATION:
            self.global_stats["escalations_to_human"] += 1
        
        self.logger.warning(
            "Ошибка записана",
            step_id=step_id,
            error_id=error_id,
            severity=severity.value,
            escalation_level=escalation_level.value,
            error_message=error_message[:100]
        )
        
        return error_id
    
    def get_step_error_count(self, step_id: str) -> int:
        """Получить количество ошибок для шага"""
        return len(self.error_records.get(step_id, []))
    
    def get_step_attempt_count(self, step_id: str) -> int:
        """Получить количество попыток для шага"""
        return len(self.attempt_records.get(step_id, []))
    
    def get_step_stats(self, step_id: str) -> Optional[StepErrorStats]:
        """Получить статистику ошибок для шага"""
        return self.step_stats.get(step_id)
    
    def should_escalate_to_planner(self, step_id: str) -> bool:
        """Проверить, нужно ли эскалировать к планировщику"""
        error_count = self.get_step_error_count(step_id)
        return error_count >= self.error_threshold
    
    def should_escalate_to_human(self, step_id: str) -> bool:
        """Проверить, нужно ли эскалировать к человеку"""
        error_count = self.get_step_error_count(step_id)
        return error_count >= self.escalation_threshold
    
    def get_escalation_level(self, step_id: str) -> EscalationLevel:
        """Получить текущий уровень эскалации для шага"""
        error_count = self.get_step_error_count(step_id)
        
        if error_count >= self.escalation_threshold:
            return EscalationLevel.HUMAN_ESCALATION
        elif error_count >= self.error_threshold:
            return EscalationLevel.PLANNER_NOTIFICATION
        elif error_count > 0:
            return EscalationLevel.AUTOCORRECTION
        else:
            return EscalationLevel.NONE
    
    def get_error_patterns(self, step_id: str) -> Dict[str, int]:
        """Получить паттерны ошибок для шага"""
        if step_id not in self.step_stats:
            return {}
        return self.step_stats[step_id].error_patterns.copy()
    
    def get_recent_errors(self, step_id: str, hours: int = 24) -> List[ErrorRecord]:
        """Получить недавние ошибки для шага"""
        if step_id not in self.error_records:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            error for error in self.error_records[step_id]
            if error.timestamp >= cutoff_time
        ]
    
    def get_error_summary(self, step_id: str) -> Dict[str, Any]:
        """Получить сводку ошибок для шага"""
        stats = self.get_step_stats(step_id)
        if not stats:
            return {
                "step_id": step_id,
                "error_count": 0,
                "attempt_count": 0,
                "success_rate": 0.0,
                "escalation_level": EscalationLevel.NONE.value,
                "recent_errors": []
            }
        
        return {
            "step_id": step_id,
            "error_count": stats.error_count,
            "attempt_count": stats.total_attempts,
            "success_rate": stats.success_rate,
            "failure_rate": stats.failure_rate,
            "average_duration": stats.average_duration,
            "escalation_level": self.get_escalation_level(step_id).value,
            "error_patterns": stats.error_patterns,
            "recent_errors": [
                {
                    "error_id": error.error_id,
                    "timestamp": error.timestamp.isoformat(),
                    "severity": error.severity.value,
                    "message": error.error_message[:100]
                }
                for error in self.get_recent_errors(step_id, 24)
            ]
        }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Получить глобальную статистику"""
        total_attempts = self.global_stats["total_attempts"]
        total_errors = self.global_stats["total_errors"]
        
        return {
            **self.global_stats,
            "success_rate": (
                ((total_attempts - total_errors) / total_attempts * 100)
                if total_attempts > 0 else 0.0
            ),
            "autocorrection_success_rate": (
                (self.global_stats["autocorrections_successful"] / 
                 self.global_stats["autocorrections_applied"] * 100)
                if self.global_stats["autocorrections_applied"] > 0 else 0.0
            ),
            "steps_tracked": len(self.step_stats),
            "total_error_records": sum(len(errors) for errors in self.error_records.values()),
            "total_attempt_records": sum(len(attempts) for attempts in self.attempt_records.values())
        }
    
    def cleanup_old_records(self):
        """Очистка старых записей"""
        cutoff_time = datetime.now() - timedelta(days=self.max_retention_days)
        
        # Очищаем записи об ошибках
        for step_id in list(self.error_records.keys()):
            self.error_records[step_id] = [
                error for error in self.error_records[step_id]
                if error.timestamp >= cutoff_time
            ]
            if not self.error_records[step_id]:
                del self.error_records[step_id]
        
        # Очищаем записи о попытках
        for step_id in list(self.attempt_records.keys()):
            self.attempt_records[step_id] = [
                attempt for attempt in self.attempt_records[step_id]
                if attempt.timestamp >= cutoff_time
            ]
            if not self.attempt_records[step_id]:
                del self.attempt_records[step_id]
        
        # Обновляем статистику
        self._recalculate_stats()
        
        self.logger.info("Старые записи очищены", cutoff_time=cutoff_time.isoformat())
    
    def reset_step_stats(self, step_id: str):
        """Сброс статистики для шага"""
        if step_id in self.error_records:
            del self.error_records[step_id]
        if step_id in self.attempt_records:
            del self.attempt_records[step_id]
        if step_id in self.step_stats:
            del self.step_stats[step_id]
        
        self.logger.info("Статистика шага сброшена", step_id=step_id)
    
    def _determine_error_severity(self, error_message: str, exit_code: Optional[int]) -> ErrorSeverity:
        """Определение серьезности ошибки"""
        error_lower = error_message.lower()
        
        # Критические ошибки
        if any(pattern in error_lower for pattern in [
            "permission denied", "access denied", "operation not permitted",
            "disk full", "no space left", "out of memory"
        ]):
            return ErrorSeverity.CRITICAL
        
        # Высокие ошибки
        if any(pattern in error_lower for pattern in [
            "connection refused", "timeout", "service not found",
            "package not found", "command not found"
        ]):
            return ErrorSeverity.HIGH
        
        # Средние ошибки
        if any(pattern in error_lower for pattern in [
            "syntax error", "invalid option", "file not found",
            "directory not found"
        ]):
            return ErrorSeverity.MEDIUM
        
        # Низкие ошибки (все остальные)
        return ErrorSeverity.LOW
    
    def _determine_escalation_level(self, step_id: str) -> EscalationLevel:
        """Определение уровня эскалации"""
        error_count = self.get_step_error_count(step_id)
        
        if error_count >= self.escalation_threshold:
            return EscalationLevel.HUMAN_ESCALATION
        elif error_count >= self.error_threshold:
            return EscalationLevel.PLANNER_NOTIFICATION
        elif error_count > 0:
            return EscalationLevel.AUTOCORRECTION
        else:
            return EscalationLevel.NONE
    
    def _update_step_stats(self, step_id: str, attempt_record: AttemptRecord):
        """Обновление статистики шага на основе попытки"""
        if step_id not in self.step_stats:
            self.step_stats[step_id] = StepErrorStats(step_id=step_id)
        
        stats = self.step_stats[step_id]
        stats.total_attempts += 1
        stats.total_duration += attempt_record.duration
        
        if attempt_record.success:
            stats.successful_attempts += 1
        else:
            stats.failed_attempts += 1
        
        if attempt_record.autocorrection_used:
            stats.autocorrection_count += 1
    
    def _update_error_stats(self, step_id: str, error_record: ErrorRecord):
        """Обновление статистики шага на основе ошибки"""
        if step_id not in self.step_stats:
            self.step_stats[step_id] = StepErrorStats(step_id=step_id)
        
        stats = self.step_stats[step_id]
        stats.error_count += 1
        stats.last_error_timestamp = error_record.timestamp
        
        # Анализируем паттерн ошибки
        error_pattern = self._extract_error_pattern(error_record.error_message)
        if error_pattern:
            stats.error_patterns[error_pattern] = stats.error_patterns.get(error_pattern, 0) + 1
        
        # Добавляем в историю эскалации
        stats.escalation_history.append(error_record.escalation_level)
    
    def _extract_error_pattern(self, error_message: str) -> Optional[str]:
        """Извлечение паттерна ошибки"""
        error_lower = error_message.lower()
        
        patterns = {
            "permission_denied": ["permission denied", "access denied"],
            "command_not_found": ["command not found", "no such file"],
            "connection_error": ["connection refused", "timeout", "network"],
            "syntax_error": ["syntax error", "invalid option"],
            "file_not_found": ["file not found", "directory not found"],
            "package_error": ["package not found", "unable to locate"],
            "service_error": ["service not found", "unit not found"]
        }
        
        for pattern_name, keywords in patterns.items():
            if any(keyword in error_lower for keyword in keywords):
                return pattern_name
        
        return "unknown"
    
    def _recalculate_stats(self):
        """Пересчет статистики после очистки"""
        # Пересчитываем статистику для каждого шага
        for step_id in list(self.step_stats.keys()):
            if step_id not in self.error_records and step_id not in self.attempt_records:
                del self.step_stats[step_id]
                continue
            
            # Пересчитываем статистику шага
            stats = self.step_stats[step_id]
            stats.total_attempts = len(self.attempt_records.get(step_id, []))
            stats.error_count = len(self.error_records.get(step_id, []))
            stats.successful_attempts = len([
                attempt for attempt in self.attempt_records.get(step_id, [])
                if attempt.success
            ])
            stats.failed_attempts = stats.total_attempts - stats.successful_attempts
            stats.autocorrection_count = len([
                attempt for attempt in self.attempt_records.get(step_id, [])
                if attempt.autocorrection_used
            ])
            stats.total_duration = sum(
                attempt.duration for attempt in self.attempt_records.get(step_id, [])
            )
