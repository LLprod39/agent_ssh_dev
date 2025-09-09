"""
Тесты для Logger
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.utils.logger import (
    LoggerSetup, StructuredLogger, MetricsLogger,
    setup_logging, get_structured_logger, get_metrics_logger
)


class TestLoggerSetup:
    """Тесты для LoggerSetup"""
    
    def test_initialization_default_config(self):
        """Тест инициализации с конфигурацией по умолчанию"""
        logger_setup = LoggerSetup()
        
        assert logger_setup.config['level'] == 'INFO'
        assert logger_setup.config['log_file'] == 'logs/agent.log'
        assert logger_setup.config['error_file'] == 'logs/errors.log'
        assert logger_setup.config['max_file_size'] == '10 MB'
        assert logger_setup.config['retention_days'] == 7
        assert logger_setup.config['compression'] is True
    
    def test_initialization_custom_config(self):
        """Тест инициализации с пользовательской конфигурацией"""
        custom_config = {
            'level': 'DEBUG',
            'log_file': 'custom/agent.log',
            'error_file': 'custom/errors.log',
            'max_file_size': '5 MB',
            'retention_days': 14,
            'compression': False
        }
        
        logger_setup = LoggerSetup(custom_config)
        
        assert logger_setup.config == custom_config
    
    def test_get_default_config(self):
        """Тест получения конфигурации по умолчанию"""
        logger_setup = LoggerSetup()
        default_config = logger_setup._get_default_config()
        
        assert default_config['level'] == 'INFO'
        assert default_config['log_file'] == 'logs/agent.log'
        assert default_config['error_file'] == 'logs/errors.log'
        assert default_config['max_file_size'] == '10 MB'
        assert default_config['retention_days'] == 7
        assert default_config['compression'] is True
    
    @patch('src.utils.logger.logger')
    def test_setup_logging(self, mock_logger):
        """Тест настройки логирования"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                'level': 'INFO',
                'log_file': f'{temp_dir}/agent.log',
                'error_file': f'{temp_dir}/errors.log',
                'max_file_size': '1 MB',
                'retention_days': 7,
                'compression': False
            }
            
            logger_setup = LoggerSetup(config)
            
            # Проверяем что logger.remove был вызван
            mock_logger.remove.assert_called_once()
            
            # Проверяем что add был вызван несколько раз (console, file, error)
            assert mock_logger.add.call_count >= 3
    
    def test_ensure_log_directories(self):
        """Тест создания директорий для логов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = {
                'log_file': f'{temp_dir}/subdir/agent.log',
                'error_file': f'{temp_dir}/another/errors.log'
            }
            
            logger_setup = LoggerSetup(config)
            logger_setup._ensure_log_directories()
            
            # Проверяем что директории созданы
            assert Path(f'{temp_dir}/subdir').exists()
            assert Path(f'{temp_dir}/another').exists()
    
    def test_console_filter_debug_disabled(self):
        """Тест фильтра консоли - DEBUG отключен"""
        config = {'level': 'INFO'}
        logger_setup = LoggerSetup(config)
        
        # Создаем мок записи DEBUG уровня
        debug_record = Mock()
        debug_record["level"].name = "DEBUG"
        
        result = logger_setup._console_filter(debug_record)
        assert result is False
    
    def test_console_filter_debug_enabled(self):
        """Тест фильтра консоли - DEBUG включен"""
        config = {'level': 'DEBUG'}
        logger_setup = LoggerSetup(config)
        
        # Создаем мок записи DEBUG уровня
        debug_record = Mock()
        debug_record["level"].name = "DEBUG"
        
        result = logger_setup._console_filter(debug_record)
        assert result is True
    
    def test_console_filter_info_level(self):
        """Тест фильтра консоли - INFO уровень"""
        config = {'level': 'INFO'}
        logger_setup = LoggerSetup(config)
        
        # Создаем мок записи INFO уровня
        info_record = Mock()
        info_record["level"].name = "INFO"
        
        result = logger_setup._console_filter(info_record)
        assert result is True
    
    @patch('src.utils.logger.logger')
    def test_get_logger_with_name(self, mock_logger):
        """Тест получения логгера с именем"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        result = LoggerSetup.get_logger("test_agent")
        
        mock_logger.bind.assert_called_once_with(name="test_agent")
        assert result == mock_bind
    
    @patch('src.utils.logger.logger')
    def test_get_logger_without_name(self, mock_logger):
        """Тест получения логгера без имени"""
        result = LoggerSetup.get_logger()
        
        assert result == mock_logger


class TestStructuredLogger:
    """Тесты для StructuredLogger"""
    
    def test_initialization(self):
        """Тест инициализации структурированного логгера"""
        logger = StructuredLogger("test_agent", "task_123")
        
        assert logger.agent_name == "test_agent"
        assert logger.task_id == "task_123"
        assert logger.logger is not None
    
    def test_initialization_without_task_id(self):
        """Тест инициализации без task_id"""
        logger = StructuredLogger("test_agent")
        
        assert logger.agent_name == "test_agent"
        assert logger.task_id is None
    
    @patch('src.utils.logger.logger')
    def test_info(self, mock_logger):
        """Тест информационного сообщения"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.info("Test message", key="value")
        
        mock_bind.info.assert_called_once_with("Test message", key="value")
    
    @patch('src.utils.logger.logger')
    def test_warning(self, mock_logger):
        """Тест предупреждения"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.warning("Test warning", key="value")
        
        mock_bind.warning.assert_called_once_with("Test warning", key="value")
    
    @patch('src.utils.logger.logger')
    def test_error(self, mock_logger):
        """Тест ошибки"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.error("Test error", key="value")
        
        mock_bind.error.assert_called_once_with("Test error", key="value")
    
    @patch('src.utils.logger.logger')
    def test_debug(self, mock_logger):
        """Тест отладочного сообщения"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.debug("Test debug", key="value")
        
        mock_bind.debug.assert_called_once_with("Test debug", key="value")
    
    @patch('src.utils.logger.logger')
    def test_critical(self, mock_logger):
        """Тест критической ошибки"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.critical("Test critical", key="value")
        
        mock_bind.critical.assert_called_once_with("Test critical", key="value")
    
    @patch('src.utils.logger.logger')
    def test_log_command_execution(self, mock_logger):
        """Тест логирования выполнения команды"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        result = {
            'exit_code': 0,
            'success': True,
            'duration': 1.5,
            'stdout': 'Success output',
            'stderr': ''
        }
        
        logger.log_command_execution("test command", result)
        
        mock_bind.info.assert_called_once_with(
            "Command executed",
            command="test command",
            exit_code=0,
            success=True,
            duration=1.5,
            stdout_length=13,
            stderr_length=0
        )
    
    @patch('src.utils.logger.logger')
    def test_log_task_start(self, mock_logger):
        """Тест логирования начала задачи"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_task_start("Install nginx")
        
        mock_bind.info.assert_called_once_with(
            "Task started",
            task_description="Install nginx",
            agent="test_agent"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_task_completion(self, mock_logger):
        """Тест логирования завершения задачи"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_task_completion(True, 10.5, 5, 0)
        
        mock_bind.info.assert_called_once_with(
            "Task completed",
            success=True,
            duration=10.5,
            steps_completed=5,
            steps_failed=0
        )
    
    @patch('src.utils.logger.logger')
    def test_log_error_escalation(self, mock_logger):
        """Тест логирования эскалации ошибок"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        error_details = {"error": "Test error", "command": "test cmd"}
        logger.log_error_escalation("step_1", 3, error_details)
        
        mock_bind.error.assert_called_once_with(
            "Error escalation",
            step_id="step_1",
            error_count=3,
            error_details=error_details
        )
    
    @patch('src.utils.logger.logger')
    def test_log_autocorrection(self, mock_logger):
        """Тест логирования автокоррекции"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_autocorrection("apt install", "sudo apt install", True)
        
        mock_bind.info.assert_called_once_with(
            "Autocorrection applied",
            original_command="apt install",
            corrected_command="sudo apt install",
            success=True
        )
    
    @patch('src.utils.logger.logger')
    def test_log_forbidden_command_attempt(self, mock_logger):
        """Тест логирования попытки выполнения запрещенной команды"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_forbidden_command_attempt("rm -rf /", "user1")
        
        mock_bind.warning.assert_called_once_with(
            "Forbidden command attempt",
            command="rm -rf /",
            user="user1"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_forbidden_command_attempt_no_user(self, mock_logger):
        """Тест логирования попытки выполнения запрещенной команды без пользователя"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_forbidden_command_attempt("rm -rf /")
        
        mock_bind.warning.assert_called_once_with(
            "Forbidden command attempt",
            command="rm -rf /",
            user="unknown"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_ssh_connection(self, mock_logger):
        """Тест логирования SSH подключения"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_ssh_connection("example.com", 22, True)
        
        mock_bind.info.assert_called_once_with(
            "SSH connection",
            host="example.com",
            port=22,
            success=True,
            error=None
        )
    
    @patch('src.utils.logger.logger')
    def test_log_ssh_connection_with_error(self, mock_logger):
        """Тест логирования SSH подключения с ошибкой"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_ssh_connection("example.com", 22, False, "Connection refused")
        
        mock_bind.info.assert_called_once_with(
            "SSH connection",
            host="example.com",
            port=22,
            success=False,
            error="Connection refused"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_llm_request(self, mock_logger):
        """Тест логирования запроса к LLM"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = StructuredLogger("test_agent")
        logger.log_llm_request("gpt-4", 1000, 500, 2.5)
        
        mock_bind.info.assert_called_once_with(
            "LLM request",
            model="gpt-4",
            prompt_length=1000,
            response_length=500,
            duration=2.5
        )


class TestMetricsLogger:
    """Тесты для MetricsLogger"""
    
    def test_initialization(self):
        """Тест инициализации логгера метрик"""
        logger = MetricsLogger("test_agent")
        
        assert logger.agent_name == "test_agent"
        assert logger.logger is not None
    
    @patch('src.utils.logger.logger')
    def test_log_performance_metric(self, mock_logger):
        """Тест логирования метрики производительности"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = MetricsLogger("test_agent")
        logger.log_performance_metric("response_time", 1.5, "seconds")
        
        mock_bind.info.assert_called_once_with(
            "Performance metric",
            metric_name="response_time",
            value=1.5,
            unit="seconds"
        )
    
    @patch('src.utils.logger.logger')
    def test_log_performance_metric_no_unit(self, mock_logger):
        """Тест логирования метрики производительности без единицы измерения"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = MetricsLogger("test_agent")
        logger.log_performance_metric("count", 100)
        
        mock_bind.info.assert_called_once_with(
            "Performance metric",
            metric_name="count",
            value=100,
            unit=None
        )
    
    @patch('src.utils.logger.logger')
    def test_log_resource_usage(self, mock_logger):
        """Тест логирования использования ресурсов"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        
        logger = MetricsLogger("test_agent")
        logger.log_resource_usage(75.5, 1024.0, 2048.0)
        
        mock_bind.info.assert_called_once_with(
            "Resource usage",
            cpu_percent=75.5,
            memory_mb=1024.0,
            disk_usage_mb=2048.0
        )
    
    @patch('src.utils.logger.logger')
    @patch('json.dumps')
    def test_log_task_metrics(self, mock_json_dumps, mock_logger):
        """Тест логирования метрик задачи"""
        mock_bind = Mock()
        mock_logger.bind.return_value = mock_bind
        mock_json_dumps.return_value = '{"key": "value"}'
        
        logger = MetricsLogger("test_agent")
        metrics = {"steps_completed": 5, "duration": 10.5}
        logger.log_task_metrics("task_123", metrics)
        
        mock_json_dumps.assert_called_once_with(metrics)
        mock_bind.info.assert_called_once_with(
            "Task metrics",
            task_id="task_123",
            metrics='{"key": "value"}'
        )


class TestModuleFunctions:
    """Тесты для функций модуля"""
    
    def test_setup_logging(self):
        """Тест функции setup_logging"""
        config = {'level': 'DEBUG'}
        result = setup_logging(config)
        
        assert isinstance(result, LoggerSetup)
        assert result.config == config
    
    def test_setup_logging_no_config(self):
        """Тест функции setup_logging без конфигурации"""
        result = setup_logging()
        
        assert isinstance(result, LoggerSetup)
        assert result.config['level'] == 'INFO'
    
    def test_get_structured_logger(self):
        """Тест функции get_structured_logger"""
        logger = get_structured_logger("test_agent", "task_123")
        
        assert isinstance(logger, StructuredLogger)
        assert logger.agent_name == "test_agent"
        assert logger.task_id == "task_123"
    
    def test_get_structured_logger_no_task_id(self):
        """Тест функции get_structured_logger без task_id"""
        logger = get_structured_logger("test_agent")
        
        assert isinstance(logger, StructuredLogger)
        assert logger.agent_name == "test_agent"
        assert logger.task_id is None
    
    def test_get_metrics_logger(self):
        """Тест функции get_metrics_logger"""
        logger = get_metrics_logger("test_agent")
        
        assert isinstance(logger, MetricsLogger)
        assert logger.agent_name == "test_agent"


if __name__ == "__main__":
    pytest.main([__file__])
