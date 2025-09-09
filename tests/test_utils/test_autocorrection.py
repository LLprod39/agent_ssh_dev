"""
Тесты для системы автокоррекции

Этот модуль содержит тесты для:
- Стратегий автокоррекции
- Проверки синтаксических ошибок
- Альтернативных флагов команд
- Проверки сетевого соединения
- Перезапуска сервисов
"""

import pytest
import time
from unittest.mock import Mock, patch
from typing import Dict, Any

from src.utils.autocorrection import (
    AutocorrectionEngine, 
    CorrectionStrategy, 
    CorrectionAttempt,
    AutocorrectionResult
)
from src.models.execution_model import CommandResult, ExecutionStatus, ExecutionContext
from src.agents.subtask_agent import Subtask


class TestAutocorrectionEngine:
    """Тесты для движка автокоррекции"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.engine = AutocorrectionEngine(max_attempts=3, timeout=5)
        self.mock_ssh = Mock()
        self.mock_ssh.execute_command.return_value = ("", "", 0)
        
        self.subtask = Subtask(
            subtask_id="test_001",
            title="Test Subtask",
            description="Test Description",
            commands=["test_command"],
            health_checks=[],
            rollback_commands=[]
        )
        
        self.context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=self.mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
    
    def test_initialization(self):
        """Тест инициализации движка"""
        assert self.engine.max_attempts == 3
        assert self.engine.timeout == 5
        assert len(self.engine.alternative_flags) > 0
        assert len(self.engine.command_substitutions) > 0
        assert len(self.engine.syntax_patterns) > 0
    
    def test_determine_correction_strategy_permission_denied(self):
        """Тест определения стратегии для ошибки прав доступа"""
        command = "apt install nginx"
        error_message = "permission denied"
        
        strategy = self.engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.PERMISSION_FIX
    
    def test_determine_correction_strategy_command_not_found(self):
        """Тест определения стратегии для команды не найдена"""
        command = "service nginx start"
        error_message = "command not found"
        
        strategy = self.engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.COMMAND_SUBSTITUTION
    
    def test_determine_correction_strategy_package_not_found(self):
        """Тест определения стратегии для пакета не найден"""
        command = "apt install nonexistent"
        error_message = "package not found"
        
        strategy = self.engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.PACKAGE_UPDATE
    
    def test_determine_correction_strategy_service_not_found(self):
        """Тест определения стратегии для сервиса не найден"""
        command = "systemctl start nginx"
        error_message = "service not found"
        
        strategy = self.engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.SERVICE_RESTART
    
    def test_determine_correction_strategy_connection_refused(self):
        """Тест определения стратегии для отказа в соединении"""
        command = "curl https://example.com"
        error_message = "connection refused"
        
        strategy = self.engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.NETWORK_CHECK
    
    def test_fix_permission_issues(self):
        """Тест исправления проблем с правами доступа"""
        command = "apt install nginx"
        error_message = "permission denied"
        
        corrected = self.engine._fix_permission_issues(command, error_message)
        assert corrected == "sudo apt install nginx"
    
    def test_fix_permission_issues_already_sudo(self):
        """Тест исправления прав доступа для команды с sudo"""
        command = "sudo apt install nginx"
        error_message = "permission denied"
        
        corrected = self.engine._fix_permission_issues(command, error_message)
        assert corrected is None
    
    def test_fix_syntax_errors(self):
        """Тест исправления синтаксических ошибок"""
        command = "ls  -la   /tmp"
        error_message = "syntax error"
        
        corrected = self.engine._fix_syntax_errors(command, error_message)
        assert corrected == "ls -la /tmp"
    
    def test_fix_syntax_errors_quotes(self):
        """Тест исправления неправильных кавычек"""
        command = "grep 'pattern' file.txt"
        error_message = "syntax error"
        
        corrected = self.engine._fix_syntax_errors(command, error_message)
        assert corrected == 'grep "pattern" file.txt'
    
    def test_fix_package_issues(self):
        """Тест исправления проблем с пакетами"""
        command = "apt install nginx"
        error_message = "package not found"
        
        corrected = self.engine._fix_package_issues(command, error_message)
        assert corrected == "sudo apt update && apt install nginx"
    
    def test_fix_service_issues(self):
        """Тест исправления проблем с сервисами"""
        command = "systemctl start nginx"
        error_message = "service not found"
        
        corrected = self.engine._fix_service_issues(command, error_message)
        assert corrected == "sudo systemctl daemon-reload && sudo systemctl restart nginx"
    
    def test_fix_network_issues(self):
        """Тест исправления сетевых проблем"""
        command = "curl https://example.com"
        error_message = "connection refused"
        
        with patch.object(self.engine, '_check_network_connectivity', return_value=True):
            corrected = self.engine._fix_network_issues(command, error_message)
            assert "ping -c 1 8.8.8.8" in corrected
            assert command in corrected
    
    def test_substitute_command(self):
        """Тест замены команд"""
        command = "service nginx start"
        error_message = "command not found"
        
        corrected = self.engine._substitute_command(command, error_message)
        assert corrected == "systemctl nginx start"
    
    def test_try_alternative_flags(self):
        """Тест использования альтернативных флагов"""
        command = "ls -l"
        error_message = "invalid option"
        
        corrected = self.engine._try_alternative_flags(command, error_message)
        assert corrected is not None
        assert "ls" in corrected
        assert "-la" in corrected or "-a" in corrected
    
    def test_check_network_connectivity_success(self):
        """Тест успешной проверки сетевого соединения"""
        with patch('socket.create_connection') as mock_connect:
            mock_connect.return_value = True
            result = self.engine._check_network_connectivity()
            assert result is True
    
    def test_check_network_connectivity_failure(self):
        """Тест неудачной проверки сетевого соединения"""
        with patch('socket.create_connection') as mock_connect:
            mock_connect.side_effect = OSError("Connection failed")
            result = self.engine._check_network_connectivity()
            assert result is False
    
    def test_correct_command_success(self):
        """Тест успешной автокоррекции команды"""
        command_result = CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stderr="permission denied",
            status=ExecutionStatus.FAILED,
            error_message="permission denied"
        )
        
        # Мокаем успешное выполнение исправленной команды
        self.mock_ssh.execute_command.return_value = ("", "", 0)
        
        result = self.engine.correct_command(command_result, self.context)
        
        assert result.success is True
        assert result.final_command == "sudo apt install nginx"
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.PERMISSION_FIX
    
    def test_correct_command_failure(self):
        """Тест неудачной автокоррекции команды"""
        command_result = CommandResult(
            command="unknown_command",
            success=False,
            exit_code=1,
            stderr="unknown error",
            status=ExecutionStatus.FAILED,
            error_message="unknown error"
        )
        
        # Мокаем неудачное выполнение команды
        self.mock_ssh.execute_command.return_value = ("", "still failing", 1)
        
        result = self.engine.correct_command(command_result, self.context)
        
        assert result.success is False
        assert result.final_command is None
        assert len(result.attempts) >= 1
    
    def test_correct_command_max_attempts(self):
        """Тест достижения максимального количества попыток"""
        command_result = CommandResult(
            command="failing_command",
            success=False,
            exit_code=1,
            stderr="persistent error",
            status=ExecutionStatus.FAILED,
            error_message="persistent error"
        )
        
        # Мокаем постоянные неудачи
        self.mock_ssh.execute_command.return_value = ("", "still failing", 1)
        
        result = self.engine.correct_command(command_result, self.context)
        
        assert result.success is False
        assert len(result.attempts) <= self.engine.max_attempts
    
    def test_get_correction_stats(self):
        """Тест получения статистики исправлений"""
        stats = self.engine.get_correction_stats()
        
        assert "max_attempts" in stats
        assert "timeout" in stats
        assert "alternative_flags_count" in stats
        assert "command_substitutions_count" in stats
        assert "syntax_patterns_count" in stats
        
        assert stats["max_attempts"] == 3
        assert stats["timeout"] == 5


class TestCorrectionAttempt:
    """Тесты для класса CorrectionAttempt"""
    
    def test_correction_attempt_creation(self):
        """Тест создания попытки исправления"""
        attempt = CorrectionAttempt(
            original_command="apt install nginx",
            corrected_command="sudo apt install nginx",
            strategy=CorrectionStrategy.PERMISSION_FIX,
            success=True,
            error_message=None,
            metadata={"test": "value"}
        )
        
        assert attempt.original_command == "apt install nginx"
        assert attempt.corrected_command == "sudo apt install nginx"
        assert attempt.strategy == CorrectionStrategy.PERMISSION_FIX
        assert attempt.success is True
        assert attempt.error_message is None
        assert attempt.metadata["test"] == "value"
    
    def test_correction_attempt_default_metadata(self):
        """Тест создания попытки исправления с метаданными по умолчанию"""
        attempt = CorrectionAttempt(
            original_command="test",
            corrected_command="test",
            strategy=CorrectionStrategy.SYNTAX_CHECK,
            success=False
        )
        
        assert attempt.metadata is not None
        assert isinstance(attempt.metadata, dict)


class TestAutocorrectionResult:
    """Тесты для класса AutocorrectionResult"""
    
    def test_autocorrection_result_creation(self):
        """Тест создания результата автокоррекции"""
        result = AutocorrectionResult(
            success=True,
            final_command="sudo apt install nginx",
            attempts=[],
            total_attempts=1,
            error_message=None
        )
        
        assert result.success is True
        assert result.final_command == "sudo apt install nginx"
        assert result.attempts == []
        assert result.total_attempts == 1
        assert result.error_message is None
    
    def test_autocorrection_result_default_attempts(self):
        """Тест создания результата автокоррекции с попытками по умолчанию"""
        result = AutocorrectionResult(success=False)
        
        assert result.attempts == []
        assert result.total_attempts == 0


class TestCorrectionStrategy:
    """Тесты для enum CorrectionStrategy"""
    
    def test_correction_strategy_values(self):
        """Тест значений стратегий исправления"""
        strategies = [
            CorrectionStrategy.SYNTAX_CHECK,
            CorrectionStrategy.ALTERNATIVE_FLAGS,
            CorrectionStrategy.NETWORK_CHECK,
            CorrectionStrategy.SERVICE_RESTART,
            CorrectionStrategy.PERMISSION_FIX,
            CorrectionStrategy.PACKAGE_UPDATE,
            CorrectionStrategy.PATH_CORRECTION,
            CorrectionStrategy.COMMAND_SUBSTITUTION
        ]
        
        for strategy in strategies:
            assert isinstance(strategy.value, str)
            assert len(strategy.value) > 0


if __name__ == "__main__":
    pytest.main([__file__])
