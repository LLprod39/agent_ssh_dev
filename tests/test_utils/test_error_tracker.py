"""
Тесты для системы подсчета ошибок
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock

from src.utils.error_tracker import (
    ErrorTracker, ErrorRecord, AttemptRecord, StepErrorStats,
    ErrorSeverity, EscalationLevel
)


class TestErrorTracker:
    """Тесты для ErrorTracker"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.error_tracker = ErrorTracker(
            error_threshold=3,
            escalation_threshold=5,
            max_retention_days=7
        )
        self.step_id = "test_step_1"
    
    def test_initialization(self):
        """Тест инициализации ErrorTracker"""
        assert self.error_tracker.error_threshold == 3
        assert self.error_tracker.escalation_threshold == 5
        assert self.error_tracker.max_retention_days == 7
        assert len(self.error_tracker.error_records) == 0
        assert len(self.error_tracker.attempt_records) == 0
        assert len(self.error_tracker.step_stats) == 0
    
    def test_record_successful_attempt(self):
        """Тест записи успешной попытки"""
        attempt_id = self.error_tracker.record_attempt(
            step_id=self.step_id,
            command="ls -la",
            success=True,
            duration=0.5,
            exit_code=0,
            metadata={"test": True}
        )
        
        assert attempt_id is not None
        assert self.step_id in self.error_tracker.attempt_records
        assert len(self.error_tracker.attempt_records[self.step_id]) == 1
        
        attempt = self.error_tracker.attempt_records[self.step_id][0]
        assert attempt.attempt_id == attempt_id
        assert attempt.command == "ls -la"
        assert attempt.success is True
        assert attempt.duration == 0.5
        assert attempt.exit_code == 0
        assert attempt.metadata["test"] is True
    
    def test_record_failed_attempt(self):
        """Тест записи неудачной попытки"""
        attempt_id = self.error_tracker.record_attempt(
            step_id=self.step_id,
            command="invalid_command",
            success=False,
            duration=0.1,
            exit_code=1,
            error_message="command not found",
            metadata={"test": True}
        )
        
        assert attempt_id is not None
        assert self.step_id in self.error_tracker.attempt_records
        assert self.step_id in self.error_tracker.error_records
        
        # Проверяем запись попытки
        attempt = self.error_tracker.attempt_records[self.step_id][0]
        assert attempt.success is False
        assert attempt.error_message == "command not found"
        
        # Проверяем запись ошибки
        error = self.error_tracker.error_records[self.step_id][0]
        assert error.command == "invalid_command"
        assert error.error_message == "command not found"
        assert error.exit_code == 1
    
    def test_error_count_tracking(self):
        """Тест подсчета ошибок"""
        # Записываем несколько неудачных попыток
        for i in range(4):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"command_{i}",
                success=False,
                duration=0.1,
                exit_code=1,
                error_message=f"error_{i}"
            )
        
        assert self.error_tracker.get_step_error_count(self.step_id) == 4
        assert self.error_tracker.get_step_attempt_count(self.step_id) == 4
    
    def test_escalation_levels(self):
        """Тест уровней эскалации"""
        # Нет ошибок - нет эскалации
        assert self.error_tracker.get_escalation_level(self.step_id) == EscalationLevel.NONE
        
        # 1 ошибка - автокоррекция
        self.error_tracker.record_attempt(
            step_id=self.step_id,
            command="cmd1",
            success=False,
            duration=0.1,
            error_message="error1"
        )
        assert self.error_tracker.get_escalation_level(self.step_id) == EscalationLevel.AUTOCORRECTION
        
        # 3 ошибки - эскалация к планировщику
        for i in range(2, 4):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=False,
                duration=0.1,
                error_message=f"error{i}"
            )
        assert self.error_tracker.get_escalation_level(self.step_id) == EscalationLevel.PLANNER_NOTIFICATION
        
        # 5 ошибок - эскалация к человеку
        for i in range(4, 6):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=False,
                duration=0.1,
                error_message=f"error{i}"
            )
        assert self.error_tracker.get_escalation_level(self.step_id) == EscalationLevel.HUMAN_ESCALATION
    
    def test_escalation_checks(self):
        """Тест проверок эскалации"""
        # Нет ошибок
        assert not self.error_tracker.should_escalate_to_planner(self.step_id)
        assert not self.error_tracker.should_escalate_to_human(self.step_id)
        
        # 3 ошибки - эскалация к планировщику
        for i in range(3):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=False,
                duration=0.1,
                error_message=f"error{i}"
            )
        
        assert self.error_tracker.should_escalate_to_planner(self.step_id)
        assert not self.error_tracker.should_escalate_to_human(self.step_id)
        
        # 5 ошибок - эскалация к человеку
        for i in range(3, 5):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=False,
                duration=0.1,
                error_message=f"error{i}"
            )
        
        assert self.error_tracker.should_escalate_to_planner(self.step_id)
        assert self.error_tracker.should_escalate_to_human(self.step_id)
    
    def test_error_severity_detection(self):
        """Тест определения серьезности ошибок"""
        # Критическая ошибка
        error_id = self.error_tracker.record_error(
            step_id=self.step_id,
            command="sudo rm -rf /",
            error_message="permission denied",
            exit_code=1
        )
        
        error = self.error_tracker.error_records[self.step_id][0]
        assert error.severity == ErrorSeverity.CRITICAL
        
        # Высокая ошибка
        error_id = self.error_tracker.record_error(
            step_id=self.step_id,
            command="curl http://example.com",
            error_message="connection refused",
            exit_code=1
        )
        
        error = self.error_tracker.error_records[self.step_id][1]
        assert error.severity == ErrorSeverity.HIGH
        
        # Средняя ошибка
        error_id = self.error_tracker.record_error(
            step_id=self.step_id,
            command="ls --invalid-option",
            error_message="syntax error",
            exit_code=1
        )
        
        error = self.error_tracker.error_records[self.step_id][2]
        assert error.severity == ErrorSeverity.MEDIUM
    
    def test_error_patterns(self):
        """Тест анализа паттернов ошибок"""
        # Записываем ошибки разных типов
        error_messages = [
            "permission denied",
            "command not found",
            "connection refused",
            "permission denied",  # Дубликат
            "file not found"
        ]
        
        for i, error_msg in enumerate(error_messages):
            self.error_tracker.record_error(
                step_id=self.step_id,
                command=f"cmd{i}",
                error_message=error_msg,
                exit_code=1
            )
        
        patterns = self.error_tracker.get_error_patterns(self.step_id)
        assert "permission_denied" in patterns
        assert patterns["permission_denied"] == 2  # Два раза
        assert "command_not_found" in patterns
        assert "connection_error" in patterns
        assert "file_not_found" in patterns
    
    def test_step_stats(self):
        """Тест статистики шага"""
        # Записываем смешанные попытки
        attempts = [
            (True, 0.5, 0),   # Успешная
            (False, 0.1, 1),  # Неудачная
            (True, 0.3, 0),   # Успешная
            (False, 0.2, 1),  # Неудачная с автокоррекцией
        ]
        
        for i, (success, duration, exit_code) in enumerate(attempts):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=success,
                duration=duration,
                exit_code=exit_code,
                autocorrection_used=(i == 3)
            )
        
        stats = self.error_tracker.get_step_stats(self.step_id)
        assert stats is not None
        assert stats.total_attempts == 4
        assert stats.successful_attempts == 2
        assert stats.failed_attempts == 2
        assert stats.error_count == 2
        assert stats.autocorrection_count == 1
        assert abs(stats.total_duration - 1.1) < 0.01  # Учитываем погрешность вычислений с плавающей точкой
        assert stats.success_rate == 50.0
        assert stats.failure_rate == 50.0
        assert abs(stats.average_duration - 0.275) < 0.01  # Учитываем погрешность вычислений с плавающей точкой
    
    def test_error_summary(self):
        """Тест сводки ошибок"""
        # Записываем несколько ошибок
        for i in range(3):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=False,
                duration=0.1,
                error_message=f"error{i}"
            )
        
        summary = self.error_tracker.get_error_summary(self.step_id)
        
        assert summary["step_id"] == self.step_id
        assert summary["error_count"] == 3
        assert summary["attempt_count"] == 3
        assert summary["success_rate"] == 0.0
        assert summary["failure_rate"] == 100.0
        assert summary["escalation_level"] == EscalationLevel.PLANNER_NOTIFICATION.value
        assert len(summary["recent_errors"]) == 3
    
    def test_global_stats(self):
        """Тест глобальной статистики"""
        # Записываем попытки для разных шагов
        for step_id in ["step1", "step2"]:
            for i in range(2):
                self.error_tracker.record_attempt(
                    step_id=step_id,
                    command=f"cmd{i}",
                    success=(i == 0),  # Первая успешная, вторая неудачная
                    duration=0.1,
                    exit_code=0 if i == 0 else 1,
                    error_message=None if i == 0 else "error",
                    autocorrection_used=(i == 1)
                )
        
        stats = self.error_tracker.get_global_stats()
        
        assert stats["total_attempts"] == 4
        assert stats["total_errors"] == 2
        assert stats["success_rate"] == 50.0
        assert stats["autocorrections_applied"] == 2
        assert stats["autocorrections_successful"] == 0  # Автокоррекция не помогла
        assert stats["steps_tracked"] == 2
    
    def test_cleanup_old_records(self):
        """Тест очистки старых записей"""
        # Создаем старые записи напрямую в хранилище
        old_time = datetime.now() - timedelta(days=10)
        
        # Создаем старую запись попытки
        old_attempt = AttemptRecord(
            attempt_id="old_attempt",
            step_id=self.step_id,
            command="old_command",
            timestamp=old_time,
            success=False,
            duration=0.1,
            error_message="old_error"
        )
        
        # Создаем старую запись ошибки
        old_error = ErrorRecord(
            error_id="old_error",
            step_id=self.step_id,
            command="old_command",
            error_message="old_error",
            severity=ErrorSeverity.LOW,
            timestamp=old_time
        )
        
        # Добавляем старые записи
        self.error_tracker.attempt_records[self.step_id] = [old_attempt]
        self.error_tracker.error_records[self.step_id] = [old_error]
        
        # Создаем новые записи
        self.error_tracker.record_attempt(
            step_id=self.step_id,
            command="new_command",
            success=True,
            duration=0.1
        )
        
        # Проверяем, что есть и старые, и новые записи
        assert len(self.error_tracker.attempt_records[self.step_id]) == 2
        assert len(self.error_tracker.error_records[self.step_id]) == 1  # Новая запись не создает ошибку, так как она успешная
        
        # Очищаем старые записи
        self.error_tracker.cleanup_old_records()
        
        # Проверяем, что остались только новые записи
        assert len(self.error_tracker.attempt_records[self.step_id]) == 1
        # Проверяем, что старые записи об ошибках удалены
        assert self.step_id not in self.error_tracker.error_records or len(self.error_tracker.error_records[self.step_id]) == 0
    
    def test_reset_step_stats(self):
        """Тест сброса статистики шага"""
        # Записываем данные для шага
        self.error_tracker.record_attempt(
            step_id=self.step_id,
            command="test_command",
            success=False,
            duration=0.1,
            error_message="test_error"
        )
        
        # Проверяем, что данные есть
        assert self.step_id in self.error_tracker.attempt_records
        assert self.step_id in self.error_tracker.error_records
        assert self.step_id in self.error_tracker.step_stats
        
        # Сбрасываем статистику
        self.error_tracker.reset_step_stats(self.step_id)
        
        # Проверяем, что данные удалены
        assert self.step_id not in self.error_tracker.attempt_records
        assert self.step_id not in self.error_tracker.error_records
        assert self.step_id not in self.error_tracker.step_stats
    
    def test_recent_errors(self):
        """Тест получения недавних ошибок"""
        # Записываем ошибки
        for i in range(5):
            self.error_tracker.record_attempt(
                step_id=self.step_id,
                command=f"cmd{i}",
                success=False,
                duration=0.1,
                error_message=f"error{i}"
            )
            time.sleep(0.01)  # Небольшая задержка между записями
        
        # Получаем недавние ошибки (последние 24 часа)
        recent_errors = self.error_tracker.get_recent_errors(self.step_id, hours=24)
        assert len(recent_errors) == 5
        
        # Получаем недавние ошибки (последние 1 миллисекунду)
        recent_errors = self.error_tracker.get_recent_errors(self.step_id, hours=0.0000001)
        assert len(recent_errors) == 0  # Все ошибки старше 1 миллисекунды


class TestErrorRecord:
    """Тесты для ErrorRecord"""
    
    def test_error_record_creation(self):
        """Тест создания записи об ошибке"""
        error_record = ErrorRecord(
            error_id="test_error_1",
            step_id="test_step",
            command="test_command",
            error_message="test error message",
            severity=ErrorSeverity.HIGH,
            timestamp=datetime.now(),
            exit_code=1,
            retry_count=2,
            autocorrection_applied=True,
            escalation_level=EscalationLevel.PLANNER_NOTIFICATION,
            metadata={"test": True}
        )
        
        assert error_record.error_id == "test_error_1"
        assert error_record.step_id == "test_step"
        assert error_record.command == "test_command"
        assert error_record.error_message == "test error message"
        assert error_record.severity == ErrorSeverity.HIGH
        assert error_record.exit_code == 1
        assert error_record.retry_count == 2
        assert error_record.autocorrection_applied is True
        assert error_record.escalation_level == EscalationLevel.PLANNER_NOTIFICATION
        assert error_record.metadata["test"] is True


class TestAttemptRecord:
    """Тесты для AttemptRecord"""
    
    def test_attempt_record_creation(self):
        """Тест создания записи о попытке"""
        attempt_record = AttemptRecord(
            attempt_id="test_attempt_1",
            step_id="test_step",
            command="test_command",
            timestamp=datetime.now(),
            success=True,
            duration=0.5,
            exit_code=0,
            error_message=None,
            autocorrection_used=False,
            metadata={"test": True}
        )
        
        assert attempt_record.attempt_id == "test_attempt_1"
        assert attempt_record.step_id == "test_step"
        assert attempt_record.command == "test_command"
        assert attempt_record.success is True
        assert attempt_record.duration == 0.5
        assert attempt_record.exit_code == 0
        assert attempt_record.error_message is None
        assert attempt_record.autocorrection_used is False
        assert attempt_record.metadata["test"] is True


class TestStepErrorStats:
    """Тесты для StepErrorStats"""
    
    def test_step_error_stats_creation(self):
        """Тест создания статистики шага"""
        stats = StepErrorStats(
            step_id="test_step",
            total_attempts=10,
            successful_attempts=7,
            failed_attempts=3,
            error_count=3,
            autocorrection_count=1,
            total_duration=5.0,
            last_error_timestamp=datetime.now(),
            error_patterns={"permission_denied": 2, "command_not_found": 1},
            escalation_history=[EscalationLevel.AUTOCORRECTION, EscalationLevel.PLANNER_NOTIFICATION]
        )
        
        assert stats.step_id == "test_step"
        assert stats.total_attempts == 10
        assert stats.successful_attempts == 7
        assert stats.failed_attempts == 3
        assert stats.error_count == 3
        assert stats.autocorrection_count == 1
        assert stats.total_duration == 5.0
        assert stats.success_rate == 70.0
        assert stats.failure_rate == 30.0
        assert stats.average_duration == 0.5
        assert len(stats.error_patterns) == 2
        assert len(stats.escalation_history) == 2


if __name__ == "__main__":
    pytest.main([__file__])
