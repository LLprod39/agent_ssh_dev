"""
Тесты для сценариев ошибок
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any

from src.models.command_result import CommandResult, ExecutionStatus
from src.models.execution_context import ExecutionContext
from src.agents.error_handler import ErrorHandler
from src.agents.escalation_system import EscalationSystem, EscalationType
from src.utils.autocorrection import AutocorrectionEngine, CorrectionStrategy


class TestErrorScenarios:
    """Тесты для различных сценариев ошибок"""
    
    @pytest.fixture
    def mock_context(self):
        """Мок контекста выполнения"""
        context = Mock(spec=ExecutionContext)
        context.ssh_connection = Mock()
        context.subtask = Mock()
        context.server_info = {"os": "ubuntu", "version": "20.04"}
        context.environment = {"production": True}
        return context
    
    @pytest.fixture
    def error_handler(self):
        """Обработчик ошибок"""
        return ErrorHandler({
            "error_threshold_per_step": 3,
            "send_to_planner_after_threshold": True,
            "human_escalation_threshold": 5
        })
    
    @pytest.fixture
    def escalation_system(self):
        """Система эскалации"""
        return EscalationSystem({
            "escalation_enabled": True,
            "max_escalation_levels": 3
        })
    
    @pytest.fixture
    def autocorrection_engine(self):
        """Движок автокоррекции"""
        return AutocorrectionEngine(max_attempts=3, timeout=30)
    
    def test_permission_denied_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки 'permission denied'"""
        # Создаем результат команды с ошибкой прав доступа
        command_result = CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stderr="permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия исправления прав
        assert result.success is True
        assert result.final_command == "sudo apt install nginx"
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.PERMISSION_FIX
    
    def test_command_not_found_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки 'command not found'"""
        # Создаем результат команды с ошибкой команда не найдена
        command_result = CommandResult(
            command="service nginx start",
            success=False,
            exit_code=127,
            stderr="command not found",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия замены команды
        assert result.success is True
        assert "systemctl" in result.final_command
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.COMMAND_SUBSTITUTION
    
    def test_package_not_found_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки 'package not found'"""
        # Создаем результат команды с ошибкой пакет не найден
        command_result = CommandResult(
            command="apt install nonexistent-package",
            success=False,
            exit_code=1,
            stderr="package not found",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия обновления пакетов
        assert result.success is True
        assert "apt update" in result.final_command
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.PACKAGE_UPDATE
    
    def test_service_not_found_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки 'service not found'"""
        # Создаем результат команды с ошибкой сервис не найден
        command_result = CommandResult(
            command="systemctl start nginx",
            success=False,
            exit_code=1,
            stderr="service not found",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия перезапуска сервиса
        assert result.success is True
        assert "daemon-reload" in result.final_command
        assert "restart" in result.final_command
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.SERVICE_RESTART
    
    def test_network_connection_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки сетевого соединения"""
        # Создаем результат команды с ошибкой соединения
        command_result = CommandResult(
            command="curl http://example.com",
            success=False,
            exit_code=7,
            stderr="connection refused",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем проверку сетевого соединения
        with patch.object(autocorrection_engine, '_check_network_connectivity', return_value=True):
            result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия проверки сети
        assert result.success is True
        assert "ping" in result.final_command
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.NETWORK_CHECK
    
    def test_syntax_error_handling(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки синтаксических ошибок"""
        # Создаем результат команды с синтаксической ошибкой
        command_result = CommandResult(
            command="ls  --invalid-flag",
            success=False,
            exit_code=2,
            stderr="syntax error",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия альтернативных флагов
        assert result.success is True
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.ALTERNATIVE_FLAGS
    
    def test_file_not_found_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки 'file not found'"""
        # Создаем результат команды с ошибкой файл не найден
        command_result = CommandResult(
            command="cat /nonexistent/file",
            success=False,
            exit_code=1,
            stderr="no such file or directory",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что была применена стратегия исправления путей
        assert result.success is True
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == CorrectionStrategy.PATH_CORRECTION
    
    def test_multiple_error_attempts(self, mock_context, error_handler, autocorrection_engine):
        """Тест множественных попыток исправления ошибок"""
        # Создаем результат команды с ошибкой
        command_result = CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stderr="permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем тестирование исправленной команды - первые попытки неудачны
        with patch.object(autocorrection_engine, '_test_corrected_command') as mock_test:
            mock_test.side_effect = [
                CommandResult("sudo apt install nginx", False, 1, "", "still error", ExecutionStatus.FAILED),
                CommandResult("sudo apt update && apt install nginx", False, 1, "", "still error", ExecutionStatus.FAILED),
                CommandResult("sudo apt update && sudo apt install nginx", True, 0, "success", "", ExecutionStatus.COMPLETED)
            ]
            
            result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что было несколько попыток
        assert result.success is True
        assert result.total_attempts == 3
        assert len(result.attempts) == 3
    
    def test_error_escalation_threshold(self, mock_context, error_handler, escalation_system):
        """Тест эскалации ошибок при превышении порога"""
        # Создаем несколько ошибок
        errors = [
            CommandResult("cmd1", False, 1, "", "error1", ExecutionStatus.FAILED),
            CommandResult("cmd2", False, 1, "", "error2", ExecutionStatus.FAILED),
            CommandResult("cmd3", False, 1, "", "error3", ExecutionStatus.FAILED),
            CommandResult("cmd4", False, 1, "", "error4", ExecutionStatus.FAILED)
        ]
        
        # Обрабатываем ошибки
        for error in errors:
            result = error_handler.handle_error(error, mock_context, {"step_id": "step_1"})
            
            if result.should_escalate:
                # Создаем запрос на эскалацию
                escalation_request = escalation_system.create_escalation_request(
                    escalation_type=EscalationType.HUMAN_ESCALATION,
                    step_id="step_1",
                    task_id="task_1",
                    error_count=len(errors),
                    reason="Превышен порог ошибок",
                    context={"step_title": "Test Step"},
                    error_details={"recent_errors": [error.to_dict() for error in errors]}
                )
                
                # Обрабатываем эскалацию
                escalation_result = escalation_system.handle_escalation(escalation_request)
                
                assert escalation_result.success is True
                assert escalation_result.escalation_id is not None
                break
    
    def test_critical_error_escalation(self, mock_context, error_handler, escalation_system):
        """Тест эскалации критических ошибок"""
        # Создаем критическую ошибку
        critical_error = CommandResult(
            command="rm -rf /",
            success=False,
            exit_code=1,
            stderr="permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Обрабатываем ошибку
        result = error_handler.handle_error(critical_error, mock_context, {"step_id": "step_1"})
        
        # Проверяем что требуется эскалация
        assert result.should_escalate is True
        assert result.escalation_type == EscalationType.EMERGENCY_STOP
    
    def test_network_timeout_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки таймаута сети"""
        # Создаем результат команды с таймаутом
        command_result = CommandResult(
            command="curl http://slow-server.com",
            success=False,
            exit_code=28,
            stderr="timeout",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем проверку сетевого соединения
        with patch.object(autocorrection_engine, '_check_network_connectivity', return_value=False):
            result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что автокоррекция не удалась из-за проблем с сетью
        assert result.success is False
        assert result.total_attempts == 0
    
    def test_disk_space_error(self, mock_context, error_handler, autocorrection_engine):
        """Тест обработки ошибки нехватки места на диске"""
        # Создаем результат команды с ошибкой места на диске
        command_result = CommandResult(
            command="apt install large-package",
            success=False,
            exit_code=1,
            stderr="no space left on device",
            status=ExecutionStatus.FAILED
        )
        
        # Тестируем автокоррекцию
        result = autocorrection_engine.correct_command(command_result, mock_context)
        
        # Проверяем что автокоррекция не смогла исправить эту ошибку
        assert result.success is False
        assert result.total_attempts == 0
    
    def test_concurrent_error_handling(self, mock_context, error_handler):
        """Тест обработки ошибок в конкурентном режиме"""
        import asyncio
        
        async def simulate_concurrent_errors():
            # Создаем несколько задач с ошибками
            tasks = []
            for i in range(5):
                error = CommandResult(f"cmd{i}", False, 1, "", f"error{i}", ExecutionStatus.FAILED)
                task = asyncio.create_task(
                    error_handler.handle_error_async(error, mock_context, {"step_id": f"step_{i}"})
                )
                tasks.append(task)
            
            # Ждем завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Проверяем что все задачи завершились
            assert len(results) == 5
            for result in results:
                assert not isinstance(result, Exception)
        
        # Запускаем тест
        asyncio.run(simulate_concurrent_errors())
    
    def test_error_recovery_workflow(self, mock_context, error_handler, autocorrection_engine):
        """Тест рабочего процесса восстановления после ошибок"""
        # Создаем последовательность ошибок и исправлений
        errors = [
            CommandResult("apt install nginx", False, 1, "", "permission denied", ExecutionStatus.FAILED),
            CommandResult("sudo apt install nginx", False, 1, "", "package not found", ExecutionStatus.FAILED),
            CommandResult("sudo apt update && apt install nginx", True, 0, "success", "", ExecutionStatus.COMPLETED)
        ]
        
        # Обрабатываем каждую ошибку
        for i, error in enumerate(errors):
            if i < len(errors) - 1:  # Не последняя ошибка
                result = error_handler.handle_error(error, mock_context, {"step_id": "step_1"})
                
                if result.should_retry and result.corrected_command:
                    # Применяем исправление
                    corrected_result = autocorrection_engine.correct_command(error, mock_context)
                    assert corrected_result.success is True
            else:  # Последняя ошибка - успешная
                result = error_handler.handle_error(error, mock_context, {"step_id": "step_1"})
                assert result.should_retry is False
                assert result.success is True
    
    def test_error_logging_and_monitoring(self, mock_context, error_handler):
        """Тест логирования и мониторинга ошибок"""
        # Создаем ошибку
        error = CommandResult(
            command="test command",
            success=False,
            exit_code=1,
            stderr="test error",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем логгер
        with patch.object(error_handler.logger, 'error') as mock_logger:
            result = error_handler.handle_error(error, mock_context, {"step_id": "step_1"})
            
            # Проверяем что ошибка была залогирована
            mock_logger.assert_called()
            
            # Проверяем что статистика обновилась
            stats = error_handler.get_error_stats()
            assert stats["total_errors"] > 0
            assert stats["errors_by_type"]["command_failed"] > 0


if __name__ == "__main__":
    pytest.main([__file__])
