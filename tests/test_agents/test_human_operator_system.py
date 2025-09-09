"""
Тесты для Human Operator System
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from src.agents.human_operator_system import (
    HumanOperatorSystem, OperatorNotification, OperatorAction,
    NotificationMethod, OperatorAction as OperatorActionEnum
)
from src.agents.escalation_system import EscalationRequest, EscalationType, EscalationStatus


class TestHumanOperatorSystem:
    """Тесты для Human Operator System"""
    
    @pytest.fixture
    def operator_config(self):
        """Конфигурация системы оператора"""
        return {
            "email_notifications": {
                "enabled": True,
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "username": "test@example.com",
                "password": "test_password",
                "from_address": "test@example.com",
                "to_addresses": ["operator@example.com"]
            },
            "webhook_notifications": {
                "enabled": True,
                "url": "https://webhook.example.com/notify",
                "headers": {"Authorization": "Bearer token"},
                "timeout": 30
            },
            "console_notifications": {
                "enabled": True
            }
        }
    
    @pytest.fixture
    def operator_system(self, operator_config):
        """Система оператора"""
        return HumanOperatorSystem(operator_config)
    
    @pytest.fixture
    def escalation_request(self):
        """Запрос на эскалацию"""
        return EscalationRequest(
            escalation_id="test_escalation_1",
            escalation_type=EscalationType.HUMAN_ESCALATION,
            step_id="step_1",
            task_id="task_1",
            error_count=5,
            threshold_exceeded=True,
            reason="Превышен порог ошибок",
            context={
                "task_title": "Тестовая задача",
                "step_title": "Тестовый шаг"
            },
            error_details={
                "recent_errors": [
                    {
                        "command": "sudo apt install test-package",
                        "error_message": "Package not found"
                    },
                    {
                        "command": "systemctl start test-service",
                        "error_message": "Service not found"
                    }
                ]
            },
            timestamp=datetime.now()
        )
    
    def test_initialization(self, operator_config):
        """Тест инициализации системы оператора"""
        system = HumanOperatorSystem(operator_config)
        
        assert system.config == operator_config
        assert len(system.notifications) == 0
        assert len(system.operator_actions) == 0
        assert system.operator_stats["total_notifications"] == 0
        assert system.notification_config["email"]["enabled"] is True
        assert system.notification_config["webhook"]["enabled"] is True
        assert system.notification_config["console"]["enabled"] is True
    
    def test_handle_escalation_success(self, operator_system, escalation_request):
        """Тест успешной обработки эскалации"""
        with patch.object(operator_system, '_send_notifications') as mock_send:
            notification = operator_system.handle_escalation(escalation_request)
            
            assert isinstance(notification, OperatorNotification)
            assert notification.escalation_id == escalation_request.escalation_id
            assert notification.escalation_type == escalation_request.escalation_type
            assert notification.priority == "high"  # HUMAN_ESCALATION = high
            assert notification.acknowledged is False
            assert notification.resolved is False
            assert len(notification.notification_methods) > 0
            assert notification.notification_id in operator_system.notifications
            assert operator_system.operator_stats["total_notifications"] == 1
            assert operator_system.operator_stats["pending_notifications"] == 1
            mock_send.assert_called_once_with(notification)
    
    def test_determine_priority_emergency(self, operator_system):
        """Тест определения приоритета для экстренной остановки"""
        emergency_request = EscalationRequest(
            escalation_id="emergency_1",
            escalation_type=EscalationType.EMERGENCY_STOP,
            step_id="step_1",
            task_id="task_1",
            error_count=10,
            threshold_exceeded=True,
            reason="Критическая ошибка",
            context={},
            error_details={},
            timestamp=datetime.now()
        )
        
        priority = operator_system._determine_priority(emergency_request)
        assert priority == "critical"
    
    def test_determine_priority_plan_revision(self, operator_system):
        """Тест определения приоритета для пересмотра плана"""
        plan_request = EscalationRequest(
            escalation_id="plan_1",
            escalation_type=EscalationType.PLAN_REVISION,
            step_id="step_1",
            task_id="task_1",
            error_count=3,
            threshold_exceeded=False,
            reason="Необходим пересмотр плана",
            context={},
            error_details={},
            timestamp=datetime.now()
        )
        
        priority = operator_system._determine_priority(plan_request)
        assert priority == "medium"
    
    def test_create_notification(self, operator_system, escalation_request):
        """Тест создания уведомления"""
        priority = "high"
        notification = operator_system._create_notification(escalation_request, priority)
        
        assert isinstance(notification, OperatorNotification)
        assert notification.escalation_id == escalation_request.escalation_id
        assert notification.priority == priority
        assert "ВЫСОКИЙ ПРИОРИТЕТ" in notification.title
        assert "Тестовая задача" in notification.message
        assert "Тестовый шаг" in notification.message
        assert notification.metadata["step_id"] == escalation_request.step_id
        assert notification.metadata["task_id"] == escalation_request.task_id
        assert notification.metadata["error_count"] == escalation_request.error_count
    
    def test_get_notification_methods_critical(self, operator_system):
        """Тест получения методов уведомления для критического приоритета"""
        methods = operator_system._get_notification_methods("critical")
        
        assert NotificationMethod.LOG in methods
        assert NotificationMethod.EMAIL in methods
        assert NotificationMethod.WEBHOOK in methods
        assert NotificationMethod.CONSOLE in methods
    
    def test_get_notification_methods_high(self, operator_system):
        """Тест получения методов уведомления для высокого приоритета"""
        methods = operator_system._get_notification_methods("high")
        
        assert NotificationMethod.LOG in methods
        assert NotificationMethod.EMAIL in methods
        assert NotificationMethod.CONSOLE in methods
        assert NotificationMethod.WEBHOOK not in methods
    
    def test_get_notification_methods_low(self, operator_system):
        """Тест получения методов уведомления для низкого приоритета"""
        methods = operator_system._get_notification_methods("low")
        
        assert NotificationMethod.LOG in methods
        assert NotificationMethod.CONSOLE in methods
        assert NotificationMethod.EMAIL not in methods
        assert NotificationMethod.WEBHOOK not in methods
    
    def test_create_notification_content_critical(self, operator_system, escalation_request):
        """Тест создания содержимого уведомления для критического приоритета"""
        title, message = operator_system._create_notification_content(escalation_request, "critical")
        
        assert "🚨 КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ" in title
        assert "Тестовый шаг" in title
        assert "Тип эскалации" in message
        assert "Тестовая задача" in message
        assert "Количество ошибок: 5" in message
        assert "Порог превышен: True" in message
    
    def test_send_email_notification_success(self, operator_system, escalation_request):
        """Тест успешной отправки email уведомления"""
        notification = operator_system._create_notification(escalation_request, "high")
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value = mock_server
            
            operator_system._send_email_notification(notification)
            
            mock_smtp.assert_called_once_with("smtp.example.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("test@example.com", "test_password")
            mock_server.send_message.assert_called_once()
            mock_server.quit.assert_called_once()
    
    def test_send_email_notification_disabled(self, operator_config, escalation_request):
        """Тест отправки email уведомления при отключенной настройке"""
        operator_config["email_notifications"]["enabled"] = False
        system = HumanOperatorSystem(operator_config)
        notification = system._create_notification(escalation_request, "high")
        
        with patch('smtplib.SMTP') as mock_smtp:
            system._send_email_notification(notification)
            mock_smtp.assert_not_called()
    
    def test_send_webhook_notification_success(self, operator_system, escalation_request):
        """Тест успешной отправки webhook уведомления"""
        notification = operator_system._create_notification(escalation_request, "critical")
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            operator_system._send_webhook_notification(notification)
            
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["url"] == "https://webhook.example.com/notify"
            assert call_args[1]["json"]["notification_id"] == notification.notification_id
            assert call_args[1]["json"]["priority"] == "critical"
    
    def test_send_webhook_notification_failure(self, operator_system, escalation_request):
        """Тест неудачной отправки webhook уведомления"""
        notification = operator_system._create_notification(escalation_request, "critical")
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response
            
            # Не должно вызывать исключение
            operator_system._send_webhook_notification(notification)
            mock_post.assert_called_once()
    
    def test_send_console_notification(self, operator_system, escalation_request, capsys):
        """Тест отправки консольного уведомления"""
        notification = operator_system._create_notification(escalation_request, "high")
        
        operator_system._send_console_notification(notification)
        
        captured = capsys.readouterr()
        assert "🚨 УВЕДОМЛЕНИЕ ОПЕРАТОРА" in captured.out
        assert notification.notification_id in captured.out
        assert "ВЫСОКИЙ ПРИОРИТЕТ" in captured.out
        assert notification.message in captured.out
    
    def test_send_log_notification_critical(self, operator_system, escalation_request):
        """Тест отправки лог уведомления для критического приоритета"""
        notification = operator_system._create_notification(escalation_request, "critical")
        
        with patch.object(operator_system.logger, 'critical') as mock_critical:
            operator_system._send_log_notification(notification)
            mock_critical.assert_called_once()
            call_args = mock_critical.call_args
            assert "КРИТИЧЕСКОЕ УВЕДОМЛЕНИЕ ОПЕРАТОРА" in call_args[0][0]
    
    def test_acknowledge_notification_success(self, operator_system, escalation_request):
        """Тест успешного подтверждения уведомления"""
        notification = operator_system.handle_escalation(escalation_request)
        
        result = operator_system.acknowledge_notification(
            notification.notification_id, 
            "operator_1"
        )
        
        assert result is True
        assert notification.acknowledged is True
        assert notification.acknowledged_by == "operator_1"
        assert notification.acknowledged_at is not None
        assert operator_system.operator_stats["acknowledged_notifications"] == 1
        assert operator_system.operator_stats["pending_notifications"] == 0
        assert len(operator_system.operator_actions) == 1
    
    def test_acknowledge_notification_not_found(self, operator_system):
        """Тест подтверждения несуществующего уведомления"""
        result = operator_system.acknowledge_notification("nonexistent", "operator_1")
        assert result is False
    
    def test_acknowledge_notification_already_acknowledged(self, operator_system, escalation_request):
        """Тест подтверждения уже подтвержденного уведомления"""
        notification = operator_system.handle_escalation(escalation_request)
        operator_system.acknowledge_notification(notification.notification_id, "operator_1")
        
        result = operator_system.acknowledge_notification(notification.notification_id, "operator_2")
        assert result is False
    
    def test_resolve_notification_success(self, operator_system, escalation_request):
        """Тест успешного разрешения уведомления"""
        notification = operator_system.handle_escalation(escalation_request)
        
        result = operator_system.resolve_notification(
            notification.notification_id,
            "operator_1",
            "Проблема решена"
        )
        
        assert result is True
        assert notification.resolved is True
        assert notification.resolved_by == "operator_1"
        assert notification.resolved_at is not None
        assert notification.resolution_notes == "Проблема решена"
        assert operator_system.operator_stats["resolved_notifications"] == 1
        assert len(operator_system.operator_actions) == 1
    
    def test_resolve_notification_not_found(self, operator_system):
        """Тест разрешения несуществующего уведомления"""
        result = operator_system.resolve_notification("nonexistent", "operator_1", "Notes")
        assert result is False
    
    def test_resolve_notification_already_resolved(self, operator_system, escalation_request):
        """Тест разрешения уже разрешенного уведомления"""
        notification = operator_system.handle_escalation(escalation_request)
        operator_system.resolve_notification(notification.notification_id, "operator_1", "Notes")
        
        result = operator_system.resolve_notification(notification.notification_id, "operator_2", "Notes2")
        assert result is False
    
    def test_get_notification_status(self, operator_system, escalation_request):
        """Тест получения статуса уведомления"""
        notification = operator_system.handle_escalation(escalation_request)
        
        status = operator_system.get_notification_status(notification.notification_id)
        
        assert status is not None
        assert status["notification_id"] == notification.notification_id
        assert status["escalation_id"] == escalation_request.escalation_id
        assert status["priority"] == "high"
        assert status["acknowledged"] is False
        assert status["resolved"] is False
    
    def test_get_notification_status_not_found(self, operator_system):
        """Тест получения статуса несуществующего уведомления"""
        status = operator_system.get_notification_status("nonexistent")
        assert status is None
    
    def test_get_pending_notifications(self, operator_system, escalation_request):
        """Тест получения ожидающих уведомлений"""
        notification1 = operator_system.handle_escalation(escalation_request)
        
        # Создаем второе уведомление
        escalation_request2 = EscalationRequest(
            escalation_id="test_escalation_2",
            escalation_type=EscalationType.PLAN_REVISION,
            step_id="step_2",
            task_id="task_2",
            error_count=2,
            threshold_exceeded=False,
            reason="Пересмотр плана",
            context={"task_title": "Задача 2", "step_title": "Шаг 2"},
            error_details={},
            timestamp=datetime.now()
        )
        notification2 = operator_system.handle_escalation(escalation_request2)
        
        # Разрешаем первое уведомление
        operator_system.resolve_notification(notification1.notification_id, "operator_1", "Resolved")
        
        pending = operator_system.get_pending_notifications()
        
        assert len(pending) == 1
        assert pending[0]["notification_id"] == notification2.notification_id
    
    def test_get_operator_stats(self, operator_system, escalation_request):
        """Тест получения статистики оператора"""
        notification = operator_system.handle_escalation(escalation_request)
        operator_system.acknowledge_notification(notification.notification_id, "operator_1")
        operator_system.resolve_notification(notification.notification_id, "operator_1", "Resolved")
        
        stats = operator_system.get_operator_stats()
        
        assert stats["total_notifications"] == 1
        assert stats["acknowledged_notifications"] == 1
        assert stats["resolved_notifications"] == 1
        assert stats["pending_notifications"] == 0
        assert stats["operator_actions"] == 2
        assert "notification_config" in stats
    
    def test_cleanup_old_notifications(self, operator_system, escalation_request):
        """Тест очистки старых уведомлений"""
        # Создаем уведомление
        notification = operator_system.handle_escalation(escalation_request)
        
        # Разрешаем его
        operator_system.resolve_notification(notification.notification_id, "operator_1", "Resolved")
        
        # Устанавливаем старое время
        old_time = datetime.now() - timedelta(days=35)
        notification.timestamp = old_time
        
        # Очищаем старые уведомления
        operator_system.cleanup_old_notifications(days=30)
        
        # Проверяем что уведомление удалено
        assert notification.notification_id not in operator_system.notifications
        assert len(operator_system.notifications) == 0


class TestOperatorNotification:
    """Тесты для OperatorNotification"""
    
    def test_operator_notification_creation(self):
        """Тест создания уведомления оператора"""
        notification = OperatorNotification(
            notification_id="test_notification_1",
            escalation_id="test_escalation_1",
            escalation_type=EscalationType.HUMAN_ESCALATION,
            priority="high",
            title="Test Notification",
            message="Test message",
            timestamp=datetime.now(),
            notification_methods=[NotificationMethod.EMAIL, NotificationMethod.CONSOLE]
        )
        
        assert notification.notification_id == "test_notification_1"
        assert notification.escalation_type == EscalationType.HUMAN_ESCALATION
        assert notification.priority == "high"
        assert notification.acknowledged is False
        assert notification.resolved is False
        assert len(notification.notification_methods) == 2
    
    def test_operator_notification_to_dict(self):
        """Тест преобразования уведомления в словарь"""
        notification = OperatorNotification(
            notification_id="test_notification_1",
            escalation_id="test_escalation_1",
            escalation_type=EscalationType.HUMAN_ESCALATION,
            priority="high",
            title="Test Notification",
            message="Test message",
            timestamp=datetime.now(),
            notification_methods=[NotificationMethod.EMAIL]
        )
        
        notification_dict = notification.to_dict()
        
        assert notification_dict["notification_id"] == "test_notification_1"
        assert notification_dict["escalation_id"] == "test_escalation_1"
        assert notification_dict["escalation_type"] == EscalationType.HUMAN_ESCALATION.value
        assert notification_dict["priority"] == "high"
        assert notification_dict["acknowledged"] is False
        assert notification_dict["resolved"] is False
        assert "email" in notification_dict["notification_methods"]


class TestOperatorAction:
    """Тесты для OperatorAction"""
    
    def test_operator_action_creation(self):
        """Тест создания действия оператора"""
        action = OperatorAction(
            action_id="test_action_1",
            notification_id="test_notification_1",
            action_type=OperatorActionEnum.ACKNOWLEDGE,
            operator_id="operator_1",
            timestamp=datetime.now(),
            notes="Test notes"
        )
        
        assert action.action_id == "test_action_1"
        assert action.notification_id == "test_notification_1"
        assert action.action_type == OperatorActionEnum.ACKNOWLEDGE
        assert action.operator_id == "operator_1"
        assert action.notes == "Test notes"
    
    def test_operator_action_to_dict(self):
        """Тест преобразования действия в словарь"""
        action = OperatorAction(
            action_id="test_action_1",
            notification_id="test_notification_1",
            action_type=OperatorActionEnum.RESOLVE,
            operator_id="operator_1",
            timestamp=datetime.now(),
            notes="Resolved issue"
        )
        
        action_dict = action.to_dict()
        
        assert action_dict["action_id"] == "test_action_1"
        assert action_dict["notification_id"] == "test_notification_1"
        assert action_dict["action_type"] == OperatorActionEnum.RESOLVE.value
        assert action_dict["operator_id"] == "operator_1"
        assert action_dict["notes"] == "Resolved issue"


if __name__ == "__main__":
    pytest.main([__file__])
