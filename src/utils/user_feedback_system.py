"""
Главная система обратной связи с пользователем

Этот модуль интегрирует все компоненты обратной связи:
- Система уведомлений
- Генератор детальных отчетов
- Трекер временной шкалы
- Управление конфигурацией
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .notification_system import NotificationSystem, NotificationType, NotificationPriority
from .report_generator import ReportGenerator, ReportType, DetailedReport
from .timeline_tracker import TimelineTracker, TimelineEventType
from .logger import StructuredLogger
from ..models.planning_model import Task, TaskStep


@dataclass
class FeedbackConfig:
    """Конфигурация системы обратной связи"""
    
    notifications: Dict[str, Any]
    reports: Dict[str, Any]
    timeline: Dict[str, Any]
    enabled: bool = True
    log_level: str = "INFO"


class UserFeedbackSystem:
    """
    Главная система обратной связи с пользователем
    
    Интегрирует все компоненты:
    - Уведомления пользователю
    - Детальные отчеты
    - Временная шкала выполнения
    """
    
    def __init__(self, config: FeedbackConfig):
        """
        Инициализация системы обратной связи
        
        Args:
            config: Конфигурация системы
        """
        self.config = config
        self.logger = StructuredLogger("UserFeedbackSystem")
        
        # Инициализируем компоненты
        self.notification_system = NotificationSystem(config.notifications)
        self.report_generator = ReportGenerator(config.reports)
        self.timeline_tracker = TimelineTracker(config.timeline)
        
        self.logger.info(
            "Система обратной связи инициализирована",
            notifications_enabled=config.notifications.get("enabled", True),
            reports_enabled=config.reports.get("enabled", True),
            timeline_enabled=config.timeline.get("enabled", True)
        )
    
    def on_task_started(self, task: Task) -> None:
        """Обработка начала задачи"""
        if not self.config.enabled:
            return
        
        # Уведомление о начале задачи
        self.notification_system.send_task_started(
            task_id=task.task_id,
            task_title=task.title,
            task_description=task.description,
            total_steps=len(task.steps),
            priority=task.priority.value
        )
        
        # Начало отслеживания временной шкалы
        self.timeline_tracker.start_task(task)
        
        self.logger.info("Обратная связь: задача начата", task_id=task.task_id)
    
    def on_task_progress(self, task: Task, completed_steps: int, current_step: Optional[TaskStep]) -> None:
        """Обработка прогресса задачи"""
        if not self.config.enabled:
            return
        
        # Уведомление о прогрессе
        current_step_title = current_step.title if current_step else "Неизвестно"
        elapsed_time = self._calculate_elapsed_time(task)
        
        self.notification_system.send_task_progress(
            task_id=task.task_id,
            task_title=task.title,
            completed_steps=completed_steps,
            total_steps=len(task.steps),
            current_step_title=current_step_title,
            elapsed_time=elapsed_time
        )
        
        self.logger.info(
            "Обратная связь: прогресс задачи",
            task_id=task.task_id,
            progress=f"{completed_steps}/{len(task.steps)}"
        )
    
    def on_task_completed(self, task: Task, execution_results: Dict[str, Any]) -> None:
        """Обработка завершения задачи"""
        if not self.config.enabled:
            return
        
        # Уведомление о завершении
        total_duration = self._format_duration(task.get_duration())
        completed_steps = len([s for s in task.steps if s.status.value == "completed"])
        error_count = sum(s.error_count for s in task.steps)
        
        self.notification_system.send_task_completed(
            task_id=task.task_id,
            task_title=task.title,
            total_duration=total_duration,
            completed_steps=completed_steps,
            total_steps=len(task.steps),
            error_count=error_count
        )
        
        # Завершение отслеживания временной шкалы
        self.timeline_tracker.complete_task(task, success=True)
        
        # Генерация детального отчета
        if self.config.reports.get("enabled", True):
            report = self.report_generator.generate_task_summary_report(task, execution_results)
            self._export_report(report)
        
        self.logger.info("Обратная связь: задача завершена", task_id=task.task_id)
    
    def on_task_failed(self, task: Task, failure_reason: str, execution_results: Dict[str, Any]) -> None:
        """Обработка провала задачи"""
        if not self.config.enabled:
            return
        
        # Уведомление о провале
        completed_steps = len([s for s in task.steps if s.status.value == "completed"])
        error_count = sum(s.error_count for s in task.steps)
        
        self.notification_system.send_task_failed(
            task_id=task.task_id,
            task_title=task.title,
            failure_reason=failure_reason,
            completed_steps=completed_steps,
            total_steps=len(task.steps),
            error_count=error_count
        )
        
        # Завершение отслеживания временной шкалы
        self.timeline_tracker.complete_task(task, success=False)
        
        # Генерация детального отчета
        if self.config.reports.get("enabled", True):
            report = self.report_generator.generate_task_summary_report(task, execution_results)
            self._export_report(report)
        
        self.logger.error("Обратная связь: задача провалена", task_id=task.task_id, reason=failure_reason)
    
    def on_step_started(self, task: Task, step: TaskStep) -> None:
        """Обработка начала шага"""
        if not self.config.enabled:
            return
        
        # Уведомление о начале шага
        self.notification_system.send_step_started(
            task_id=task.task_id,
            task_title=task.title,
            step_id=step.step_id,
            step_title=step.title,
            step_description=step.description
        )
        
        # Начало отслеживания шага
        self.timeline_tracker.start_step(task, step)
        
        self.logger.info("Обратная связь: шаг начат", task_id=task.task_id, step_id=step.step_id)
    
    def on_step_completed(self, task: Task, step: TaskStep, duration: float) -> None:
        """Обработка завершения шага"""
        if not self.config.enabled:
            return
        
        # Уведомление о завершении шага
        duration_str = self._format_duration(duration)
        
        self.notification_system.send_step_completed(
            task_id=task.task_id,
            task_title=task.title,
            step_id=step.step_id,
            step_title=step.title,
            duration=duration_str
        )
        
        # Завершение отслеживания шага
        self.timeline_tracker.complete_step(task, step, success=True)
        
        self.logger.info("Обратная связь: шаг завершен", task_id=task.task_id, step_id=step.step_id)
    
    def on_step_failed(self, task: Task, step: TaskStep, error_message: str, retry_count: int, 
                      autocorrection_applied: bool) -> None:
        """Обработка провала шага"""
        if not self.config.enabled:
            return
        
        # Уведомление о провале шага
        self.notification_system.send_step_failed(
            task_id=task.task_id,
            task_title=task.title,
            step_id=step.step_id,
            step_title=step.title,
            error_message=error_message,
            retry_count=retry_count,
            autocorrection_applied=autocorrection_applied
        )
        
        # Завершение отслеживания шага
        self.timeline_tracker.complete_step(task, step, success=False)
        
        self.logger.warning("Обратная связь: шаг провален", task_id=task.task_id, step_id=step.step_id)
    
    def on_command_executed(self, task_id: str, step_id: str, command: str, success: bool, 
                           duration: float, output: str = "", error: str = "", exit_code: int = 0) -> None:
        """Обработка выполнения команды"""
        if not self.config.enabled:
            return
        
        # Логирование в временную шкалу
        self.timeline_tracker.log_command_execution(
            task_id=task_id,
            step_id=step_id,
            command=command,
            success=success,
            duration=duration,
            output=output,
            error=error,
            exit_code=exit_code
        )
    
    def on_command_retry(self, task_id: str, step_id: str, command: str, retry_count: int, reason: str) -> None:
        """Обработка повторной попытки команды"""
        if not self.config.enabled:
            return
        
        # Логирование в временную шкалу
        self.timeline_tracker.log_command_retry(
            task_id=task_id,
            step_id=step_id,
            command=command,
            retry_count=retry_count,
            reason=reason
        )
    
    def on_autocorrection_applied(self, task_id: str, step_id: str, original_command: str, 
                                 corrected_command: str, correction_type: str, success: bool) -> None:
        """Обработка применения автокоррекции"""
        if not self.config.enabled:
            return
        
        # Уведомление об автокоррекции
        self.notification_system.send_autocorrection(
            task_id=task_id,
            task_title="",  # Можно получить из контекста
            step_id=step_id,
            step_title="",  # Можно получить из контекста
            original_command=original_command,
            corrected_command=corrected_command,
            correction_type=correction_type,
            correction_result="Успешно" if success else "Провалено"
        )
        
        # Логирование в временную шкалу
        self.timeline_tracker.log_autocorrection(
            task_id=task_id,
            step_id=step_id,
            original_command=original_command,
            corrected_command=corrected_command,
            correction_type=correction_type,
            success=success
        )
    
    def on_error_escalation(self, task_id: str, step_id: str, error_count: int, 
                           error_threshold: int, escalation_reason: str) -> None:
        """Обработка эскалации ошибок"""
        if not self.config.enabled:
            return
        
        # Уведомление об эскалации
        self.notification_system.send_error_escalation(
            task_id=task_id,
            task_title="",  # Можно получить из контекста
            step_id=step_id,
            step_title="",  # Можно получить из контекста
            error_count=error_count,
            error_threshold=error_threshold,
            escalation_reason=escalation_reason
        )
        
        # Логирование в временную шкалу
        self.timeline_tracker.log_error_escalation(
            task_id=task_id,
            step_id=step_id,
            error_count=error_count,
            threshold=error_threshold,
            reason=escalation_reason
        )
    
    def on_human_escalation(self, task_id: str, step_id: str, reason: str, 
                           error_details: Dict[str, Any]) -> None:
        """Обработка эскалации к человеку"""
        if not self.config.enabled:
            return
        
        # Уведомление об эскалации к человеку
        recent_errors = error_details.get("recent_errors", [])
        
        self.notification_system.send_human_escalation(
            task_id=task_id,
            task_title="",  # Можно получить из контекста
            step_id=step_id,
            step_title="",  # Можно получить из контекста
            error_count=error_details.get("error_count", 0),
            escalation_reason=reason,
            recent_errors=recent_errors
        )
        
        # Логирование в временную шкалу
        self.timeline_tracker.log_human_escalation(
            task_id=task_id,
            step_id=step_id,
            reason=reason,
            error_details=error_details
        )
    
    def generate_task_report(self, task: Task, execution_results: Dict[str, Any]) -> DetailedReport:
        """Генерация отчета по задаче"""
        return self.report_generator.generate_task_summary_report(task, execution_results)
    
    def generate_step_report(self, task: Task, step_id: str, step_results: List[Dict[str, Any]]) -> DetailedReport:
        """Генерация отчета по шагу"""
        return self.report_generator.generate_step_details_report(task, step_id, step_results)
    
    def get_task_timeline(self, task_id: str) -> List[Dict[str, Any]]:
        """Получение временной шкалы задачи"""
        timeline_events = self.timeline_tracker.get_task_timeline(task_id)
        return [event.to_dict() for event in timeline_events]
    
    def export_task_timeline(self, task_id: str, format_type: str = "json") -> str:
        """Экспорт временной шкалы задачи"""
        return self.timeline_tracker.export_timeline(task_id, format_type)
    
    def get_notification_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получение истории уведомлений"""
        return self.notification_system.get_notification_history(hours)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Получение статуса системы обратной связи"""
        return {
            "enabled": self.config.enabled,
            "notifications": self.notification_system.get_stats(),
            "reports": {
                "total_reports": len(self.report_generator.get_all_reports()),
                "export_config": self.report_generator.export_config
            },
            "timeline": {
                "total_events": len(self.timeline_tracker.events),
                "total_segments": len(self.timeline_tracker.segments)
            }
        }
    
    def cleanup_old_data(self, days: int = 30):
        """Очистка старых данных"""
        self.notification_system.cleanup_old_notifications(days)
        self.report_generator.cleanup_old_reports(days)
        self.timeline_tracker.cleanup_old_events(days)
        
        self.logger.info("Старые данные системы обратной связи очищены", retention_days=days)
    
    def _calculate_elapsed_time(self, task: Task) -> str:
        """Вычисление прошедшего времени"""
        if not task.started_at:
            return "0 мин"
        
        elapsed = datetime.now() - task.started_at
        total_minutes = int(elapsed.total_seconds() / 60)
        
        if total_minutes < 60:
            return f"{total_minutes} мин"
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}ч {minutes}мин"
    
    def _format_duration(self, duration: Optional[float]) -> str:
        """Форматирование длительности"""
        if duration is None:
            return "Не завершено"
        
        if duration < 60:
            return f"{duration:.1f} сек"
        else:
            minutes = int(duration / 60)
            seconds = int(duration % 60)
            return f"{minutes}м {seconds}с"
    
    def _export_report(self, report: DetailedReport):
        """Экспорт отчета"""
        try:
            exported_files = self.report_generator.export_report(report)
            self.logger.info(
                "Отчет экспортирован",
                report_id=report.report_id,
                files=exported_files
            )
        except Exception as e:
            self.logger.error(
                "Ошибка экспорта отчета",
                error=str(e),
                report_id=report.report_id
            )
