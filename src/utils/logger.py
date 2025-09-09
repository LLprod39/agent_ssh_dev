"""
Система логирования для SSH Agent
"""
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from datetime import datetime
import json


class LoggerSetup:
    """Настройка системы логирования"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Инициализация системы логирования
        
        Args:
            config: Конфигурация логирования
        """
        self.config = config or self._get_default_config()
        self._setup_logging()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Получение конфигурации по умолчанию"""
        return {
            'level': 'INFO',
            'log_file': 'logs/agent.log',
            'error_file': 'logs/errors.log',
            'max_file_size': '10 MB',
            'retention_days': 7,
            'compression': True
        }
    
    def _setup_logging(self):
        """Настройка системы логирования"""
        # Удаляем стандартный обработчик
        logger.remove()
        
        # Создаем директории для логов
        self._ensure_log_directories()
        
        # Консольный вывод
        self._setup_console_logging()
        
        # Файловый вывод
        self._setup_file_logging()
        
        # Отдельный файл для ошибок
        self._setup_error_logging()
        
        # Добавляем контекстную информацию
        self._add_context_logging()
    
    def _ensure_log_directories(self):
        """Создание директорий для логов"""
        log_file = Path(self.config['log_file'])
        error_file = Path(self.config['error_file'])
        
        log_file.parent.mkdir(parents=True, exist_ok=True)
        error_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _setup_console_logging(self):
        """Настройка консольного логирования"""
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        
        logger.add(
            sys.stdout,
            level=self.config['level'],
            format=console_format,
            colorize=True,
            filter=self._console_filter
        )
    
    def _setup_file_logging(self):
        """Настройка файлового логирования"""
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        )
        
        logger.add(
            self.config['log_file'],
            level=self.config['level'],
            format=file_format,
            rotation=self.config['max_file_size'],
            retention=f"{self.config['retention_days']} days",
            compression="zip" if self.config['compression'] else None,
            encoding="utf-8"
        )
    
    def _setup_error_logging(self):
        """Настройка логирования ошибок"""
        error_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} - "
            "{message}"
        )
        
        logger.add(
            self.config['error_file'],
            level="ERROR",
            format=error_format,
            rotation="5 MB",
            retention="30 days",
            compression="zip" if self.config['compression'] else None,
            encoding="utf-8"
        )
    
    def _add_context_logging(self):
        """Добавление контекстной информации в логи"""
        def add_context(record):
            record["extra"]["timestamp"] = datetime.now().isoformat()
            record["extra"]["pid"] = os.getpid()
            return True
        
        logger.patch(add_context)
    
    def _console_filter(self, record):
        """Фильтр для консольного вывода"""
        # Исключаем DEBUG сообщения из консоли в production
        if record["level"].name == "DEBUG" and self.config['level'] != "DEBUG":
            return False
        return True
    
    @staticmethod
    def get_logger(name: str = None):
        """Получение экземпляра логгера"""
        if name:
            return logger.bind(name=name)
        return logger


class StructuredLogger:
    """Структурированное логирование для агентов"""
    
    def __init__(self, agent_name: str, task_id: str = None):
        """
        Инициализация структурированного логгера
        
        Args:
            agent_name: Имя агента
            task_id: ID задачи
        """
        self.agent_name = agent_name
        self.task_id = task_id
        self.logger = logger.bind(agent=agent_name, task_id=task_id)
    
    def info(self, message: str, **kwargs):
        """Информационное сообщение"""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Предупреждение"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Ошибка"""
        self.logger.error(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Отладочное сообщение"""
        self.logger.debug(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Критическая ошибка"""
        self.logger.critical(message, **kwargs)
    
    def log_command_execution(self, command: str, result: Dict[str, Any]):
        """Логирование выполнения команды"""
        self.logger.info(
            "Command executed",
            command=command,
            exit_code=result.get('exit_code'),
            success=result.get('success', False),
            duration=result.get('duration'),
            stdout_length=len(result.get('stdout', '')),
            stderr_length=len(result.get('stderr', ''))
        )
    
    def log_task_start(self, task_description: str):
        """Логирование начала задачи"""
        self.logger.info(
            "Task started",
            task_description=task_description,
            agent=self.agent_name
        )
    
    def log_task_completion(self, success: bool, duration: float, steps_completed: int, steps_failed: int):
        """Логирование завершения задачи"""
        self.logger.info(
            "Task completed",
            success=success,
            duration=duration,
            steps_completed=steps_completed,
            steps_failed=steps_failed
        )
    
    def log_error_escalation(self, step_id: str, error_count: int, error_details: Dict[str, Any]):
        """Логирование эскалации ошибок"""
        self.logger.error(
            "Error escalation",
            step_id=step_id,
            error_count=error_count,
            error_details=error_details
        )
    
    def log_autocorrection(self, original_command: str, corrected_command: str, success: bool):
        """Логирование автокоррекции"""
        self.logger.info(
            "Autocorrection applied",
            original_command=original_command,
            corrected_command=corrected_command,
            success=success
        )
    
    def log_forbidden_command_attempt(self, command: str, user: str = None):
        """Логирование попытки выполнения запрещенной команды"""
        self.logger.warning(
            "Forbidden command attempt",
            command=command,
            user=user or "unknown"
        )
    
    def log_ssh_connection(self, host: str, port: int, success: bool, error: str = None):
        """Логирование SSH подключения"""
        self.logger.info(
            "SSH connection",
            host=host,
            port=port,
            success=success,
            error=error
        )
    
    def log_llm_request(self, model: str, prompt_length: int, response_length: int, duration: float):
        """Логирование запроса к LLM"""
        self.logger.info(
            "LLM request",
            model=model,
            prompt_length=prompt_length,
            response_length=response_length,
            duration=duration
        )


class MetricsLogger:
    """Логгер для метрик и производительности"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = logger.bind(agent=agent_name, type="metrics")
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = None):
        """Логирование метрики производительности"""
        self.logger.info(
            "Performance metric",
            metric_name=metric_name,
            value=value,
            unit=unit
        )
    
    def log_resource_usage(self, cpu_percent: float, memory_mb: float, disk_usage_mb: float):
        """Логирование использования ресурсов"""
        self.logger.info(
            "Resource usage",
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            disk_usage_mb=disk_usage_mb
        )
    
    def log_task_metrics(self, task_id: str, metrics: Dict[str, Any]):
        """Логирование метрик задачи"""
        self.logger.info(
            "Task metrics",
            task_id=task_id,
            metrics=json.dumps(metrics)
        )


def setup_logging(config: Optional[Dict[str, Any]] = None) -> LoggerSetup:
    """
    Настройка системы логирования
    
    Args:
        config: Конфигурация логирования
        
    Returns:
        Экземпляр LoggerSetup
    """
    return LoggerSetup(config)


def get_structured_logger(agent_name: str, task_id: str = None) -> StructuredLogger:
    """
    Получение структурированного логгера
    
    Args:
        agent_name: Имя агента
        task_id: ID задачи
        
    Returns:
        Экземпляр StructuredLogger
    """
    return StructuredLogger(agent_name, task_id)


def get_metrics_logger(agent_name: str) -> MetricsLogger:
    """
    Получение логгера метрик
    
    Args:
        agent_name: Имя агента
        
    Returns:
        Экземпляр MetricsLogger
    """
    return MetricsLogger(agent_name)
