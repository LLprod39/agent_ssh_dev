"""
Конфигурация агентов и LLM
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml


class TaskmasterConfig(BaseModel):
    """Конфигурация Task Master"""
    
    enabled: bool = Field(default=True, description="Включен ли Task Master")
    model: str = Field(default="gpt-4", description="Модель LLM для Task Master")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура для генерации")
    max_tokens: int = Field(default=1000, ge=1, le=8000, description="Максимальное количество токенов")


class TaskAgentConfig(BaseModel):
    """Конфигурация Task Agent (планировщик основных шагов)"""
    
    model: str = Field(default="gpt-4", description="Модель LLM")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Температура для генерации")
    max_steps: int = Field(default=10, ge=1, le=50, description="Максимальное количество шагов")
    max_tokens: int = Field(default=2000, ge=1, le=8000, description="Максимальное количество токенов")


class SubtaskAgentConfig(BaseModel):
    """Конфигурация Subtask Agent (планировщик подзадач)"""
    
    model: str = Field(default="gpt-4", description="Модель LLM")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Температура для генерации")
    max_subtasks: int = Field(default=20, ge=1, le=100, description="Максимальное количество подзадач")
    max_tokens: int = Field(default=3000, ge=1, le=8000, description="Максимальное количество токенов")


class ExecutorConfig(BaseModel):
    """Конфигурация Executor (выполнение команд)"""
    
    max_retries_per_command: int = Field(default=2, ge=0, le=10, description="Максимальное количество повторов команды")
    auto_correction_enabled: bool = Field(default=True, description="Включена ли автокоррекция")
    dry_run_mode: bool = Field(default=False, description="Режим симуляции")
    command_timeout: int = Field(default=30, ge=1, le=300, description="Таймаут выполнения команды в секундах")
    
    # Настройки автокоррекции
    autocorrection_max_attempts: int = Field(default=3, ge=1, le=10, description="Максимальное количество попыток автокоррекции")
    autocorrection_timeout: int = Field(default=30, ge=5, le=120, description="Таймаут для автокоррекции в секундах")
    enable_syntax_correction: bool = Field(default=True, description="Включить исправление синтаксических ошибок")
    enable_permission_correction: bool = Field(default=True, description="Включить исправление ошибок прав доступа")
    enable_network_correction: bool = Field(default=True, description="Включить исправление сетевых ошибок")
    enable_service_correction: bool = Field(default=True, description="Включить исправление ошибок сервисов")
    enable_package_correction: bool = Field(default=True, description="Включить исправление ошибок пакетов")
    enable_command_substitution: bool = Field(default=True, description="Включить замену команд")


class ErrorHandlerConfig(BaseModel):
    """Конфигурация Error Handler"""
    
    error_threshold_per_step: int = Field(default=4, ge=1, le=20, description="Порог ошибок на шаг")
    send_to_planner_after_threshold: bool = Field(default=True, description="Отправлять ли ошибки планировщику")
    human_escalation_threshold: int = Field(default=3, ge=1, le=10, description="Порог эскалации к человеку")
    max_error_reports: int = Field(default=10, ge=1, le=100, description="Максимальное количество отчетов об ошибках")
    
    # Настройки системы подсчета ошибок
    enable_error_tracking: bool = Field(default=True, description="Включить систему подсчета ошибок")
    max_retention_days: int = Field(default=7, ge=1, le=30, description="Максимальное количество дней хранения записей об ошибках")
    track_error_patterns: bool = Field(default=True, description="Отслеживать паттерны ошибок")
    enable_escalation: bool = Field(default=True, description="Включить систему эскалации")
    escalation_cooldown_minutes: int = Field(default=5, ge=1, le=60, description="Время ожидания между эскалациями в минутах")


class LLMConfig(BaseModel):
    """Конфигурация LLM"""
    
    api_key: str = Field(..., description="API ключ")
    base_url: str = Field(default="https://api.openai.com/v1", description="Базовый URL API")
    model: str = Field(default="gpt-4", description="Модель по умолчанию")
    max_tokens: int = Field(default=4000, ge=1, le=8000, description="Максимальное количество токенов")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура по умолчанию")
    timeout: int = Field(default=60, ge=1, le=300, description="Таймаут запроса в секундах")
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        """Валидация API ключа"""
        if not v or v == "your-api-key":
            raise ValueError("API ключ не может быть пустым или значением по умолчанию")
        return v


class LoggingConfig(BaseModel):
    """Конфигурация логирования"""
    
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="Уровень логирования")
    log_file: str = Field(default="logs/agent.log", description="Путь к файлу логов")
    error_file: str = Field(default="logs/errors.log", description="Путь к файлу ошибок")
    max_file_size: str = Field(default="10 MB", description="Максимальный размер файла лога")
    retention_days: int = Field(default=7, ge=1, le=365, description="Количество дней хранения логов")
    compression: bool = Field(default=True, description="Сжимать ли старые логи")


class SecurityConfig(BaseModel):
    """Конфигурация безопасности"""
    
    validate_commands: bool = Field(default=True, description="Валидировать ли команды")
    log_forbidden_attempts: bool = Field(default=True, description="Логировать ли попытки выполнения запрещенных команд")
    require_confirmation_for_dangerous: bool = Field(default=True, description="Требовать подтверждение для опасных команд")
    allowed_commands_only: bool = Field(default=False, description="Разрешать только команды из белого списка")


class AgentConfig(BaseModel):
    """Основная конфигурация агентов"""
    
    taskmaster: TaskmasterConfig = Field(default_factory=TaskmasterConfig)
    task_agent: TaskAgentConfig = Field(default_factory=TaskAgentConfig)
    subtask_agent: SubtaskAgentConfig = Field(default_factory=SubtaskAgentConfig)
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)
    error_handler: ErrorHandlerConfig = Field(default_factory=ErrorHandlerConfig)
    llm: LLMConfig = Field(..., description="Конфигурация LLM")
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'AgentConfig':
        """Загрузка конфигурации из YAML файла"""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Создаем конфигурации для каждого агента
        taskmaster_config = TaskmasterConfig(**data.get('agents', {}).get('taskmaster', {}))
        task_agent_config = TaskAgentConfig(**data.get('agents', {}).get('task_agent', {}))
        subtask_agent_config = SubtaskAgentConfig(**data.get('agents', {}).get('subtask_agent', {}))
        executor_config = ExecutorConfig(**data.get('agents', {}).get('executor', {}))
        error_handler_config = ErrorHandlerConfig(**data.get('agents', {}).get('error_handler', {}))
        llm_config = LLMConfig(**data.get('llm', {}))
        logging_config = LoggingConfig(**data.get('logging', {}))
        security_config = SecurityConfig(**data.get('security', {}))
        
        return cls(
            taskmaster=taskmaster_config,
            task_agent=task_agent_config,
            subtask_agent=subtask_agent_config,
            executor=executor_config,
            error_handler=error_handler_config,
            llm=llm_config,
            logging=logging_config,
            security=security_config
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return self.dict()
    
    def get_agent_config(self, agent_name: str) -> BaseModel:
        """Получение конфигурации конкретного агента"""
        config_map = {
            'taskmaster': self.taskmaster,
            'task_agent': self.task_agent,
            'subtask_agent': self.subtask_agent,
            'executor': self.executor,
            'error_handler': self.error_handler
        }
        
        if agent_name not in config_map:
            raise ValueError(f"Неизвестный агент: {agent_name}")
        
        return config_map[agent_name]
    
    def is_dry_run(self) -> bool:
        """Проверка, включен ли режим симуляции"""
        return self.executor.dry_run_mode
    
    def get_llm_params(self, agent_name: str = None) -> Dict[str, Any]:
        """Получение параметров LLM для конкретного агента или общих"""
        if agent_name:
            agent_config = self.get_agent_config(agent_name)
            return {
                'model': getattr(agent_config, 'model', self.llm.model),
                'temperature': getattr(agent_config, 'temperature', self.llm.temperature),
                'max_tokens': getattr(agent_config, 'max_tokens', self.llm.max_tokens),
                'api_key': self.llm.api_key,
                'base_url': self.llm.base_url,
                'timeout': self.llm.timeout
            }
        else:
            return {
                'model': self.llm.model,
                'temperature': self.llm.temperature,
                'max_tokens': self.llm.max_tokens,
                'api_key': self.llm.api_key,
                'base_url': self.llm.base_url,
                'timeout': self.llm.timeout
            }
