"""
Тесты для Autocorrection
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.utils.autocorrection import (
    CorrectionStrategy, CorrectionAttempt, AutocorrectionResult,
    AutocorrectionEngine
)
from src.models.command_result import CommandResult, ExecutionStatus
from src.models.execution_context import ExecutionContext


class TestCorrectionStrategy:
    """Тесты для CorrectionStrategy"""
    
    def test_correction_strategy_values(self):
        """Тест значений стратегий исправления"""
        assert CorrectionStrategy.SYNTAX_CHECK.value == "syntax_check"
        assert CorrectionStrategy.ALTERNATIVE_FLAGS.value == "alternative_flags"
        assert CorrectionStrategy.NETWORK_CHECK.value == "network_check"
        assert CorrectionStrategy.SERVICE_RESTART.value == "service_restart"
        assert CorrectionStrategy.PERMISSION_FIX.value == "permission_fix"
        assert CorrectionStrategy.PACKAGE_UPDATE.value == "package_update"
        assert CorrectionStrategy.PATH_CORRECTION.value == "path_correction"
        assert CorrectionStrategy.COMMAND_SUBSTITUTION.value == "command_substitution"


class TestCorrectionAttempt:
    """Тесты для CorrectionAttempt"""
    
    def test_correction_attempt_creation(self):
        """Тест создания попытки исправления"""
        attempt = CorrectionAttempt(
            original_command="ls -l",
            corrected_command="ls -la",
            strategy=CorrectionStrategy.ALTERNATIVE_FLAGS,
            success=True,
            error_message=None,
            metadata={"test": "value"}
        )
        
        assert attempt.original_command == "ls -l"
        assert attempt.corrected_command == "ls -la"
        assert attempt.strategy == CorrectionStrategy.ALTERNATIVE_FLAGS
        assert attempt.success is True
        assert attempt.error_message is None
        assert attempt.metadata == {"test": "value"}
    
    def test_correction_attempt_default_metadata(self):
        """Тест создания попытки исправления с метаданными по умолчанию"""
        attempt = CorrectionAttempt(
            original_command="test",
            corrected_command="test",
            strategy=CorrectionStrategy.SYNTAX_CHECK,
            success=False
        )
        
        assert attempt.metadata == {}


class TestAutocorrectionResult:
    """Тесты для AutocorrectionResult"""
    
    def test_autocorrection_result_creation(self):
        """Тест создания результата автокоррекции"""
        result = AutocorrectionResult(
            success=True,
            final_command="corrected_command",
            total_attempts=2,
            error_message=None
        )
        
        assert result.success is True
        assert result.final_command == "corrected_command"
        assert result.total_attempts == 2
        assert result.error_message is None
        assert result.attempts == []
    
    def test_autocorrection_result_with_attempts(self):
        """Тест создания результата автокоррекции с попытками"""
        attempts = [
            CorrectionAttempt("cmd1", "cmd2", CorrectionStrategy.SYNTAX_CHECK, False),
            CorrectionAttempt("cmd2", "cmd3", CorrectionStrategy.ALTERNATIVE_FLAGS, True)
        ]
        
        result = AutocorrectionResult(
            success=True,
            final_command="cmd3",
            attempts=attempts,
            total_attempts=2
        )
        
        assert result.success is True
        assert result.final_command == "cmd3"
        assert len(result.attempts) == 2
        assert result.total_attempts == 2


class TestAutocorrectionEngine:
    """Тесты для AutocorrectionEngine"""
    
    @pytest.fixture
    def engine(self):
        """Фикстура движка автокоррекции"""
        return AutocorrectionEngine(max_attempts=3, timeout=30)
    
    @pytest.fixture
    def mock_context(self):
        """Фикстура мок контекста"""
        context = Mock(spec=ExecutionContext)
        context.ssh_connection = Mock()
        return context
    
    def test_initialization(self, engine):
        """Тест инициализации движка"""
        assert engine.max_attempts == 3
        assert engine.timeout == 30
        assert len(engine.alternative_flags) > 0
        assert len(engine.command_substitutions) > 0
        assert len(engine.syntax_patterns) > 0
    
    def test_determine_correction_strategy_permission_denied(self, engine):
        """Тест определения стратегии для ошибки прав доступа"""
        command = "apt install nginx"
        error_message = "permission denied"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.PERMISSION_FIX
    
    def test_determine_correction_strategy_command_not_found(self, engine):
        """Тест определения стратегии для команды не найдена"""
        command = "service nginx start"
        error_message = "command not found"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.COMMAND_SUBSTITUTION
    
    def test_determine_correction_strategy_package_not_found(self, engine):
        """Тест определения стратегии для пакет не найден"""
        command = "apt install nonexistent-package"
        error_message = "package not found"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.PACKAGE_UPDATE
    
    def test_determine_correction_strategy_service_not_found(self, engine):
        """Тест определения стратегии для сервис не найден"""
        command = "systemctl start nginx"
        error_message = "service not found"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.SERVICE_RESTART
    
    def test_determine_correction_strategy_connection_refused(self, engine):
        """Тест определения стратегии для отказа в соединении"""
        command = "curl http://example.com"
        error_message = "connection refused"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.NETWORK_CHECK
    
    def test_determine_correction_strategy_file_not_found(self, engine):
        """Тест определения стратегии для файл не найден"""
        command = "cat /nonexistent/file"
        error_message = "no such file or directory"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.PATH_CORRECTION
    
    def test_determine_correction_strategy_syntax_error(self, engine):
        """Тест определения стратегии для синтаксической ошибки"""
        command = "ls --invalid-flag"
        error_message = "syntax error"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.ALTERNATIVE_FLAGS
    
    def test_determine_correction_strategy_network_error(self, engine):
        """Тест определения стратегии для сетевой ошибки"""
        command = "ping google.com"
        error_message = "network is unreachable"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.NETWORK_CHECK
    
    def test_determine_correction_strategy_systemctl_failed(self, engine):
        """Тест определения стратегии для systemctl failed"""
        command = "systemctl status nginx"
        error_message = "failed to get unit"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.SERVICE_RESTART
    
    def test_determine_correction_strategy_network_command(self, engine):
        """Тест определения стратегии для сетевой команды"""
        command = "curl http://example.com"
        error_message = "network error"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.NETWORK_CHECK
    
    def test_determine_correction_strategy_apt_not_found(self, engine):
        """Тест определения стратегии для apt not found"""
        command = "apt install package"
        error_message = "not found"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.PACKAGE_UPDATE
    
    def test_determine_correction_strategy_unknown_error(self, engine):
        """Тест определения стратегии для неизвестной ошибки"""
        command = "unknown_command"
        error_message = "unknown error"
        
        strategy = engine._determine_correction_strategy(command, error_message)
        assert strategy == CorrectionStrategy.SYNTAX_CHECK
    
    def test_fix_syntax_errors_whitespace(self, engine):
        """Тест исправления синтаксических ошибок - пробелы"""
        command = "ls  -la   /home"
        error_message = "syntax error"
        
        result = engine._fix_syntax_errors(command, error_message)
        assert result == "ls -la /home"
    
    def test_fix_syntax_errors_quotes(self, engine):
        """Тест исправления синтаксических ошибок - кавычки"""
        command = 'echo "hello world"'
        error_message = "syntax error"
        
        result = engine._fix_syntax_errors(command, error_message)
        assert result == 'echo "hello world"'
    
    def test_fix_syntax_errors_backslashes(self, engine):
        """Тест исправления синтаксических ошибок - слеши"""
        command = "cd C:\\Users\\test"
        error_message = "syntax error"
        
        result = engine._fix_syntax_errors(command, error_message)
        assert result == "cd C:/Users/test"
    
    def test_fix_syntax_errors_no_changes(self, engine):
        """Тест исправления синтаксических ошибок - без изменений"""
        command = "ls -la"
        error_message = "syntax error"
        
        result = engine._fix_syntax_errors(command, error_message)
        assert result is None
    
    def test_try_alternative_flags_ls(self, engine):
        """Тест попытки альтернативных флагов для ls"""
        command = "ls"
        error_message = "invalid option"
        
        result = engine._try_alternative_flags(command, error_message)
        assert result is not None
        assert result.startswith("ls ")
        assert any(flag in result for flag in ["-la", "-l", "-a", "-lh"])
    
    def test_try_alternative_flags_unknown_command(self, engine):
        """Тест попытки альтернативных флагов для неизвестной команды"""
        command = "unknown_command"
        error_message = "invalid option"
        
        result = engine._try_alternative_flags(command, error_message)
        assert result is None
    
    def test_try_alternative_flags_short_command(self, engine):
        """Тест попытки альтернативных флагов для короткой команды"""
        command = "ls"
        error_message = "invalid option"
        
        result = engine._try_alternative_flags(command, error_message)
        assert result is not None
    
    @patch('socket.create_connection')
    def test_fix_network_issues_connectivity_ok(self, mock_socket, engine):
        """Тест исправления сетевых проблем при доступном соединении"""
        mock_socket.return_value = Mock()
        
        command = "curl http://example.com"
        error_message = "connection refused"
        
        result = engine._fix_network_issues(command, error_message)
        assert result == "ping -c 1 8.8.8.8 > /dev/null 2>&1 && curl http://example.com"
    
    @patch('socket.create_connection')
    def test_fix_network_issues_connectivity_failed(self, mock_socket, engine):
        """Тест исправления сетевых проблем при недоступном соединении"""
        mock_socket.side_effect = OSError("Connection failed")
        
        command = "curl http://example.com"
        error_message = "connection refused"
        
        result = engine._fix_network_issues(command, error_message)
        assert result is None
    
    def test_fix_network_issues_non_network_command(self, engine):
        """Тест исправления сетевых проблем для не-сетевой команды"""
        command = "ls -la"
        error_message = "connection refused"
        
        result = engine._fix_network_issues(command, error_message)
        assert result is None
    
    def test_fix_service_issues_systemctl_not_found(self, engine):
        """Тест исправления проблем с сервисами - сервис не найден"""
        command = "systemctl start nginx"
        error_message = "service not found"
        
        result = engine._fix_service_issues(command, error_message)
        assert result == "sudo systemctl daemon-reload && sudo systemctl restart nginx"
    
    def test_fix_service_issues_systemctl_failed(self, engine):
        """Тест исправления проблем с сервисами - сервис failed"""
        command = "systemctl status nginx"
        error_message = "failed to get unit"
        
        result = engine._fix_service_issues(command, error_message)
        assert result == "sudo systemctl daemon-reload && sudo systemctl restart nginx"
    
    def test_fix_service_issues_non_systemctl(self, engine):
        """Тест исправления проблем с сервисами - не systemctl"""
        command = "ls -la"
        error_message = "service not found"
        
        result = engine._fix_service_issues(command, error_message)
        assert result is None
    
    def test_fix_permission_issues_apt(self, engine):
        """Тест исправления проблем с правами - apt"""
        command = "apt install nginx"
        error_message = "permission denied"
        
        result = engine._fix_permission_issues(command, error_message)
        assert result == "sudo apt install nginx"
    
    def test_fix_permission_issues_systemctl(self, engine):
        """Тест исправления проблем с правами - systemctl"""
        command = "systemctl start nginx"
        error_message = "permission denied"
        
        result = engine._fix_permission_issues(command, error_message)
        assert result == "sudo systemctl start nginx"
    
    def test_fix_permission_issues_already_sudo(self, engine):
        """Тест исправления проблем с правами - уже sudo"""
        command = "sudo apt install nginx"
        error_message = "permission denied"
        
        result = engine._fix_permission_issues(command, error_message)
        assert result is None
    
    def test_fix_permission_issues_non_sudo_command(self, engine):
        """Тест исправления проблем с правами - не sudo команда"""
        command = "echo hello"
        error_message = "permission denied"
        
        result = engine._fix_permission_issues(command, error_message)
        assert result is None
    
    def test_fix_package_issues_apt_install(self, engine):
        """Тест исправления проблем с пакетами - apt install"""
        command = "apt install nginx"
        error_message = "package not found"
        
        result = engine._fix_package_issues(command, error_message)
        assert result == "sudo apt update && apt install nginx"
    
    def test_fix_package_issues_non_apt(self, engine):
        """Тест исправления проблем с пакетами - не apt"""
        command = "yum install nginx"
        error_message = "package not found"
        
        result = engine._fix_package_issues(command, error_message)
        assert result is None
    
    def test_fix_path_issues_mkdir(self, engine):
        """Тест исправления проблем с путями - mkdir"""
        command = "mkdir /new/directory"
        error_message = "permission denied"
        
        result = engine._fix_path_issues(command, error_message)
        assert result == "sudo mkdir /new/directory"
    
    def test_fix_path_issues_relative_path(self, engine):
        """Тест исправления проблем с путями - относительный путь"""
        command = "cat ./file.txt"
        error_message = "no such file or directory"
        
        result = engine._fix_path_issues(command, error_message)
        assert result == "cat /file.txt"
    
    def test_fix_path_issues_no_changes(self, engine):
        """Тест исправления проблем с путями - без изменений"""
        command = "ls /home"
        error_message = "no such file or directory"
        
        result = engine._fix_path_issues(command, error_message)
        assert result is None
    
    def test_substitute_command_service(self, engine):
        """Тест замены команды - service"""
        command = "service nginx start"
        error_message = "command not found"
        
        result = engine._substitute_command(command, error_message)
        assert result == "systemctl nginx start"
    
    def test_substitute_command_ifconfig(self, engine):
        """Тест замены команды - ifconfig"""
        command = "ifconfig eth0"
        error_message = "command not found"
        
        result = engine._substitute_command(command, error_message)
        assert result == "ip eth0"
    
    def test_substitute_command_no_match(self, engine):
        """Тест замены команды - нет совпадений"""
        command = "unknown_command"
        error_message = "command not found"
        
        result = engine._substitute_command(command, error_message)
        assert result is None
    
    @patch('socket.create_connection')
    def test_check_network_connectivity_success(self, mock_socket, engine):
        """Тест проверки сетевого соединения - успех"""
        mock_socket.return_value = Mock()
        
        result = engine._check_network_connectivity()
        assert result is True
    
    @patch('socket.create_connection')
    def test_check_network_connectivity_failure(self, mock_socket, engine):
        """Тест проверки сетевого соединения - неудача"""
        mock_socket.side_effect = OSError("Connection failed")
        
        result = engine._check_network_connectivity()
        assert result is False
    
    def test_test_corrected_command_success(self, engine, mock_context):
        """Тест тестирования исправленной команды - успех"""
        mock_context.ssh_connection.execute_command.return_value = ("output", "", 0)
        
        result = engine._test_corrected_command("ls -la", mock_context)
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.status == ExecutionStatus.COMPLETED
    
    def test_test_corrected_command_failure(self, engine, mock_context):
        """Тест тестирования исправленной команды - неудача"""
        mock_context.ssh_connection.execute_command.return_value = ("", "error", 1)
        
        result = engine._test_corrected_command("invalid_command", mock_context)
        
        assert result.success is False
        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == "error"
        assert result.status == ExecutionStatus.FAILED
        assert result.error_message == "error"
    
    def test_test_corrected_command_exception(self, engine, mock_context):
        """Тест тестирования исправленной команды - исключение"""
        mock_context.ssh_connection.execute_command.side_effect = Exception("Connection failed")
        
        result = engine._test_corrected_command("test_command", mock_context)
        
        assert result.success is False
        assert result.status == ExecutionStatus.FAILED
        assert result.error_message == "Connection failed"
    
    def test_correct_command_success(self, engine, mock_context):
        """Тест исправления команды - успех"""
        # Создаем мок результата команды с ошибкой
        command_result = CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stderr="permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем тестирование исправленной команды
        with patch.object(engine, '_test_corrected_command') as mock_test:
            mock_test.return_value = CommandResult(
                command="sudo apt install nginx",
                success=True,
                exit_code=0,
                status=ExecutionStatus.COMPLETED
            )
            
            result = engine.correct_command(command_result, mock_context)
            
            assert result.success is True
            assert result.final_command == "sudo apt install nginx"
            assert result.total_attempts == 1
            assert len(result.attempts) == 1
            assert result.attempts[0].strategy == CorrectionStrategy.PERMISSION_FIX
    
    def test_correct_command_failure(self, engine, mock_context):
        """Тест исправления команды - неудача"""
        # Создаем мок результата команды с ошибкой
        command_result = CommandResult(
            command="unknown_command",
            success=False,
            exit_code=1,
            stderr="command not found",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем тестирование исправленной команды - всегда неудача
        with patch.object(engine, '_test_corrected_command') as mock_test:
            mock_test.return_value = CommandResult(
                command="unknown_command",
                success=False,
                exit_code=1,
                stderr="command not found",
                status=ExecutionStatus.FAILED
            )
            
            result = engine.correct_command(command_result, mock_context)
            
            assert result.success is False
            assert result.final_command is None
            assert result.total_attempts == 3  # max_attempts
            assert len(result.attempts) == 3
            assert "Все попытки исправления исчерпаны" in result.error_message
    
    def test_correct_command_no_strategy(self, engine, mock_context):
        """Тест исправления команды - нет стратегии"""
        # Создаем мок результата команды с неизвестной ошибкой
        command_result = CommandResult(
            command="test_command",
            success=False,
            exit_code=1,
            stderr="unknown error",
            status=ExecutionStatus.FAILED
        )
        
        # Мокаем определение стратегии - возвращаем None
        with patch.object(engine, '_determine_correction_strategy', return_value=None):
            result = engine.correct_command(command_result, mock_context)
            
            assert result.success is False
            assert result.total_attempts == 0
            assert len(result.attempts) == 0
    
    def test_get_correction_stats(self, engine):
        """Тест получения статистики исправлений"""
        stats = engine.get_correction_stats()
        
        assert stats["max_attempts"] == 3
        assert stats["timeout"] == 30
        assert stats["alternative_flags_count"] > 0
        assert stats["command_substitutions_count"] > 0
        assert stats["syntax_patterns_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__])