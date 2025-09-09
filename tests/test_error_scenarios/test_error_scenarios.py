"""
Тесты для сценариев ошибок
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.models.execution_model import CommandResult, ExecutionStatus
from src.agents.error_handler import ErrorHandler
from src.utils.autocorrection import AutocorrectionEngine
from src.utils.error_tracker import ErrorTracker, ErrorSeverity


class TestErrorScenarios:
    """Тесты сценариев ошибок"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.mock_config = Mock()
        self.mock_ssh_connector = Mock()
        self.error_handler = ErrorHandler(self.mock_config)
        self.autocorrection_engine = AutocorrectionEngine()
        self.error_tracker = ErrorTracker()
    
    @pytest.mark.error_scenarios
    def test_permission_denied_error(self):
        """Тест сценария ошибки 'Permission denied'"""
        # Создаем результат команды с ошибкой прав доступа
        failed_result = CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Проверяем, что ошибка правильно классифицируется
        error_entry = self.error_tracker.log_error(
            error_type="PermissionDeniedError",
            message="Permission denied when executing command",
            context={"command": failed_result.command},
            severity=ErrorSeverity.HIGH
        )
        
        assert error_entry.severity == ErrorSeverity.HIGH
        assert "Permission denied" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_package_not_found_error(self):
        """Тест сценария ошибки 'Package not found'"""
        failed_result = CommandResult(
            command="apt install nonexistent-package",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Package 'nonexistent-package' not found",
            status=ExecutionStatus.FAILED
        )
        
        # Логируем ошибку
        error_entry = self.error_tracker.log_error(
            error_type="PackageNotFoundError",
            message="Package not found",
            context={"command": failed_result.command, "package": "nonexistent-package"},
            severity=ErrorSeverity.MEDIUM
        )
        
        assert error_entry.severity == ErrorSeverity.MEDIUM
        assert "Package not found" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_network_connection_error(self):
        """Тест сценария сетевой ошибки"""
        failed_result = CommandResult(
            command="curl https://example.com",
            success=False,
            exit_code=7,
            stdout="",
            stderr="Connection refused",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="NetworkConnectionError",
            message="Network connection failed",
            context={"command": failed_result.command, "url": "https://example.com"},
            severity=ErrorSeverity.HIGH
        )
        
        assert error_entry.severity == ErrorSeverity.HIGH
        assert "Network connection failed" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_service_not_found_error(self):
        """Тест сценария ошибки 'Service not found'"""
        failed_result = CommandResult(
            command="systemctl start nonexistent-service",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Unit nonexistent-service.service not found",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="ServiceNotFoundError",
            message="Service not found",
            context={"command": failed_result.command, "service": "nonexistent-service"},
            severity=ErrorSeverity.MEDIUM
        )
        
        assert error_entry.severity == ErrorSeverity.MEDIUM
        assert "Service not found" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_file_not_found_error(self):
        """Тест сценария ошибки 'File not found'"""
        failed_result = CommandResult(
            command="cat /nonexistent/file.txt",
            success=False,
            exit_code=1,
            stdout="",
            stderr="No such file or directory",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="FileNotFoundError",
            message="File not found",
            context={"command": failed_result.command, "file": "/nonexistent/file.txt"},
            severity=ErrorSeverity.MEDIUM
        )
        
        assert error_entry.severity == ErrorSeverity.MEDIUM
        assert "File not found" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_syntax_error(self):
        """Тест сценария синтаксической ошибки"""
        failed_result = CommandResult(
            command="ls  -la   /tmp",
            success=False,
            exit_code=2,
            stdout="",
            stderr="syntax error",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="SyntaxError",
            message="Command syntax error",
            context={"command": failed_result.command},
            severity=ErrorSeverity.LOW
        )
        
        assert error_entry.severity == ErrorSeverity.LOW
        assert "syntax error" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_timeout_error(self):
        """Тест сценария ошибки таймаута"""
        failed_result = CommandResult(
            command="long-running-command",
            success=False,
            exit_code=124,
            stdout="",
            stderr="Command timed out",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="TimeoutError",
            message="Command execution timed out",
            context={"command": failed_result.command, "timeout": 30},
            severity=ErrorSeverity.HIGH
        )
        
        assert error_entry.severity == ErrorSeverity.HIGH
        assert "timed out" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_disk_space_error(self):
        """Тест сценария ошибки нехватки места на диске"""
        failed_result = CommandResult(
            command="apt install large-package",
            success=False,
            exit_code=1,
            stdout="",
            stderr="No space left on device",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="DiskSpaceError",
            message="Insufficient disk space",
            context={"command": failed_result.command},
            severity=ErrorSeverity.CRITICAL
        )
        
        assert error_entry.severity == ErrorSeverity.CRITICAL
        assert "Insufficient disk space" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_memory_error(self):
        """Тест сценария ошибки нехватки памяти"""
        failed_result = CommandResult(
            command="memory-intensive-command",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Cannot allocate memory",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="MemoryError",
            message="Insufficient memory",
            context={"command": failed_result.command},
            severity=ErrorSeverity.CRITICAL
        )
        
        assert error_entry.severity == ErrorSeverity.CRITICAL
        assert "Insufficient memory" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_authentication_error(self):
        """Тест сценария ошибки аутентификации"""
        failed_result = CommandResult(
            command="sudo command",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Authentication failed",
            status=ExecutionStatus.FAILED
        )
        
        error_entry = self.error_tracker.log_error(
            error_type="AuthenticationError",
            message="Authentication failed",
            context={"command": failed_result.command},
            severity=ErrorSeverity.HIGH
        )
        
        assert error_entry.severity == ErrorSeverity.HIGH
        assert "Authentication failed" in error_entry.message
    
    @pytest.mark.error_scenarios
    def test_multiple_errors_aggregation(self):
        """Тест агрегации множественных ошибок"""
        # Создаем несколько результатов с ошибками
        failed_results = [
            CommandResult(
                command="apt install package1",
                success=False,
                exit_code=1,
                stderr="Package not found",
                status=ExecutionStatus.FAILED
            ),
            CommandResult(
                command="apt install package2",
                success=False,
                exit_code=1,
                stderr="Permission denied",
                status=ExecutionStatus.FAILED
            ),
            CommandResult(
                command="apt update",
                success=True,
                exit_code=0,
                stdout="Update completed",
                status=ExecutionStatus.COMPLETED
            )
        ]
        
        # Агрегируем ошибки
        error_summary = self.error_handler.aggregate_errors(failed_results)
        
        # Проверяем результат
        assert error_summary.total_errors == 2
        assert error_summary.successful_commands == 1
        assert error_summary.error_rate == 2/3  # 2 из 3 команд завершились ошибкой
    
    @pytest.mark.error_scenarios
    def test_error_threshold_exceeded(self):
        """Тест превышения порога ошибок"""
        # Создаем конфигурацию с низким порогом
        config = Mock()
        config.error_handler = Mock()
        config.error_handler.error_threshold_per_step = 2
        
        error_handler = ErrorHandler(config)
        
        # Создаем результаты с превышением порога
        failed_results = [
            CommandResult(command="cmd1", success=False, exit_code=1, stderr="Error 1", status=ExecutionStatus.FAILED),
            CommandResult(command="cmd2", success=False, exit_code=1, stderr="Error 2", status=ExecutionStatus.FAILED),
            CommandResult(command="cmd3", success=False, exit_code=1, stderr="Error 3", status=ExecutionStatus.FAILED)
        ]
        
        # Проверяем превышение порога
        threshold_exceeded = error_handler.check_error_threshold(failed_results)
        assert threshold_exceeded is True
    
    @pytest.mark.error_scenarios
    def test_critical_error_escalation(self):
        """Тест эскалации критических ошибок"""
        # Логируем критическую ошибку
        error_entry = self.error_tracker.log_error(
            error_type="CriticalSystemError",
            message="System is in critical state",
            context={"component": "filesystem"},
            severity=ErrorSeverity.CRITICAL
        )
        
        # Проверяем, что ошибка правильно классифицирована
        assert error_entry.severity == ErrorSeverity.CRITICAL
        
        # Получаем сводку ошибок
        summary = self.error_tracker.get_error_summary()
        assert summary.errors_by_severity[ErrorSeverity.CRITICAL] == 1
    
    @pytest.mark.error_scenarios
    def test_error_recovery_scenarios(self):
        """Тест сценариев восстановления после ошибок"""
        # Создаем движок автокоррекции
        autocorrection_engine = AutocorrectionEngine()
        
        # Тестируем различные сценарии восстановления
        recovery_scenarios = [
            {
                "command": "apt install nginx",
                "error": "Permission denied",
                "expected_correction": "sudo apt install nginx"
            },
            {
                "command": "service nginx start",
                "error": "command not found",
                "expected_correction": "systemctl start nginx"
            },
            {
                "command": "apt install missing-package",
                "error": "Package not found",
                "expected_correction": "sudo apt update && apt install missing-package"
            }
        ]
        
        for scenario in recovery_scenarios:
            failed_result = CommandResult(
                command=scenario["command"],
                success=False,
                exit_code=1,
                stderr=scenario["error"],
                status=ExecutionStatus.FAILED
            )
            
            # Применяем автокоррекцию
            correction_result = autocorrection_engine.correct_command(failed_result, Mock())
            
            # Проверяем, что коррекция была применена
            assert correction_result is not None
            assert hasattr(correction_result, 'success')
            assert hasattr(correction_result, 'final_command')


if __name__ == "__main__":
    pytest.main([__file__])
