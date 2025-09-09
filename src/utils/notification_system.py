"""
Система уведомлений для обратной связи с пользователем

Этот модуль отвечает за:
- Отправку уведомлений пользователю о статусе выполнения задач
- Различные каналы уведомлений (email, webhook, консоль, файл)
- Настройку приоритетов и фильтрации уведомлений
- Логирование всех уведомлений
"""
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from pathlib import Path

from ..utils.logger import StructuredLogger


class NotificationChannel(Enum):
    """Канал уведомления"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    FILE = "file"
    LOG = "log"


class NotificationPriority(Enum):
    """Приоритет уведомления"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(Enum):
    """Тип уведомления"""
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    ERROR_ESCALATION = "error_escalation"
    HUMAN_ESCALATION = "human_escalation"
    SYSTEM_STATUS = "system_status"
    AUTOCORRECTION = "autocorrection"


@dataclass
class Notification:
    """Уведомление пользователю"""
    
    notification_id: str
    notification_type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    timestamp: datetime
    channels: List[NotificationChannel]
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    sent: bool = False
    sent_at: Optional[datetime] = None
    delivery_status: Dict[str, str] = field(default_factory=dict)  # channel -> status
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "notification_id": self.notification_id,
            "notification_type": self.notification_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "channels": [channel.value for channel in self.channels],
            "task_id": self.task_id,
            "step_id": self.step_id,
            "metadata": self.metadata,
            "sent": self.sent,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivery_status": self.delivery_status
        }


@dataclass
class NotificationTemplate:
    """Шаблон уведомления"""
    
    template_id: str
    notification_type: NotificationType
    priority: NotificationPriority
    title_template: str
    message_template: str
    channels: List[NotificationChannel]
    enabled: bool = True
    conditions: Dict[str, Any] = field(default_factory=dict)  # Условия для отправки
    
    def render(self, context: Dict[str, Any]) -> tuple:
        """Рендеринг шаблона с контекстом"""
        title = self.title_template.format(**context)
        message = self.message_template.format(**context)
        return title, message


class NotificationSystem:
    """
    Система уведомлений для обратной связи с пользователем
    
    Основные возможности:
    - Отправка уведомлений через различные каналы
    - Настройка шаблонов уведомлений
    - Фильтрация и приоритизация уведомлений
    - Отслеживание доставки уведомлений
    - Логирование всех уведомлений
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация системы уведомлений
        
        Args:
            config: Конфигурация системы уведомлений
        """
        self.config = config
        self.logger = StructuredLogger("NotificationSystem")
        
        # Хранилище уведомлений
        self.notifications: Dict[str, Notification] = {}
        self.templates: Dict[str, NotificationTemplate] = {}
        
        # Настройки каналов
        self.channel_configs = {
            NotificationChannel.EMAIL: config.get("email", {}),
            NotificationChannel.WEBHOOK: config.get("webhook", {}),
            NotificationChannel.CONSOLE: config.get("console", {}),
            NotificationChannel.FILE: config.get("file", {}),
            NotificationChannel.LOG: config.get("log", {})
        }
        
        # Инициализация шаблонов
        self._initialize_templates()
        
        # Статистика
        self.stats = {
            "notifications_sent": 0,
            "notifications_failed": 0,
            "notifications_by_type": {},
            "notifications_by_priority": {},
            "notifications_by_channel": {}
        }
        
        self.logger.info(
            "Система уведомлений инициализирована",
            channels_enabled=[channel.value for channel, config in self.channel_configs.items() if config.get("enabled", False)],
            templates_loaded=len(self.templates)
        )
    
    def _initialize_templates(self):
        """Инициализация шаблонов уведомлений"""
        templates = [
            # Задача началась
            NotificationTemplate(
                template_id="task_started",
                notification_type=NotificationType.TASK_STARTED,
                priority=NotificationPriority.MEDIUM,
                title_template="🚀 Задача начата: {task_title}",
                message_template=(
                    "Задача '{task_title}' начата.\n"
                    "ID задачи: {task_id}\n"
                    "Описание: {task_description}\n"
                    "Количество шагов: {total_steps}\n"
                    "Время начала: {start_time}\n"
                    "Приоритет: {priority}"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG]
            ),
            
            # Прогресс задачи
            NotificationTemplate(
                template_id="task_progress",
                notification_type=NotificationType.TASK_PROGRESS,
                priority=NotificationPriority.LOW,
                title_template="📊 Прогресс задачи: {task_title}",
                message_template=(
                    "Задача '{task_title}' - обновление прогресса.\n"
                    "Выполнено шагов: {completed_steps}/{total_steps}\n"
                    "Прогресс: {progress_percentage:.1f}%\n"
                    "Текущий шаг: {current_step_title}\n"
                    "Время выполнения: {elapsed_time}"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG],
                conditions={"progress_interval": 25}  # Каждые 25%
            ),
            
            # Задача завершена
            NotificationTemplate(
                template_id="task_completed",
                notification_type=NotificationType.TASK_COMPLETED,
                priority=NotificationPriority.HIGH,
                title_template="✅ Задача завершена: {task_title}",
                message_template=(
                    "Задача '{task_title}' успешно завершена!\n"
                    "ID задачи: {task_id}\n"
                    "Общее время выполнения: {total_duration}\n"
                    "Выполнено шагов: {completed_steps}/{total_steps}\n"
                    "Ошибок: {error_count}\n"
                    "Время завершения: {completion_time}"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG, NotificationChannel.EMAIL]
            ),
            
            # Задача провалена
            NotificationTemplate(
                template_id="task_failed",
                notification_type=NotificationType.TASK_FAILED,
                priority=NotificationPriority.CRITICAL,
                title_template="❌ Задача провалена: {task_title}",
                message_template=(
                    "Задача '{task_title}' завершилась с ошибкой!\n"
                    "ID задачи: {task_id}\n"
                    "Причина: {failure_reason}\n"
                    "Выполнено шагов: {completed_steps}/{total_steps}\n"
                    "Ошибок: {error_count}\n"
                    "Время провала: {failure_time}\n"
                    "Требуется вмешательство человека"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG, NotificationChannel.EMAIL, NotificationChannel.WEBHOOK]
            ),
            
            # Шаг начался
            NotificationTemplate(
                template_id="step_started",
                notification_type=NotificationType.STEP_STARTED,
                priority=NotificationPriority.LOW,
                title_template="🔄 Шаг начат: {step_title}",
                message_template=(
                    "Выполняется шаг '{step_title}' задачи '{task_title}'.\n"
                    "ID шага: {step_id}\n"
                    "Описание: {step_description}\n"
                    "Время начала: {start_time}"
                ),
                channels=[NotificationChannel.LOG]
            ),
            
            # Шаг завершен
            NotificationTemplate(
                template_id="step_completed",
                notification_type=NotificationType.STEP_COMPLETED,
                priority=NotificationPriority.LOW,
                title_template="✅ Шаг завершен: {step_title}",
                message_template=(
                    "Шаг '{step_title}' успешно завершен.\n"
                    "ID шага: {step_id}\n"
                    "Время выполнения: {duration}\n"
                    "Время завершения: {completion_time}"
                ),
                channels=[NotificationChannel.LOG]
            ),
            
            # Шаг провален
            NotificationTemplate(
                template_id="step_failed",
                notification_type=NotificationType.STEP_FAILED,
                priority=NotificationPriority.MEDIUM,
                title_template="⚠️ Шаг провален: {step_title}",
                message_template=(
                    "Шаг '{step_title}' завершился с ошибкой.\n"
                    "ID шага: {step_id}\n"
                    "Ошибка: {error_message}\n"
                    "Количество попыток: {retry_count}\n"
                    "Время провала: {failure_time}\n"
                    "Применена автокоррекция: {autocorrection_applied}"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG]
            ),
            
            # Эскалация ошибок
            NotificationTemplate(
                template_id="error_escalation",
                notification_type=NotificationType.ERROR_ESCALATION,
                priority=NotificationPriority.HIGH,
                title_template="🚨 Эскалация ошибок: {step_title}",
                message_template=(
                    "Превышен порог ошибок для шага '{step_title}'.\n"
                    "ID шага: {step_id}\n"
                    "Количество ошибок: {error_count}\n"
                    "Порог: {error_threshold}\n"
                    "Причина эскалации: {escalation_reason}\n"
                    "Время эскалации: {escalation_time}\n"
                    "Отправлено планировщику для пересмотра"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG, NotificationChannel.EMAIL]
            ),
            
            # Эскалация к человеку
            NotificationTemplate(
                template_id="human_escalation",
                notification_type=NotificationType.HUMAN_ESCALATION,
                priority=NotificationPriority.CRITICAL,
                title_template="🚨 КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ: {step_title}",
                message_template=(
                    "ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО ЧЕЛОВЕКА!\n"
                    "Шаг '{step_title}' требует немедленного внимания.\n"
                    "ID шага: {step_id}\n"
                    "ID задачи: {task_id}\n"
                    "Количество ошибок: {error_count}\n"
                    "Причина: {escalation_reason}\n"
                    "Время эскалации: {escalation_time}\n"
                    "Последние ошибки:\n{recent_errors}\n"
                    "Пожалуйста, проверьте систему и примите меры"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG, NotificationChannel.EMAIL, NotificationChannel.WEBHOOK]
            ),
            
            # Автокоррекция
            NotificationTemplate(
                template_id="autocorrection",
                notification_type=NotificationType.AUTOCORRECTION,
                priority=NotificationPriority.LOW,
                title_template="🔧 Автокоррекция применена: {step_title}",
                message_template=(
                    "Применена автокоррекция для шага '{step_title}'.\n"
                    "ID шага: {step_id}\n"
                    "Исходная команда: {original_command}\n"
                    "Исправленная команда: {corrected_command}\n"
                    "Тип коррекции: {correction_type}\n"
                    "Результат: {correction_result}\n"
                    "Время коррекции: {correction_time}"
                ),
                channels=[NotificationChannel.LOG]
            ),
            
            # Статус системы
            NotificationTemplate(
                template_id="system_status",
                notification_type=NotificationType.SYSTEM_STATUS,
                priority=NotificationPriority.MEDIUM,
                title_template="📈 Статус системы",
                message_template=(
                    "Отчет о состоянии системы.\n"
                    "Активных задач: {active_tasks}\n"
                    "Завершенных задач: {completed_tasks}\n"
                    "Проваленных задач: {failed_tasks}\n"
                    "Общее количество ошибок: {total_errors}\n"
                    "Время отчета: {report_time}"
                ),
                channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG]
            )
        ]
        
        for template in templates:
            self.templates[template.template_id] = template
        
        self.logger.info(f"Загружено {len(templates)} шаблонов уведомлений")
    
    def send_notification(self, notification_type: NotificationType, context: Dict[str, Any], 
                         custom_channels: Optional[List[NotificationChannel]] = None) -> Notification:
        """
        Отправка уведомления
        
        Args:
            notification_type: Тип уведомления
            context: Контекст для шаблона
            custom_channels: Кастомные каналы (если не указаны, используются из шаблона)
            
        Returns:
            Созданное уведомление
        """
        # Находим подходящий шаблон
        template = self._find_template(notification_type, context)
        if not template:
            self.logger.warning("Шаблон уведомления не найден", notification_type=notification_type.value)
            return None
        
        # Проверяем условия отправки
        if not self._check_conditions(template, context):
            self.logger.debug("Условия отправки не выполнены", template_id=template.template_id)
            return None
        
        # Рендерим шаблон
        title, message = template.render(context)
        
        # Определяем каналы
        channels = custom_channels or template.channels
        
        # Создаем уведомление
        notification_id = f"notif_{notification_type.value}_{int(time.time() * 1000)}"
        notification = Notification(
            notification_id=notification_id,
            notification_type=notification_type,
            priority=template.priority,
            title=title,
            message=message,
            timestamp=datetime.now(),
            channels=channels,
            task_id=context.get("task_id"),
            step_id=context.get("step_id"),
            metadata=context
        )
        
        # Отправляем уведомление
        self._send_notification(notification)
        
        # Сохраняем уведомление
        self.notifications[notification_id] = notification
        
        # Обновляем статистику
        self._update_stats(notification)
        
        self.logger.info(
            "Уведомление отправлено",
            notification_id=notification_id,
            notification_type=notification_type.value,
            priority=template.priority.value,
            channels=[channel.value for channel in channels]
        )
        
        return notification
    
    def send_task_started(self, task_id: str, task_title: str, task_description: str, 
                         total_steps: int, priority: str = "medium") -> Notification:
        """Отправка уведомления о начале задачи"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "task_description": task_description,
            "total_steps": total_steps,
            "priority": priority,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.TASK_STARTED, context)
    
    def send_task_progress(self, task_id: str, task_title: str, completed_steps: int, 
                          total_steps: int, current_step_title: str, elapsed_time: str) -> Optional[Notification]:
        """Отправка уведомления о прогрессе задачи"""
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        # Проверяем интервал отправки (каждые 25%)
        if progress_percentage % 25 != 0 and completed_steps != total_steps:
            return None
        
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "progress_percentage": progress_percentage,
            "current_step_title": current_step_title,
            "elapsed_time": elapsed_time
        }
        return self.send_notification(NotificationType.TASK_PROGRESS, context)
    
    def send_task_completed(self, task_id: str, task_title: str, total_duration: str, 
                           completed_steps: int, total_steps: int, error_count: int) -> Notification:
        """Отправка уведомления о завершении задачи"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "total_duration": total_duration,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "error_count": error_count,
            "completion_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.TASK_COMPLETED, context)
    
    def send_task_failed(self, task_id: str, task_title: str, failure_reason: str, 
                        completed_steps: int, total_steps: int, error_count: int) -> Notification:
        """Отправка уведомления о провале задачи"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "failure_reason": failure_reason,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "error_count": error_count,
            "failure_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.TASK_FAILED, context)
    
    def send_step_started(self, task_id: str, task_title: str, step_id: str, 
                         step_title: str, step_description: str) -> Notification:
        """Отправка уведомления о начале шага"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "step_id": step_id,
            "step_title": step_title,
            "step_description": step_description,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.STEP_STARTED, context)
    
    def send_step_completed(self, task_id: str, task_title: str, step_id: str, 
                           step_title: str, duration: str) -> Notification:
        """Отправка уведомления о завершении шага"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "step_id": step_id,
            "step_title": step_title,
            "duration": duration,
            "completion_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.STEP_COMPLETED, context)
    
    def send_step_failed(self, task_id: str, task_title: str, step_id: str, 
                        step_title: str, error_message: str, retry_count: int, 
                        autocorrection_applied: bool) -> Notification:
        """Отправка уведомления о провале шага"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "step_id": step_id,
            "step_title": step_title,
            "error_message": error_message,
            "retry_count": retry_count,
            "autocorrection_applied": "Да" if autocorrection_applied else "Нет",
            "failure_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.STEP_FAILED, context)
    
    def send_error_escalation(self, task_id: str, task_title: str, step_id: str, 
                             step_title: str, error_count: int, error_threshold: int, 
                             escalation_reason: str) -> Notification:
        """Отправка уведомления об эскалации ошибок"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "step_id": step_id,
            "step_title": step_title,
            "error_count": error_count,
            "error_threshold": error_threshold,
            "escalation_reason": escalation_reason,
            "escalation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.ERROR_ESCALATION, context)
    
    def send_human_escalation(self, task_id: str, task_title: str, step_id: str, 
                             step_title: str, error_count: int, escalation_reason: str, 
                             recent_errors: List[Dict[str, Any]]) -> Notification:
        """Отправка уведомления об эскалации к человеку"""
        # Форматируем последние ошибки
        errors_text = "\n".join([
            f"- {error.get('command', 'Unknown')}: {error.get('error_message', 'Unknown error')[:100]}"
            for error in recent_errors[:3]
        ])
        
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "step_id": step_id,
            "step_title": step_title,
            "error_count": error_count,
            "escalation_reason": escalation_reason,
            "recent_errors": errors_text,
            "escalation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.HUMAN_ESCALATION, context)
    
    def send_autocorrection(self, task_id: str, task_title: str, step_id: str, 
                           step_title: str, original_command: str, corrected_command: str, 
                           correction_type: str, correction_result: str) -> Notification:
        """Отправка уведомления об автокоррекции"""
        context = {
            "task_id": task_id,
            "task_title": task_title,
            "step_id": step_id,
            "step_title": step_title,
            "original_command": original_command,
            "corrected_command": corrected_command,
            "correction_type": correction_type,
            "correction_result": correction_result,
            "correction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.AUTOCORRECTION, context)
    
    def send_system_status(self, active_tasks: int, completed_tasks: int, 
                          failed_tasks: int, total_errors: int) -> Notification:
        """Отправка уведомления о статусе системы"""
        context = {
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "total_errors": total_errors,
            "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.send_notification(NotificationType.SYSTEM_STATUS, context)
    
    def _find_template(self, notification_type: NotificationType, context: Dict[str, Any]) -> Optional[NotificationTemplate]:
        """Поиск подходящего шаблона"""
        for template in self.templates.values():
            if template.notification_type == notification_type and template.enabled:
                return template
        return None
    
    def _check_conditions(self, template: NotificationTemplate, context: Dict[str, Any]) -> bool:
        """Проверка условий отправки"""
        if not template.conditions:
            return True
        
        # Проверяем интервал прогресса
        if "progress_interval" in template.conditions:
            progress = context.get("progress_percentage", 0)
            interval = template.conditions["progress_interval"]
            if progress % interval != 0:
                return False
        
        return True
    
    def _send_notification(self, notification: Notification):
        """Отправка уведомления по всем каналам"""
        for channel in notification.channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    self._send_email(notification)
                elif channel == NotificationChannel.WEBHOOK:
                    self._send_webhook(notification)
                elif channel == NotificationChannel.CONSOLE:
                    self._send_console(notification)
                elif channel == NotificationChannel.FILE:
                    self._send_file(notification)
                elif channel == NotificationChannel.LOG:
                    self._send_log(notification)
                
                notification.delivery_status[channel.value] = "sent"
                
            except Exception as e:
                self.logger.error(
                    f"Ошибка отправки уведомления через {channel.value}",
                    error=str(e),
                    notification_id=notification.notification_id
                )
                notification.delivery_status[channel.value] = f"failed: {str(e)}"
        
        notification.sent = True
        notification.sent_at = datetime.now()
    
    def _send_email(self, notification: Notification):
        """Отправка email уведомления"""
        config = self.channel_configs[NotificationChannel.EMAIL]
        
        if not config.get("enabled", False):
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = config.get("from_address", "")
            msg['To'] = ", ".join(config.get("to_addresses", []))
            msg['Subject'] = notification.title
            
            body = notification.message
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(config.get("smtp_server", ""), config.get("smtp_port", 587))
            server.starttls()
            server.login(config.get("username", ""), config.get("password", ""))
            server.send_message(msg)
            server.quit()
            
            self.logger.info("Email уведомление отправлено", notification_id=notification.notification_id)
            
        except Exception as e:
            self.logger.error("Ошибка отправки email", error=str(e))
            raise
    
    def _send_webhook(self, notification: Notification):
        """Отправка webhook уведомления"""
        config = self.channel_configs[NotificationChannel.WEBHOOK]
        
        if not config.get("enabled", False):
            return
        
        try:
            import requests
            
            payload = notification.to_dict()
            
            response = requests.post(
                config.get("url", ""),
                json=payload,
                headers=config.get("headers", {}),
                timeout=config.get("timeout", 30)
            )
            
            if response.status_code == 200:
                self.logger.info("Webhook уведомление отправлено", notification_id=notification.notification_id)
            else:
                self.logger.warning(
                    "Webhook уведомление отправлено с ошибкой",
                    notification_id=notification.notification_id,
                    status_code=response.status_code
                )
                
        except Exception as e:
            self.logger.error("Ошибка отправки webhook", error=str(e))
            raise
    
    def _send_console(self, notification: Notification):
        """Отправка консольного уведомления"""
        config = self.channel_configs[NotificationChannel.CONSOLE]
        
        if not config.get("enabled", True):
            return
        
        # Определяем цвет на основе приоритета
        colors = {
            NotificationPriority.LOW: "\033[94m",      # Синий
            NotificationPriority.MEDIUM: "\033[93m",    # Желтый
            NotificationPriority.HIGH: "\033[91m",      # Красный
            NotificationPriority.CRITICAL: "\033[95m"   # Фиолетовый
        }
        reset_color = "\033[0m"
        
        color = colors.get(notification.priority, "")
        
        print(f"\n{color}{'='*80}{reset_color}")
        print(f"{color}{notification.title}{reset_color}")
        print(f"{color}{'='*80}{reset_color}")
        print(notification.message)
        print(f"{color}{'='*80}{reset_color}\n")
    
    def _send_file(self, notification: Notification):
        """Отправка уведомления в файл"""
        config = self.channel_configs[NotificationChannel.FILE]
        
        if not config.get("enabled", False):
            return
        
        file_path = config.get("file_path", "notifications.log")
        
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"Уведомление: {notification.title}\n")
                f.write(f"Время: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Приоритет: {notification.priority.value}\n")
                f.write(f"Тип: {notification.notification_type.value}\n")
                f.write(f"{'='*80}\n")
                f.write(notification.message)
                f.write(f"\n{'='*80}\n")
            
            self.logger.info("Уведомление записано в файл", notification_id=notification.notification_id)
            
        except Exception as e:
            self.logger.error("Ошибка записи в файл", error=str(e))
            raise
    
    def _send_log(self, notification: Notification):
        """Отправка уведомления в лог"""
        config = self.channel_configs[NotificationChannel.LOG]
        
        if not config.get("enabled", True):
            return
        
        # Используем соответствующий уровень логирования
        if notification.priority == NotificationPriority.CRITICAL:
            self.logger.critical(
                f"УВЕДОМЛЕНИЕ: {notification.title}",
                notification_id=notification.notification_id,
                notification_type=notification.notification_type.value,
                priority=notification.priority.value,
                message=notification.message
            )
        elif notification.priority == NotificationPriority.HIGH:
            self.logger.error(
                f"УВЕДОМЛЕНИЕ: {notification.title}",
                notification_id=notification.notification_id,
                notification_type=notification.notification_type.value,
                priority=notification.priority.value,
                message=notification.message
            )
        elif notification.priority == NotificationPriority.MEDIUM:
            self.logger.warning(
                f"УВЕДОМЛЕНИЕ: {notification.title}",
                notification_id=notification.notification_id,
                notification_type=notification.notification_type.value,
                priority=notification.priority.value,
                message=notification.message
            )
        else:
            self.logger.info(
                f"УВЕДОМЛЕНИЕ: {notification.title}",
                notification_id=notification.notification_id,
                notification_type=notification.notification_type.value,
                priority=notification.priority.value,
                message=notification.message
            )
    
    def _update_stats(self, notification: Notification):
        """Обновление статистики"""
        self.stats["notifications_sent"] += 1
        
        # Статистика по типам
        notif_type = notification.notification_type.value
        self.stats["notifications_by_type"][notif_type] = self.stats["notifications_by_type"].get(notif_type, 0) + 1
        
        # Статистика по приоритетам
        priority = notification.priority.value
        self.stats["notifications_by_priority"][priority] = self.stats["notifications_by_priority"].get(priority, 0) + 1
        
        # Статистика по каналам
        for channel in notification.channels:
            channel_name = channel.value
            self.stats["notifications_by_channel"][channel_name] = self.stats["notifications_by_channel"].get(channel_name, 0) + 1
    
    def get_notification_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Получение истории уведомлений"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_notifications = [
            notification.to_dict()
            for notification in self.notifications.values()
            if notification.timestamp >= cutoff_time
        ]
        
        # Сортируем по времени (новые сначала)
        recent_notifications.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return recent_notifications
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики уведомлений"""
        return {
            **self.stats,
            "total_notifications": len(self.notifications),
            "templates_count": len(self.templates),
            "channels_enabled": [
                channel.value for channel, config in self.channel_configs.items() 
                if config.get("enabled", False)
            ]
        }
    
    def cleanup_old_notifications(self, days: int = 7):
        """Очистка старых уведомлений"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        old_notifications = [
            notification_id for notification_id, notification in self.notifications.items()
            if notification.timestamp < cutoff_time
        ]
        
        for notification_id in old_notifications:
            del self.notifications[notification_id]
        
        self.logger.info(
            "Старые уведомления очищены",
            removed_count=len(old_notifications),
            retention_days=days
        )

