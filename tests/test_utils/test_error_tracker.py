"""
Тесты для системы отслеживания ошибок
"""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.utils.error_tracker import (
    ErrorTracker, ErrorEntry, ErrorSummary, ErrorPattern,
    ErrorSeverity, ErrorCategory
)


class TestErrorTracker:
    """Тесты для ErrorTracker"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.error_tracker = ErrorTracker()
    
    def test_initialization(self):
        """Тест инициализации трекера ошибок"""
        assert len(self.error_tracker.errors) == 0
        assert self.error_tracker.max_entries == 1000
        assert self.error_tracker.retention_days == 7
    
    def test_log_error(self):
        """Тест логирования ошибки"""
        error_entry = self.error_tracker.log_error(
            error_type="CommandExecutionError",
            message="Command failed",
            context={"command": "apt install nginx"},
            severity=ErrorSeverity.HIGH
        )
        
        assert error_entry.error_type == "CommandExecutionError"
        assert error_entry.message == "Command failed"
        assert error_entry.severity == ErrorSeverity.HIGH
        assert len(self.error_tracker.errors) == 1
    
    def test_get_error_summary(self):
        """Тест получения сводки ошибок"""
        # Добавляем несколько ошибок
        self.error_tracker.log_error("Error1", "Message1", severity=ErrorSeverity.HIGH)
        self.error_tracker.log_error("Error2", "Message2", severity=ErrorSeverity.MEDIUM)
        self.error_tracker.log_error("Error1", "Message3", severity=ErrorSeverity.HIGH)
        
        summary = self.error_tracker.get_error_summary()
        
        assert summary.total_errors == 3
        assert summary.errors_by_type["Error1"] == 2
        assert summary.errors_by_type["Error2"] == 1
        assert summary.errors_by_severity[ErrorSeverity.HIGH] == 2
        assert summary.errors_by_severity[ErrorSeverity.MEDIUM] == 1


if __name__ == "__main__":
    pytest.main([__file__])