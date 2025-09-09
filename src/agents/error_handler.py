"""
Error Handler - Система обработки ошибок и обратной связи

Этот модуль отвечает за:
- Агрегацию ошибок от всех компонентов системы
- Формирование отчетов для планировщика
- Сбор снимков состояния сервера
- Анализ паттернов ошибок
- Генерацию рекомендаций по исправлению
"""
import time
import json
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from ..config.agent_config import ErrorHandlerConfig, AgentConfig
from ..connectors.ssh_connector import SSHConnector
from ..utils.error_tracker import ErrorTracker, ErrorRecord, AttemptRecord, StepErrorStats, EscalationLevel
from ..utils.logger import StructuredLogger
from ..models.planning_model import Task, TaskStep, StepStatus
from ..models.command_result import CommandResult, ExecutionStatus


class ErrorReportType(Enum):
    """Тип отчета об ошибках"""
    STEP_SUMMARY = "step_summary"
    TASK_SUMMARY = "task_summary"
    SYSTEM_HEALTH = "system_health"
    ESCALATION_REPORT = "escalation_report"
    PATTERN_ANALYSIS = "pattern_analysis"


class ServerSnapshotType(Enum):
    """Тип снимка состояния сервера"""
    SYSTEM_INFO = "system_info"
    PROCESS_LIST = "process_list"
    DISK_USAGE = "disk_usage"
    MEMORY_USAGE = "memory_usage"
    NETWORK_STATUS = "network_status"
    SERVICE_STATUS = "service_status"
    LOG_ANALYSIS = "log_analysis"


@dataclass
class ServerSnapshot:
    """Снимок состояния сервера"""
    
    snapshot_id: str
    snapshot_type: ServerSnapshotType
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_type": self.snapshot_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata
        }


@dataclass
class ErrorReport:
    """Отчет об ошибках"""
    
    report_id: str
    report_type: ErrorReportType
    timestamp: datetime
    title: str
    summary: str
    details: Dict[str, Any]
    recommendations: List[str] = field(default_factory=list)
    server_snapshots: List[ServerSnapshot] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "timestamp": self.timestamp.isoformat(),
            "title": self.title,
            "summary": self.summary,
            "details": self.details,
            "recommendations": self.recommendations,
            "server_snapshots": [snapshot.to_dict() for snapshot in self.server_snapshots],
            "metadata": self.metadata
        }


@dataclass
class ErrorPattern:
    """Паттерн ошибок"""
    
    pattern_id: str
    pattern_name: str
    description: str
    frequency: int
    affected_steps: List[str]
    common_commands: List[str]
    common_error_messages: List[str]
    suggested_solutions: List[str]
    severity: str
    first_seen: datetime
    last_seen: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "description": self.description,
            "frequency": self.frequency,
            "affected_steps": self.affected_steps,
            "common_commands": self.common_commands,
            "common_error_messages": self.common_error_messages,
            "suggested_solutions": self.suggested_solutions,
            "severity": self.severity,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat()
        }


class ErrorHandler:
    """
    Обработчик ошибок и система обратной связи
    
    Основные возможности:
    - Агрегация ошибок от всех компонентов
    - Формирование отчетов для планировщика
    - Сбор снимков состояния сервера
    - Анализ паттернов ошибок
    - Генерация рекомендаций
    - Эскалация критических ошибок
    """
    
    def __init__(self, config: AgentConfig, ssh_connector: Optional[SSHConnector] = None):
        """
        Инициализация Error Handler
        
        Args:
            config: Конфигурация агентов
            ssh_connector: SSH коннектор для сбора снимков сервера
        """
        self.config = config
        self.error_handler_config = config.error_handler
        self.ssh_connector = ssh_connector
        self.logger = StructuredLogger("ErrorHandler")
        
        # Инициализация системы подсчета ошибок
        self.error_tracker = ErrorTracker(
            error_threshold=self.error_handler_config.error_threshold_per_step,
            escalation_threshold=self.error_handler_config.human_escalation_threshold,
            max_retention_days=self.error_handler_config.max_retention_days
        )
        
        # Хранилище отчетов и снимков
        self.error_reports: Dict[str, ErrorReport] = {}
        self.server_snapshots: Dict[str, ServerSnapshot] = {}
        self.error_patterns: Dict[str, ErrorPattern] = {}
        
        # Колбэки для уведомлений
        self.planner_callbacks: List[Callable[[ErrorReport], None]] = []
        self.human_escalation_callbacks: List[Callable[[ErrorReport], None]] = []
        
        # Система эскалации (будет установлена отдельно)
        self.escalation_system = None
        
        # Статистика
        self.handler_stats = {
            "reports_generated": 0,
            "snapshots_taken": 0,
            "patterns_identified": 0,
            "escalations_sent": 0,
            "recommendations_generated": 0
        }
        
        self.logger.info(
            "Error Handler инициализирован",
            error_threshold=self.error_handler_config.error_threshold_per_step,
            human_escalation_threshold=self.error_handler_config.human_escalation_threshold,
            ssh_connector_available=ssh_connector is not None
        )
    
    def register_planner_callback(self, callback: Callable[[ErrorReport], None]):
        """Регистрация колбэка для уведомления планировщика"""
        self.planner_callbacks.append(callback)
        self.logger.info("Колбэк планировщика зарегистрирован")
    
    def register_human_escalation_callback(self, callback: Callable[[ErrorReport], None]):
        """Регистрация колбэка для эскалации к человеку"""
        self.human_escalation_callbacks.append(callback)
        self.logger.info("Колбэк эскалации к человеку зарегистрирован")
    
    def set_escalation_system(self, escalation_system):
        """Установка системы эскалации"""
        self.escalation_system = escalation_system
        self.logger.info("Система эскалации установлена")
    
    def handle_step_error(self, step_id: str, task: Task, error_details: Dict[str, Any]) -> Optional[ErrorReport]:
        """
        Обработка ошибки шага
        
        Args:
            step_id: ID шага с ошибкой
            task: Задача, содержащая шаг
            error_details: Детали ошибки
            
        Returns:
            Отчет об ошибке если требуется эскалация
        """
        self.logger.info("Обработка ошибки шага", step_id=step_id, task_id=task.task_id)
        
        # Получаем статистику ошибок для шага
        step_stats = self.error_tracker.get_step_stats(step_id)
        if not step_stats:
            self.logger.warning("Статистика ошибок для шага не найдена", step_id=step_id)
            return None
        
        # Проверяем необходимость эскалации
        escalation_level = self.error_tracker.get_escalation_level(step_id)
        
        # Если система эскалации доступна, используем её
        if self.escalation_system:
            escalation_request = self.escalation_system.handle_escalation(
                step_id, task, step_stats.error_count, error_details
            )
            if escalation_request:
                # Создаем отчет на основе эскалации
                if escalation_level == EscalationLevel.PLANNER_NOTIFICATION:
                    return self._generate_planner_report(step_id, task, step_stats, error_details)
                elif escalation_level == EscalationLevel.HUMAN_ESCALATION:
                    return self._generate_human_escalation_report(step_id, task, step_stats, error_details)
        else:
            # Старая логика эскалации
            if escalation_level == EscalationLevel.PLANNER_NOTIFICATION:
                return self._generate_planner_report(step_id, task, step_stats, error_details)
            elif escalation_level == EscalationLevel.HUMAN_ESCALATION:
                return self._generate_human_escalation_report(step_id, task, step_stats, error_details)
        
        return None
    
    async def handle_task_completion(self, task: Task, execution_results: Dict[str, Any]) -> ErrorReport:
        """
        Обработка завершения задачи
        
        Args:
            task: Завершенная задача
            execution_results: Результаты выполнения
            
        Returns:
            Итоговый отчет по задаче
        """
        self.logger.info("Обработка завершения задачи", task_id=task.task_id)
        
        # Собираем статистику по всем шагам задачи
        task_error_summary = self._collect_task_error_summary(task)
        
        # Анализируем паттерны ошибок
        patterns = self._analyze_error_patterns(task)
        
        # Создаем итоговый отчет
        report = await self._generate_task_summary_report(task, task_error_summary, patterns, execution_results)
        
        # Сохраняем отчет
        self.error_reports[report.report_id] = report
        self.handler_stats["reports_generated"] += 1
        
        self.logger.info(
            "Отчет по задаче создан",
            task_id=task.task_id,
            report_id=report.report_id,
            total_errors=task_error_summary["total_errors"],
            patterns_found=len(patterns)
        )
        
        return report
    
    async def take_server_snapshot(self, snapshot_type: ServerSnapshotType, 
                           context: Optional[Dict[str, Any]] = None) -> ServerSnapshot:
        """
        Создание снимка состояния сервера
        
        Args:
            snapshot_type: Тип снимка
            context: Контекст для снимка
            
        Returns:
            Снимок состояния сервера
        """
        snapshot_id = f"snapshot_{snapshot_type.value}_{int(time.time() * 1000)}"
        
        self.logger.info("Создание снимка сервера", snapshot_type=snapshot_type.value, snapshot_id=snapshot_id)
        
        try:
            if not self.ssh_connector:
                # Создаем пустой снимок если SSH недоступен
                data = {"error": "SSH коннектор недоступен"}
            else:
                data = await self._collect_server_data(snapshot_type, context)
            
            snapshot = ServerSnapshot(
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type,
                timestamp=datetime.now(),
                data=data,
                metadata={
                    "context": context or {},
                    "collection_duration": 0.0  # Будет обновлено
                }
            )
            
            # Сохраняем снимок
            self.server_snapshots[snapshot_id] = snapshot
            self.handler_stats["snapshots_taken"] += 1
            
            self.logger.info("Снимок сервера создан", snapshot_id=snapshot_id, data_size=len(str(data)))
            
            return snapshot
            
        except Exception as e:
            error_msg = f"Ошибка создания снимка сервера: {str(e)}"
            self.logger.error("Ошибка создания снимка", error=error_msg, snapshot_type=snapshot_type.value)
            
            # Создаем снимок с ошибкой
            return ServerSnapshot(
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type,
                timestamp=datetime.now(),
                data={"error": error_msg},
                metadata={"error": True, "context": context or {}}
            )
    
    def analyze_error_patterns(self, time_window_hours: int = 24) -> List[ErrorPattern]:
        """
        Анализ паттернов ошибок за указанный период
        
        Args:
            time_window_hours: Временное окно для анализа в часах
            
        Returns:
            Список выявленных паттернов
        """
        self.logger.info("Анализ паттернов ошибок", time_window_hours=time_window_hours)
        
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        patterns = []
        
        # Группируем ошибки по типам
        error_groups = {}
        
        for step_id, error_records in self.error_tracker.error_records.items():
            recent_errors = [e for e in error_records if e.timestamp >= cutoff_time]
            
            for error in recent_errors:
                pattern_key = self._extract_pattern_key(error)
                if pattern_key not in error_groups:
                    error_groups[pattern_key] = []
                error_groups[pattern_key].append((step_id, error))
        
        # Создаем паттерны для групп с достаточным количеством ошибок
        for pattern_key, error_group in error_groups.items():
            if len(error_group) >= 2:  # Минимум 2 ошибки для паттерна
                pattern = self._create_error_pattern(pattern_key, error_group)
                if pattern:
                    patterns.append(pattern)
                    self.error_patterns[pattern.pattern_id] = pattern
        
        self.handler_stats["patterns_identified"] += len(patterns)
        
        self.logger.info(
            "Анализ паттернов завершен",
            patterns_found=len(patterns),
            error_groups_analyzed=len(error_groups)
        )
        
        return patterns
    
    def generate_recommendations(self, step_id: str, error_history: List[ErrorRecord]) -> List[str]:
        """
        Генерация рекомендаций по исправлению ошибок
        
        Args:
            step_id: ID шага
            error_history: История ошибок
            
        Returns:
            Список рекомендаций
        """
        recommendations = []
        
        # Анализируем типы ошибок
        error_types = {}
        for error in error_history:
            error_type = self._classify_error_type(error.error_message)
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Генерируем рекомендации на основе типов ошибок
        for error_type, count in error_types.items():
            if error_type == "permission_denied":
                recommendations.extend([
                    "Проверить права доступа к файлам и директориям",
                    "Убедиться что пользователь имеет необходимые привилегии",
                    "Рассмотреть использование sudo для команд, требующих повышенных прав"
                ])
            elif error_type == "command_not_found":
                recommendations.extend([
                    "Проверить установку необходимых пакетов",
                    "Обновить PATH переменную окружения",
                    "Установить отсутствующие зависимости"
                ])
            elif error_type == "connection_error":
                recommendations.extend([
                    "Проверить сетевое соединение",
                    "Убедиться что удаленные сервисы доступны",
                    "Проверить настройки файрвола"
                ])
            elif error_type == "syntax_error":
                recommendations.extend([
                    "Проверить синтаксис команд",
                    "Убедиться в корректности параметров",
                    "Проверить версию используемых инструментов"
                ])
            elif error_type == "file_not_found":
                recommendations.extend([
                    "Проверить существование файлов и директорий",
                    "Убедиться в корректности путей",
                    "Создать отсутствующие файлы или директории"
                ])
        
        # Добавляем общие рекомендации
        if len(error_history) > 3:
            recommendations.extend([
                "Рассмотреть разбиение шага на более мелкие подзадачи",
                "Добавить дополнительные проверки перед выполнением команд",
                "Увеличить timeout для команд, которые могут выполняться долго"
            ])
        
        self.handler_stats["recommendations_generated"] += len(recommendations)
        
        return list(set(recommendations))  # Убираем дубликаты
    
    def get_error_summary(self, step_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение сводки по ошибкам
        
        Args:
            step_id: ID шага (если None, то общая сводка)
            
        Returns:
            Сводка по ошибкам
        """
        if step_id:
            return self.error_tracker.get_error_summary(step_id)
        else:
            return self.error_tracker.get_global_stats()
    
    def get_recent_reports(self, hours: int = 24) -> List[ErrorReport]:
        """Получение недавних отчетов"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            report for report in self.error_reports.values()
            if report.timestamp >= cutoff_time
        ]
    
    def cleanup_old_data(self, days: int = 7):
        """Очистка старых данных"""
        self.logger.info("Очистка старых данных", retention_days=days)
        
        # Очищаем старые отчеты
        cutoff_time = datetime.now() - timedelta(days=days)
        old_reports = [
            report_id for report_id, report in self.error_reports.items()
            if report.timestamp < cutoff_time
        ]
        for report_id in old_reports:
            del self.error_reports[report_id]
        
        # Очищаем старые снимки
        old_snapshots = [
            snapshot_id for snapshot_id, snapshot in self.server_snapshots.items()
            if snapshot.timestamp < cutoff_time
        ]
        for snapshot_id in old_snapshots:
            del self.server_snapshots[snapshot_id]
        
        # Очищаем старые паттерны
        old_patterns = [
            pattern_id for pattern_id, pattern in self.error_patterns.items()
            if pattern.last_seen < cutoff_time
        ]
        for pattern_id in old_patterns:
            del self.error_patterns[pattern_id]
        
        # Очищаем данные в error_tracker
        self.error_tracker.cleanup_old_records()
        
        self.logger.info(
            "Очистка завершена",
            reports_removed=len(old_reports),
            snapshots_removed=len(old_snapshots),
            patterns_removed=len(old_patterns)
        )
    
    async def _generate_planner_report(self, step_id: str, task: Task, step_stats: StepErrorStats, 
                                error_details: Dict[str, Any]) -> ErrorReport:
        """Генерация отчета для планировщика"""
        report_id = f"planner_report_{step_id}_{int(time.time() * 1000)}"
        
        # Собираем снимки сервера
        snapshots = [
            await self.take_server_snapshot(ServerSnapshotType.SYSTEM_INFO),
            await self.take_server_snapshot(ServerSnapshotType.SERVICE_STATUS)
        ]
        
        # Генерируем рекомендации
        recent_errors = self.error_tracker.get_recent_errors(step_id, 24)
        recommendations = self.generate_recommendations(step_id, recent_errors)
        
        report = ErrorReport(
            report_id=report_id,
            report_type=ErrorReportType.ESCALATION_REPORT,
            timestamp=datetime.now(),
            title=f"Эскалация к планировщику: {step_id}",
            summary=f"Шаг {step_id} превысил порог ошибок ({step_stats.error_count}/{self.error_handler_config.error_threshold_per_step})",
            details={
                "step_id": step_id,
                "task_id": task.task_id,
                "error_count": step_stats.error_count,
                "attempt_count": step_stats.total_attempts,
                "success_rate": step_stats.success_rate,
                "error_patterns": step_stats.error_patterns,
                "recent_errors": [
                    {
                        "timestamp": error.timestamp.isoformat(),
                        "command": error.command,
                        "error_message": error.error_message[:200],
                        "severity": error.severity.value if hasattr(error.severity, 'value') else error.severity
                    }
                    for error in recent_errors[-5:]  # Последние 5 ошибок
                ],
                "escalation_reason": "error_threshold_exceeded"
            },
            recommendations=recommendations,
            server_snapshots=snapshots,
            metadata={
                "escalation_level": "planner",
                "step_stats": {
                    "error_count": step_stats.error_count,
                    "attempt_count": step_stats.total_attempts,
                    "success_rate": step_stats.success_rate
                }
            }
        )
        
        # Сохраняем отчет
        self.error_reports[report_id] = report
        self.handler_stats["reports_generated"] += 1
        self.handler_stats["escalations_sent"] += 1
        
        # Уведомляем планировщик
        for callback in self.planner_callbacks:
            try:
                callback(report)
            except Exception as e:
                self.logger.error("Ошибка в колбэке планировщика", error=str(e))
        
        self.logger.info(
            "Отчет для планировщика создан и отправлен",
            report_id=report_id,
            step_id=step_id,
            error_count=step_stats.error_count
        )
        
        return report
    
    async def _generate_human_escalation_report(self, step_id: str, task: Task, step_stats: StepErrorStats,
                                        error_details: Dict[str, Any]) -> ErrorReport:
        """Генерация отчета для эскалации к человеку"""
        report_id = f"human_escalation_{step_id}_{int(time.time() * 1000)}"
        
        # Собираем полные снимки сервера
        snapshots = [
            await self.take_server_snapshot(ServerSnapshotType.SYSTEM_INFO),
            await self.take_server_snapshot(ServerSnapshotType.PROCESS_LIST),
            await self.take_server_snapshot(ServerSnapshotType.DISK_USAGE),
            await self.take_server_snapshot(ServerSnapshotType.MEMORY_USAGE),
            await self.take_server_snapshot(ServerSnapshotType.SERVICE_STATUS),
            await self.take_server_snapshot(ServerSnapshotType.LOG_ANALYSIS)
        ]
        
        # Генерируем рекомендации
        recent_errors = self.error_tracker.get_recent_errors(step_id, 24)
        recommendations = self.generate_recommendations(step_id, recent_errors)
        
        report = ErrorReport(
            report_id=report_id,
            report_type=ErrorReportType.ESCALATION_REPORT,
            timestamp=datetime.now(),
            title=f"КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ: {step_id}",
            summary=f"Шаг {step_id} требует вмешательства человека. Ошибок: {step_stats.error_count}",
            details={
                "step_id": step_id,
                "task_id": task.task_id,
                "error_count": step_stats.error_count,
                "attempt_count": step_stats.total_attempts,
                "success_rate": step_stats.success_rate,
                "escalation_level": "human",
                "critical_errors": [
                    {
                        "timestamp": error.timestamp.isoformat(),
                        "command": error.command,
                        "error_message": error.error_message,
                        "severity": error.severity.value if hasattr(error.severity, 'value') else error.severity,
                        "exit_code": error.exit_code
                    }
                    for error in recent_errors if (error.severity.value if hasattr(error.severity, 'value') else error.severity) in ["high", "critical"]
                ],
                "escalation_reason": "human_escalation_threshold_exceeded"
            },
            recommendations=recommendations,
            server_snapshots=snapshots,
            metadata={
                "escalation_level": "human",
                "urgent": True,
                "step_stats": {
                    "error_count": step_stats.error_count,
                    "attempt_count": step_stats.total_attempts,
                    "success_rate": step_stats.success_rate
                }
            }
        )
        
        # Сохраняем отчет
        self.error_reports[report_id] = report
        self.handler_stats["reports_generated"] += 1
        self.handler_stats["escalations_sent"] += 1
        
        # Уведомляем человека-оператора
        for callback in self.human_escalation_callbacks:
            try:
                callback(report)
            except Exception as e:
                self.logger.error("Ошибка в колбэке эскалации к человеку", error=str(e))
        
        self.logger.error(
            "КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ",
            report_id=report_id,
            step_id=step_id,
            error_count=step_stats.error_count,
            success_rate=step_stats.success_rate
        )
        
        return report
    
    async def _generate_task_summary_report(self, task: Task, error_summary: Dict[str, Any],
                                    patterns: List[ErrorPattern], execution_results: Dict[str, Any]) -> ErrorReport:
        """Генерация итогового отчета по задаче"""
        report_id = f"task_summary_{task.task_id}_{int(time.time() * 1000)}"
        
        # Определяем статус задачи
        if task.is_completed():
            status = "completed"
            title = f"Задача завершена: {task.title}"
        elif task.is_failed():
            status = "failed"
            title = f"Задача провалена: {task.title}"
        else:
            status = "incomplete"
            title = f"Задача не завершена: {task.title}"
        
        # Собираем снимки сервера
        snapshots = [
            await self.take_server_snapshot(ServerSnapshotType.SYSTEM_INFO),
            await self.take_server_snapshot(ServerSnapshotType.SERVICE_STATUS)
        ]
        
        # Генерируем рекомендации
        all_recommendations = []
        for pattern in patterns:
            all_recommendations.extend(pattern.suggested_solutions)
        
        report = ErrorReport(
            report_id=report_id,
            report_type=ErrorReportType.TASK_SUMMARY,
            timestamp=datetime.now(),
            title=title,
            summary=f"Задача {task.task_id} завершена со статусом: {status}",
            details={
                "task_id": task.task_id,
                "task_title": task.title,
                "task_status": status,
                "progress": task.get_progress(),
                "error_summary": error_summary,
                "execution_results": execution_results,
                "patterns_found": len(patterns),
                "total_duration": task.get_duration(),
                "steps_summary": [
                    {
                        "step_id": step.step_id,
                        "title": step.title,
                        "status": step.status.value if hasattr(step.status, 'value') else step.status,
                        "error_count": step.error_count,
                        "duration": step.get_duration()
                    }
                    for step in task.steps
                ]
            },
            recommendations=list(set(all_recommendations)),
            server_snapshots=snapshots,
            metadata={
                "task_completion": True,
                "patterns_analyzed": len(patterns),
                "total_steps": len(task.steps)
            }
        )
        
        return report
    
    def _collect_task_error_summary(self, task: Task) -> Dict[str, Any]:
        """Сбор сводки по ошибкам задачи"""
        total_errors = 0
        total_attempts = 0
        failed_steps = []
        step_summaries = []
        
        for step in task.steps:
            step_stats = self.error_tracker.get_step_stats(step.step_id)
            if step_stats:
                total_errors += step_stats.error_count
                total_attempts += step_stats.total_attempts
                
                if step_stats.error_count > 0:
                    failed_steps.append({
                        "step_id": step.step_id,
                        "title": step.title,
                        "error_count": step_stats.error_count,
                        "success_rate": step_stats.success_rate
                    })
                
                step_summaries.append({
                    "step_id": step.step_id,
                    "title": step.title,
                    "error_count": step_stats.error_count,
                    "attempt_count": step_stats.total_attempts,
                    "success_rate": step_stats.success_rate
                })
        
        return {
            "total_errors": total_errors,
            "total_attempts": total_attempts,
            "failed_steps": failed_steps,
            "step_summaries": step_summaries,
            "overall_success_rate": (
                ((total_attempts - total_errors) / total_attempts * 100)
                if total_attempts > 0 else 100.0
            )
        }
    
    def _analyze_error_patterns(self, task: Task) -> List[ErrorPattern]:
        """Анализ паттернов ошибок для задачи"""
        patterns = []
        
        # Группируем ошибки по типам для всех шагов задачи
        error_groups = {}
        
        for step in task.steps:
            step_errors = self.error_tracker.error_records.get(step.step_id, [])
            for error in step_errors:
                pattern_key = self._extract_pattern_key(error)
                if pattern_key not in error_groups:
                    error_groups[pattern_key] = []
                error_groups[pattern_key].append((step.step_id, error))
        
        # Создаем паттерны
        for pattern_key, error_group in error_groups.items():
            if len(error_group) >= 2:
                pattern = self._create_error_pattern(pattern_key, error_group)
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    async def _collect_server_data(self, snapshot_type: ServerSnapshotType, 
                           context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Сбор данных с сервера"""
        data = {}
        
        try:
            if snapshot_type == ServerSnapshotType.SYSTEM_INFO:
                data = {
                    "hostname": await self._execute_command("hostname"),
                    "os_info": await self._execute_command("cat /etc/os-release"),
                    "kernel": await self._execute_command("uname -a"),
                    "uptime": await self._execute_command("uptime"),
                    "load_average": await self._execute_command("cat /proc/loadavg")
                }
            elif snapshot_type == ServerSnapshotType.PROCESS_LIST:
                data = {
                    "top_processes": await self._execute_command("ps aux --sort=-%cpu | head -20"),
                    "running_services": await self._execute_command("systemctl list-units --type=service --state=running"),
                    "failed_services": await self._execute_command("systemctl list-units --type=service --state=failed")
                }
            elif snapshot_type == ServerSnapshotType.DISK_USAGE:
                data = {
                    "disk_usage": await self._execute_command("df -h"),
                    "inode_usage": await self._execute_command("df -i"),
                    "largest_dirs": await self._execute_command("du -h / 2>/dev/null | sort -hr | head -20")
                }
            elif snapshot_type == ServerSnapshotType.MEMORY_USAGE:
                data = {
                    "memory_info": await self._execute_command("free -h"),
                    "memory_details": await self._execute_command("cat /proc/meminfo"),
                    "swap_usage": await self._execute_command("swapon -s")
                }
            elif snapshot_type == ServerSnapshotType.NETWORK_STATUS:
                data = {
                    "network_interfaces": await self._execute_command("ip addr show"),
                    "network_connections": await self._execute_command("ss -tuln"),
                    "routing_table": await self._execute_command("ip route show")
                }
            elif snapshot_type == ServerSnapshotType.SERVICE_STATUS:
                data = {
                    "systemctl_status": await self._execute_command("systemctl status"),
                    "active_services": await self._execute_command("systemctl list-units --type=service --state=active"),
                    "failed_services": await self._execute_command("systemctl list-units --type=service --state=failed")
                }
            elif snapshot_type == ServerSnapshotType.LOG_ANALYSIS:
                data = {
                    "system_logs": await self._execute_command("journalctl --since '1 hour ago' --no-pager | tail -100"),
                    "auth_logs": await self._execute_command("tail -50 /var/log/auth.log 2>/dev/null || echo 'Auth log not accessible'"),
                    "syslog": await self._execute_command("tail -50 /var/log/syslog 2>/dev/null || echo 'Syslog not accessible'")
                }
            
        except Exception as e:
            data = {"error": f"Ошибка сбора данных: {str(e)}"}
        
        return data
    
    async def _execute_command(self, command: str) -> str:
        """Выполнение команды на сервере"""
        if not self.ssh_connector:
            return f"[SSH недоступен] {command}"
        
        try:
            result = await self.ssh_connector.execute_command(command, timeout=30)
            if result.exit_code == 0:
                return result.stdout.strip()
            else:
                return f"[Ошибка {result.exit_code}] {result.stderr.strip()}"
        except Exception as e:
            return f"[Исключение] {str(e)}"
    
    def _extract_pattern_key(self, error: ErrorRecord) -> str:
        """Извлечение ключа паттерна из ошибки"""
        # Группируем по типу ошибки и команде
        error_type = self._classify_error_type(error.error_message)
        command_type = self._classify_command_type(error.command)
        return f"{error_type}_{command_type}"
    
    def _classify_error_type(self, error_message: str) -> str:
        """Классификация типа ошибки"""
        error_lower = error_message.lower()
        
        if any(pattern in error_lower for pattern in ["permission denied", "access denied"]):
            return "permission_denied"
        elif any(pattern in error_lower for pattern in ["command not found", "no such file"]):
            return "command_not_found"
        elif any(pattern in error_lower for pattern in ["connection refused", "timeout", "network"]):
            return "connection_error"
        elif any(pattern in error_lower for pattern in ["syntax error", "invalid option"]):
            return "syntax_error"
        elif any(pattern in error_lower for pattern in ["file not found", "directory not found"]):
            return "file_not_found"
        elif any(pattern in error_lower for pattern in ["package not found", "unable to locate"]):
            return "package_error"
        elif any(pattern in error_lower for pattern in ["service not found", "unit not found"]):
            return "service_error"
        else:
            return "unknown"
    
    def _classify_command_type(self, command: str) -> str:
        """Классификация типа команды"""
        command_lower = command.lower().strip()
        
        if "apt" in command_lower or "install" in command_lower:
            return "package_management"
        elif "systemctl" in command_lower or "service" in command_lower:
            return "service_management"
        elif "docker" in command_lower:
            return "container_management"
        elif "nginx" in command_lower or "apache" in command_lower:
            return "web_server"
        elif "curl" in command_lower or "wget" in command_lower:
            return "network_request"
        elif "mkdir" in command_lower or "touch" in command_lower or "cp" in command_lower:
            return "file_operations"
        else:
            return "other"
    
    def _create_error_pattern(self, pattern_key: str, error_group: List[tuple]) -> Optional[ErrorPattern]:
        """Создание паттерна ошибок"""
        if len(error_group) < 2:
            return None
        
        pattern_id = f"pattern_{pattern_key}_{int(time.time() * 1000)}"
        
        # Анализируем группу ошибок
        affected_steps = list(set(step_id for step_id, _ in error_group))
        commands = [error.command for _, error in error_group]
        error_messages = [error.error_message for _, error in error_group]
        
        # Определяем общие команды и сообщения
        common_commands = list(set(commands))
        common_error_messages = list(set(error_messages))
        
        # Генерируем решения
        suggested_solutions = self._generate_pattern_solutions(pattern_key, error_group)
        
        # Определяем серьезность
        severities = [error.severity.value if hasattr(error.severity, 'value') else error.severity for _, error in error_group]
        severity = "high" if "critical" in severities else ("medium" if "high" in severities else "low")
        
        # Временные метки
        timestamps = [error.timestamp for _, error in error_group]
        first_seen = min(timestamps)
        last_seen = max(timestamps)
        
        pattern = ErrorPattern(
            pattern_id=pattern_id,
            pattern_name=f"Паттерн {pattern_key}",
            description=f"Повторяющийся паттерн ошибок: {pattern_key}",
            frequency=len(error_group),
            affected_steps=affected_steps,
            common_commands=common_commands,
            common_error_messages=common_error_messages,
            suggested_solutions=suggested_solutions,
            severity=severity,
            first_seen=first_seen,
            last_seen=last_seen
        )
        
        return pattern
    
    def _generate_pattern_solutions(self, pattern_key: str, error_group: List[tuple]) -> List[str]:
        """Генерация решений для паттерна"""
        solutions = []
        
        error_type, command_type = pattern_key.split("_", 1)
        
        if error_type == "permission_denied":
            solutions.extend([
                "Проверить права доступа к файлам и директориям",
                "Использовать sudo для команд, требующих повышенных прав",
                "Проверить владельца файлов и директорий"
            ])
        elif error_type == "command_not_found":
            solutions.extend([
                "Установить отсутствующие пакеты",
                "Проверить PATH переменную окружения",
                "Обновить список пакетов"
            ])
        elif error_type == "connection_error":
            solutions.extend([
                "Проверить сетевое соединение",
                "Убедиться что удаленные сервисы доступны",
                "Проверить настройки файрвола"
            ])
        
        if command_type == "package_management":
            solutions.extend([
                "Обновить список пакетов: apt update",
                "Проверить доступность репозиториев",
                "Очистить кэш пакетов: apt clean"
            ])
        elif command_type == "service_management":
            solutions.extend([
                "Проверить статус сервиса: systemctl status",
                "Перезапустить сервис: systemctl restart",
                "Проверить конфигурацию сервиса"
            ])
        
        return list(set(solutions))  # Убираем дубликаты
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Получение статистики обработчика ошибок"""
        return {
            **self.handler_stats,
            "error_tracker_stats": self.error_tracker.get_global_stats(),
            "reports_count": len(self.error_reports),
            "snapshots_count": len(self.server_snapshots),
            "patterns_count": len(self.error_patterns),
            "callbacks_registered": {
                "planner_callbacks": len(self.planner_callbacks),
                "human_escalation_callbacks": len(self.human_escalation_callbacks)
            }
        }
