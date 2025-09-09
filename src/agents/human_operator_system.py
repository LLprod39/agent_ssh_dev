"""
Система эскалации к человеку-оператору

Этот модуль отвечает за:
- Уведомления человека-оператора о критических ситуациях
- Интерфейс для взаимодействия с оператором
- Систему приоритизации эскалаций
- Логирование действий оператора
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

from ..agents.escalation_system import EscalationRequest, EscalationType, EscalationStatus
from ..utils.logger import StructuredLogger


class NotificationMethod(Enum):
    """Метод уведомления"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"
    CONSOLE = "console"


class OperatorAction(Enum):
    """Действие оператора"""
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"
    ESCALATE = "escalate"
    IGNORE = "ignore"
    REQUEST_INFO = "request_info"


@dataclass
class OperatorNotification:
    """Уведомление оператора"""
    
    notification_id: str
    escalation_id: str
    escalation_type: EscalationType
    priority: str
    title: str
    message: str
    timestamp: datetime
    notification_methods: List[NotificationMethod]
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "notification_id": self.notification_id,
            "escalation_id": self.escalation_id,
            "escalation_type": self.escalation_type.value,
            "priority": self.priority,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "notification_methods": [method.value for method in self.notification_methods],
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
            "metadata": self.metadata
        }


@dataclass
class OperatorAction:
    """Действие оператора"""
    
    action_id: str
    notification_id: str
    action_type: OperatorAction
    operator_id: str
    timestamp: datetime
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "action_id": self.action_id,
            "notification_id": self.notification_id,
            "action_type": self.action_type.value,
            "operator_id": self.operator_id,
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
            "metadata": self.metadata
        }


class HumanOperatorSystem:
    """
    Система эскалации к человеку-оператору
    
    Основные возможности:
    - Уведомления оператора о критических ситуациях
    - Интерфейс для взаимодействия с оператором
    - Система приоритизации эскалаций
    - Логирование действий оператора
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация системы оператора
        
        Args:
            config: Конфигурация системы оператора
        """
        self.config = config
        self.logger = StructuredLogger("HumanOperatorSystem")
        
        # Хранилище уведомлений и действий
        self.notifications: Dict[str, OperatorNotification] = {}
        self.operator_actions: Dict[str, OperatorAction] = {}
        
        # Настройки уведомлений
        self.notification_config = {
            "email": {
                "enabled": config.get("email_notifications", {}).get("enabled", False),
                "smtp_server": config.get("email_notifications", {}).get("smtp_server", ""),
                "smtp_port": config.get("email_notifications", {}).get("smtp_port", 587),
                "username": config.get("email_notifications", {}).get("username", ""),
                "password": config.get("email_notifications", {}).get("password", ""),
                "from_address": config.get("email_notifications", {}).get("from_address", ""),
                "to_addresses": config.get("email_notifications", {}).get("to_addresses", [])
            },
            "webhook": {
                "enabled": config.get("webhook_notifications", {}).get("enabled", False),
                "url": config.get("webhook_notifications", {}).get("url", ""),
                "headers": config.get("webhook_notifications", {}).get("headers", {}),
                "timeout": config.get("webhook_notifications", {}).get("timeout", 30)
            },
            "console": {
                "enabled": config.get("console_notifications", {}).get("enabled", True)
            }
        }
        
        # Статистика
        self.operator_stats = {
            "total_notifications": 0,
            "acknowledged_notifications": 0,
            "resolved_notifications": 0,
            "pending_notifications": 0,
            "operator_actions": 0
        }
        
        self.logger.info(
            "Система оператора инициализирована",
            email_enabled=self.notification_config["email"]["enabled"],
            webhook_enabled=self.notification_config["webhook"]["enabled"],
            console_enabled=self.notification_config["console"]["enabled"]
        )
    
    def handle_escalation(self, escalation_request: EscalationRequest) -> OperatorNotification:
        """
        Обработка эскалации к оператору
        
        Args:
            escalation_request: Запрос на эскалацию
            
        Returns:
            Уведомление оператора
        """
        self.logger.info(
            "Обработка эскалации к оператору",
            escalation_id=escalation_request.escalation_id,
            escalation_type=escalation_request.escalation_type.value
        )
        
        # Определяем приоритет
        priority = self._determine_priority(escalation_request)
        
        # Создаем уведомление
        notification = self._create_notification(escalation_request, priority)
        
        # Отправляем уведомления
        self._send_notifications(notification)
        
        # Сохраняем уведомление
        self.notifications[notification.notification_id] = notification
        self.operator_stats["total_notifications"] += 1
        self.operator_stats["pending_notifications"] += 1
        
        self.logger.info(
            "Уведомление оператора создано",
            notification_id=notification.notification_id,
            priority=priority,
            methods=len(notification.notification_methods)
        )
        
        return notification
    
    def _determine_priority(self, escalation_request: EscalationRequest) -> str:
        """Определение приоритета уведомления"""
        if escalation_request.escalation_type == EscalationType.EMERGENCY_STOP:
            return "critical"
        elif escalation_request.escalation_type == EscalationType.HUMAN_ESCALATION:
            return "high"
        elif escalation_request.escalation_type == EscalationType.PLAN_REVISION:
            return "medium"
        else:
            return "low"
    
    def _create_notification(self, escalation_request: EscalationRequest, priority: str) -> OperatorNotification:
        """Создание уведомления оператора"""
        notification_id = f"notification_{escalation_request.escalation_id}_{int(time.time() * 1000)}"
        
        # Определяем методы уведомления на основе приоритета
        notification_methods = self._get_notification_methods(priority)
        
        # Создаем заголовок и сообщение
        title, message = self._create_notification_content(escalation_request, priority)
        
        notification = OperatorNotification(
            notification_id=notification_id,
            escalation_id=escalation_request.escalation_id,
            escalation_type=escalation_request.escalation_type,
            priority=priority,
            title=title,
            message=message,
            timestamp=datetime.now(),
            notification_methods=notification_methods,
            metadata={
                "step_id": escalation_request.step_id,
                "task_id": escalation_request.task_id,
                "error_count": escalation_request.error_count,
                "threshold_exceeded": escalation_request.threshold_exceeded
            }
        )
        
        return notification
    
    def _get_notification_methods(self, priority: str) -> List[NotificationMethod]:
        """Получение методов уведомления на основе приоритета"""
        methods = []
        
        # Всегда добавляем логирование
        methods.append(NotificationMethod.LOG)
        
        # Для критических и высоких приоритетов добавляем email
        if priority in ["critical", "high"] and self.notification_config["email"]["enabled"]:
            methods.append(NotificationMethod.EMAIL)
        
        # Для критических приоритетов добавляем webhook
        if priority == "critical" and self.notification_config["webhook"]["enabled"]:
            methods.append(NotificationMethod.WEBHOOK)
        
        # Для отладки добавляем консоль
        if self.notification_config["console"]["enabled"]:
            methods.append(NotificationMethod.CONSOLE)
        
        return methods
    
    def _create_notification_content(self, escalation_request: EscalationRequest, priority: str) -> tuple:
        """Создание содержимого уведомления"""
        # Заголовок
        if priority == "critical":
            title = f"🚨 КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ: {escalation_request.context.get('step_title', 'Unknown Step')}"
        elif priority == "high":
            title = f"⚠️ ВЫСОКИЙ ПРИОРИТЕТ: {escalation_request.context.get('step_title', 'Unknown Step')}"
        else:
            title = f"ℹ️ ЭСКАЛАЦИЯ: {escalation_request.context.get('step_title', 'Unknown Step')}"
        
        # Сообщение
        message_parts = [
            f"Тип эскалации: {escalation_request.escalation_type.value}",
            f"Задача: {escalation_request.context.get('task_title', 'Unknown Task')}",
            f"Шаг: {escalation_request.context.get('step_title', 'Unknown Step')}",
            f"Количество ошибок: {escalation_request.error_count}",
            f"Порог превышен: {escalation_request.threshold_exceeded}",
            f"Причина: {escalation_request.reason}",
            f"Время: {escalation_request.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Детали ошибок:",
        ]
        
        # Добавляем детали ошибок
        error_details = escalation_request.error_details
        if "recent_errors" in error_details:
            for i, error in enumerate(error_details["recent_errors"][:3], 1):
                message_parts.append(f"{i}. {error.get('command', 'Unknown command')}: {error.get('error_message', 'Unknown error')[:100]}")
        
        message_parts.extend([
            "",
            "Требуемые действия:",
            "- Проверить состояние системы",
            "- Проанализировать логи ошибок",
            "- Принять решение о дальнейших действиях",
            "",
            f"ID эскалации: {escalation_request.escalation_id}",
            f"ID уведомления: {notification.notification_id}"
        ])
        
        message = "\n".join(message_parts)
        
        return title, message
    
    def _send_notifications(self, notification: OperatorNotification):
        """Отправка уведомлений"""
        for method in notification.notification_methods:
            try:
                if method == NotificationMethod.EMAIL:
                    self._send_email_notification(notification)
                elif method == NotificationMethod.WEBHOOK:
                    self._send_webhook_notification(notification)
                elif method == NotificationMethod.CONSOLE:
                    self._send_console_notification(notification)
                elif method == NotificationMethod.LOG:
                    self._send_log_notification(notification)
            except Exception as e:
                self.logger.error(
                    f"Ошибка отправки уведомления методом {method.value}",
                    error=str(e),
                    notification_id=notification.notification_id
                )
    
    def _send_email_notification(self, notification: OperatorNotification):
        """Отправка email уведомления"""
        email_config = self.notification_config["email"]
        
        if not email_config["enabled"] or not email_config["to_addresses"]:
            return
        
        try:
            # Создаем сообщение
            msg = MIMEMultipart()
            msg['From'] = email_config["from_address"]
            msg['To'] = ", ".join(email_config["to_addresses"])
            msg['Subject'] = notification.title
            
            # Добавляем тело сообщения
            body = notification.message
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Отправляем email
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["username"], email_config["password"])
            server.send_message(msg)
            server.quit()
            
            self.logger.info(
                "Email уведомление отправлено",
                notification_id=notification.notification_id,
                recipients=len(email_config["to_addresses"])
            )
            
        except Exception as e:
            self.logger.error(
                "Ошибка отправки email уведомления",
                error=str(e),
                notification_id=notification.notification_id
            )
    
    def _send_webhook_notification(self, notification: OperatorNotification):
        """Отправка webhook уведомления"""
        webhook_config = self.notification_config["webhook"]
        
        if not webhook_config["enabled"] or not webhook_config["url"]:
            return
        
        try:
            import requests
            
            payload = {
                "notification_id": notification.notification_id,
                "escalation_id": notification.escalation_id,
                "priority": notification.priority,
                "title": notification.title,
                "message": notification.message,
                "timestamp": notification.timestamp.isoformat(),
                "metadata": notification.metadata
            }
            
            response = requests.post(
                webhook_config["url"],
                json=payload,
                headers=webhook_config["headers"],
                timeout=webhook_config["timeout"]
            )
            
            if response.status_code == 200:
                self.logger.info(
                    "Webhook уведомление отправлено",
                    notification_id=notification.notification_id,
                    status_code=response.status_code
                )
            else:
                self.logger.warning(
                    "Webhook уведомление отправлено с ошибкой",
                    notification_id=notification.notification_id,
                    status_code=response.status_code,
                    response=response.text
                )
                
        except Exception as e:
            self.logger.error(
                "Ошибка отправки webhook уведомления",
                error=str(e),
                notification_id=notification.notification_id
            )
    
    def _send_console_notification(self, notification: OperatorNotification):
        """Отправка консольного уведомления"""
        print("\n" + "="*80)
        print(f"🚨 УВЕДОМЛЕНИЕ ОПЕРАТОРА")
        print("="*80)
        print(f"ID: {notification.notification_id}")
        print(f"Приоритет: {notification.priority.upper()}")
        print(f"Время: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Тип: {notification.escalation_type.value}")
        print("-"*80)
        print(notification.message)
        print("="*80 + "\n")
    
    def _send_log_notification(self, notification: OperatorNotification):
        """Отправка лог уведомления"""
        if notification.priority == "critical":
            self.logger.critical(
                "КРИТИЧЕСКОЕ УВЕДОМЛЕНИЕ ОПЕРАТОРА",
                notification_id=notification.notification_id,
                escalation_id=notification.escalation_id,
                priority=notification.priority,
                title=notification.title
            )
        elif notification.priority == "high":
            self.logger.error(
                "УВЕДОМЛЕНИЕ ОПЕРАТОРА ВЫСОКОГО ПРИОРИТЕТА",
                notification_id=notification.notification_id,
                escalation_id=notification.escalation_id,
                priority=notification.priority,
                title=notification.title
            )
        else:
            self.logger.warning(
                "УВЕДОМЛЕНИЕ ОПЕРАТОРА",
                notification_id=notification.notification_id,
                escalation_id=notification.escalation_id,
                priority=notification.priority,
                title=notification.title
            )
    
    def acknowledge_notification(self, notification_id: str, operator_id: str) -> bool:
        """
        Подтверждение уведомления оператором
        
        Args:
            notification_id: ID уведомления
            operator_id: ID оператора
            
        Returns:
            True если уведомление успешно подтверждено
        """
        if notification_id not in self.notifications:
            self.logger.warning("Уведомление не найдено", notification_id=notification_id)
            return False
        
        notification = self.notifications[notification_id]
        
        if notification.acknowledged:
            self.logger.warning("Уведомление уже подтверждено", notification_id=notification_id)
            return False
        
        notification.acknowledged = True
        notification.acknowledged_by = operator_id
        notification.acknowledged_at = datetime.now()
        
        # Записываем действие оператора
        action = OperatorAction(
            action_id=f"action_{notification_id}_{int(time.time() * 1000)}",
            notification_id=notification_id,
            action_type=OperatorAction.ACKNOWLEDGE,
            operator_id=operator_id,
            timestamp=datetime.now(),
            notes="Уведомление подтверждено оператором"
        )
        
        self.operator_actions[action.action_id] = action
        self.operator_stats["acknowledged_notifications"] += 1
        self.operator_stats["pending_notifications"] -= 1
        self.operator_stats["operator_actions"] += 1
        
        self.logger.info(
            "Уведомление подтверждено оператором",
            notification_id=notification_id,
            operator_id=operator_id
        )
        
        return True
    
    def resolve_notification(self, notification_id: str, operator_id: str, 
                           resolution_notes: str) -> bool:
        """
        Разрешение уведомления оператором
        
        Args:
            notification_id: ID уведомления
            operator_id: ID оператора
            resolution_notes: Заметки о разрешении
            
        Returns:
            True если уведомление успешно разрешено
        """
        if notification_id not in self.notifications:
            self.logger.warning("Уведомление не найдено", notification_id=notification_id)
            return False
        
        notification = self.notifications[notification_id]
        
        if notification.resolved:
            self.logger.warning("Уведомление уже разрешено", notification_id=notification_id)
            return False
        
        notification.resolved = True
        notification.resolved_by = operator_id
        notification.resolved_at = datetime.now()
        notification.resolution_notes = resolution_notes
        
        # Записываем действие оператора
        action = OperatorAction(
            action_id=f"action_{notification_id}_{int(time.time() * 1000)}",
            notification_id=notification_id,
            action_type=OperatorAction.RESOLVE,
            operator_id=operator_id,
            timestamp=datetime.now(),
            notes=resolution_notes
        )
        
        self.operator_actions[action.action_id] = action
        self.operator_stats["resolved_notifications"] += 1
        self.operator_stats["operator_actions"] += 1
        
        self.logger.info(
            "Уведомление разрешено оператором",
            notification_id=notification_id,
            operator_id=operator_id,
            resolution_notes=resolution_notes
        )
        
        return True
    
    def get_notification_status(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса уведомления"""
        if notification_id not in self.notifications:
            return None
        
        return self.notifications[notification_id].to_dict()
    
    def get_pending_notifications(self) -> List[Dict[str, Any]]:
        """Получение ожидающих уведомлений"""
        return [
            notification.to_dict()
            for notification in self.notifications.values()
            if not notification.resolved
        ]
    
    def get_operator_stats(self) -> Dict[str, Any]:
        """Получение статистики оператора"""
        return {
            **self.operator_stats,
            "total_notifications": len(self.notifications),
            "total_actions": len(self.operator_actions),
            "notification_config": self.notification_config
        }
    
    def cleanup_old_notifications(self, days: int = 30):
        """Очистка старых уведомлений"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # Очищаем старые уведомления
        old_notifications = [
            notification_id for notification_id, notification in self.notifications.items()
            if notification.timestamp < cutoff_time and notification.resolved
        ]
        
        for notification_id in old_notifications:
            del self.notifications[notification_id]
        
        # Очищаем старые действия
        old_actions = [
            action_id for action_id, action in self.operator_actions.items()
            if action.timestamp < cutoff_time
        ]
        
        for action_id in old_actions:
            del self.operator_actions[action_id]
        
        self.logger.info(
            "Старые уведомления и действия очищены",
            notifications_removed=len(old_notifications),
            actions_removed=len(old_actions)
        )
