"""
Тесты для системы идемпотентности
"""

import pytest
from unittest.mock import Mock

from src.utils.idempotency_system import (
    IdempotencySystem, IdempotencyKey, IdempotencyResult,
    IdempotencyStatus, CommandIdempotencyChecker
)


class TestIdempotencySystem:
    """Тесты для IdempotencySystem"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.idempotency_system = IdempotencySystem()
    
    def test_initialization(self):
        """Тест инициализации системы идемпотентности"""
        assert len(self.idempotency_system.executed_operations) == 0
        assert self.idempotency_system.max_entries == 10000
        assert self.idempotency_system.retention_days == 30
    
    def test_generate_idempotency_key(self):
        """Тест генерации ключа идемпотентности"""
        key = self.idempotency_system.generate_idempotency_key(
            operation="install_package",
            parameters={"package": "nginx", "version": "1.18.0"},
            context={"server": "test.example.com"}
        )
        
        assert isinstance(key, IdempotencyKey)
        assert key.operation == "install_package"
        assert key.parameters == {"package": "nginx", "version": "1.18.0"}
        assert key.context == {"server": "test.example.com"}
        assert key.key_hash is not None
        assert len(key.key_hash) == 64  # SHA-256 hash length
    
    def test_check_idempotency_new_operation(self):
        """Тест проверки идемпотентности для новой операции"""
        key = self.idempotency_system.generate_idempotency_key(
            operation="install_package",
            parameters={"package": "nginx"}
        )
        
        result = self.idempotency_system.check_idempotency(key)
        
        assert result.status == IdempotencyStatus.NOT_EXECUTED
        assert result.already_executed is False
        assert result.previous_result is None


if __name__ == "__main__":
    pytest.main([__file__])