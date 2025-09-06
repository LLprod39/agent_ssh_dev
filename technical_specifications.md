# Технические спецификации SSH Agent с LLM

## Технологический стек

### Основные технологии
- **Python 3.9+** - основной язык программирования
- **Node.js 18+** - для Task Master интеграции
- **Task Master AI** - [light-task-master](https://github.com/mrsions/light-task-master) для улучшения промтов
- **Paramiko** - SSH подключения
- **OpenAI API / Anthropic Claude** - LLM интеграция
- **PyYAML** - конфигурационные файлы
- **Pydantic** - валидация данных
- **Loguru** - продвинутое логирование
- **Pytest** - тестирование
- **FastAPI** - веб-интерфейс (опционально)

### Дополнительные библиотеки
- **asyncio** - асинхронное выполнение
- **aiofiles** - асинхронная работа с файлами
- **tenacity** - retry механизмы
- **rich** - красивые консольные выводы
- **typer** - CLI интерфейс

## Детальная архитектура

### 1. Task Master Integration

```python
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional

class TaskMasterIntegration:
    """Интеграция с light-task-master для улучшения промтов"""
    
    def __init__(self, project_path: str, config: TaskMasterConfig):
        self.project_path = Path(project_path)
        self.config = config
        self.taskmaster_path = self.project_path / ".taskmaster"
        self._ensure_taskmaster_initialized()
    
    def _ensure_taskmaster_initialized(self):
        """Проверяет и инициализирует Task Master если необходимо"""
        if not self.taskmaster_path.exists():
            self._init_taskmaster()
    
    def _init_taskmaster(self):
        """Инициализирует Task Master в проекте"""
        try:
            subprocess.run([
                "npx", "task-master-ai", "init",
                "--rules", "cursor,windsurf,vscode"
            ], cwd=self.project_path, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to initialize Task Master: {e}")
    
    async def improve_prompt(self, user_prompt: str, context: dict) -> str:
        """Улучшает пользовательский промт через Task Master"""
        # Создаем временный PRD если его нет
        prd_path = self.taskmaster_path / "docs" / "prd.txt"
        if not prd_path.exists():
            await self._create_prd_from_prompt(user_prompt, context)
        
        # Используем Task Master для парсинга и улучшения
        improved_tasks = await self._parse_prd_with_taskmaster(prd_path)
        return self._format_improved_prompt(improved_tasks)
    
    async def _create_prd_from_prompt(self, prompt: str, context: dict) -> None:
        """Создает PRD из пользовательского промта"""
        prd_content = f"""
# Product Requirements Document

## User Request
{prompt}

## Context
{json.dumps(context, indent=2)}

## Requirements
- Implement the requested functionality
- Ensure proper error handling
- Follow best practices for the technology stack
- Include proper documentation
"""
        prd_path = self.taskmaster_path / "docs" / "prd.txt"
        prd_path.parent.mkdir(parents=True, exist_ok=True)
        prd_path.write_text(prd_content, encoding='utf-8')
    
    async def _parse_prd_with_taskmaster(self, prd_path: Path) -> List[Dict]:
        """Парсит PRD с помощью Task Master"""
        try:
            result = subprocess.run([
                "npx", "task-master-ai", "parse-prd", str(prd_path)
            ], cwd=self.project_path, capture_output=True, text=True, check=True)
            
            # Парсим результат Task Master
            tasks = self._parse_taskmaster_output(result.stdout)
            return tasks
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Task Master parsing failed: {e}")
    
    def _parse_taskmaster_output(self, output: str) -> List[Dict]:
        """Парсит вывод Task Master в структурированный формат"""
        # Здесь нужно реализовать парсинг вывода Task Master
        # В зависимости от формата вывода
        tasks = []
        # TODO: Реализовать парсинг
        return tasks
    
    def _format_improved_prompt(self, tasks: List[Dict]) -> str:
        """Форматирует улучшенный промт из задач Task Master"""
        if not tasks:
            return "Unable to improve prompt with Task Master"
        
        formatted_tasks = []
        for i, task in enumerate(tasks, 1):
            formatted_tasks.append(f"{i}. {task.get('description', 'Unknown task')}")
        
        return f"""
Improved task breakdown:
{chr(10).join(formatted_tasks)}

This breakdown provides a structured approach to implementing your request.
"""
```

### 2. Task Agent (Главный планировщик)

```python
class TaskAgent:
    """Разбиение задач на основные шаги"""
    
    def __init__(self, llm_client: LLMClient, config: TaskAgentConfig):
        self.llm_client = llm_client
        self.config = config
        self.step_counter = 0
    
    async def plan_task(self, task: str, server_info: ServerInfo) -> List[Step]:
        """Создает план выполнения задачи"""
        planning_prompt = self._build_planning_prompt(task, server_info)
        
        response = await self.llm_client.generate(
            system_prompt=PLANNING_SYSTEM_PROMPT,
            user_prompt=planning_prompt,
            temperature=self.config.temperature
        )
        
        steps = self._parse_steps(response)
        return self._validate_steps(steps)
    
    def _build_planning_prompt(self, task: str, server_info: ServerInfo) -> str:
        return f"""
        Задача: {task}
        
        Информация о сервере:
        - ОС: {server_info.os_type}
        - Установленные сервисы: {server_info.installed_services}
        - Запрещенные команды: {server_info.forbidden_commands}
        
        Разбейте задачу на логические шаги (максимум {self.config.max_steps}).
        Каждый шаг должен быть выполним независимо.
        """
```

### 3. Subtask Agent (Детальное планирование)

```python
class SubtaskAgent:
    """Разбиение шагов на подзадачи и команды"""
    
    async def plan_subtasks(self, step: Step, server_info: ServerInfo) -> List[Subtask]:
        """Создает детальный план выполнения шага"""
        subtask_prompt = self._build_subtask_prompt(step, server_info)
        
        response = await self.llm_client.generate(
            system_prompt=SUBTASK_SYSTEM_PROMPT,
            user_prompt=subtask_prompt,
            temperature=self.config.temperature
        )
        
        subtasks = self._parse_subtasks(response)
        return self._validate_subtasks(subtasks)
    
    def _build_subtask_prompt(self, step: Step, server_info: ServerInfo) -> str:
        return f"""
        Шаг: {step.description}
        
        Создайте последовательность команд для выполнения этого шага.
        Учитывайте:
        - ОС: {server_info.os_type}
        - Установленные пакеты: {server_info.installed_packages}
        - Запрещенные команды: {server_info.forbidden_commands}
        
        Каждая команда должна включать:
        - Саму команду
        - Проверку успешности выполнения
        - Таймаут выполнения
        - Предусловия (если нужны)
        """
```

### 4. SSH Connector

```python
class SSHConnector:
    """Безопасное SSH подключение"""
    
    def __init__(self, config: SSHConfig):
        self.config = config
        self.client = None
        self.sftp = None
    
    async def connect(self) -> bool:
        """Устанавливает SSH соединение"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.config.auth_method == "key":
                self.client.connect(
                    hostname=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    key_filename=self.config.key_path,
                    timeout=self.config.timeout
                )
            else:
                self.client.connect(
                    hostname=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    timeout=self.config.timeout
                )
            
            self.sftp = self.client.open_sftp()
            return True
            
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return False
    
    async def execute_command(self, command: str, timeout: int = 30) -> CommandResult:
        """Выполняет команду через SSH"""
        if not self.client:
            raise ConnectionError("SSH not connected")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Ждем завершения команды
            exit_code = stdout.channel.recv_exit_status()
            
            return CommandResult(
                command=command,
                exit_code=exit_code,
                stdout=stdout.read().decode('utf-8'),
                stderr=stderr.read().decode('utf-8'),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timestamp=datetime.now()
            )
```

### 5. Execution Model

```python
class ExecutionModel:
    """Выполнение команд с автокоррекцией"""
    
    def __init__(self, ssh_connector: SSHConnector, config: ExecutorConfig):
        self.ssh_connector = ssh_connector
        self.config = config
        self.error_count = 0
    
    async def execute_subtask(self, subtask: Subtask) -> ExecutionResult:
        """Выполняет подзадачу с автокоррекцией"""
        result = await self._execute_command(subtask.command)
        
        if result.success:
            return ExecutionResult(success=True, result=result)
        
        # Попытка автокоррекции
        if self.config.auto_correction_enabled:
            corrected_result = await self._attempt_autocorrection(subtask, result)
            if corrected_result.success:
                return ExecutionResult(success=True, result=corrected_result)
        
        self.error_count += 1
        return ExecutionResult(success=False, result=result, error_count=self.error_count)
    
    async def _attempt_autocorrection(self, subtask: Subtask, failed_result: CommandResult) -> CommandResult:
        """Пытается исправить ошибку автоматически"""
        correction_strategies = [
            self._fix_syntax_error,
            self._add_apt_update,
            self._try_alternative_flags,
            self._check_network_connectivity,
            self._restart_service
        ]
        
        for strategy in correction_strategies:
            corrected_command = await strategy(subtask.command, failed_result)
            if corrected_command:
                result = await self._execute_command(corrected_command)
                if result.success:
                    return result
        
        return failed_result
    
    async def _fix_syntax_error(self, command: str, result: CommandResult) -> Optional[str]:
        """Исправляет синтаксические ошибки"""
        if "command not found" in result.stderr.lower():
            # Попытка найти правильный путь к команде
            which_result = await self._execute_command(f"which {command.split()[0]}")
            if which_result.success:
                return command.replace(command.split()[0], which_result.stdout.strip())
        return None
    
    async def _add_apt_update(self, command: str, result: CommandResult) -> Optional[str]:
        """Добавляет apt update перед установкой пакетов"""
        if "apt install" in command and "unable to locate package" in result.stderr.lower():
            return f"apt update && {command}"
        return None
```

### 6. Error Handler

```python
class ErrorHandler:
    """Обработка ошибок и формирование отчетов"""
    
    def __init__(self, config: ErrorHandlerConfig):
        self.config = config
        self.error_logs = []
    
    async def handle_step_errors(self, step_id: str, error_count: int, logs: List[CommandResult]) -> bool:
        """Обрабатывает ошибки на уровне шага"""
        if error_count >= self.config.error_threshold_per_step:
            await self._escalate_to_planner(step_id, logs)
            return True
        return False
    
    async def _escalate_to_planner(self, step_id: str, logs: List[CommandResult]) -> None:
        """Отправляет ошибки планировщику для пересмотра"""
        error_report = self._build_error_report(step_id, logs)
        
        # Отправляем отчет соответствующему планировщику
        if self.config.send_to_planner_after_threshold:
            await self._send_to_planner(error_report)
    
    def _build_error_report(self, step_id: str, logs: List[CommandResult]) -> ErrorReport:
        """Строит отчет об ошибках"""
        return ErrorReport(
            step_id=step_id,
            error_count=len(logs),
            commands_executed=[log.command for log in logs],
            error_details=[
                {
                    "command": log.command,
                    "exit_code": log.exit_code,
                    "stdout": log.stdout,
                    "stderr": log.stderr,
                    "timestamp": log.timestamp
                }
                for log in logs
            ],
            server_state=self._capture_server_state(),
            suggestions=self._generate_suggestions(logs)
        )
```

## Модели данных

### Pydantic модели

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ServerInfo(BaseModel):
    host: str
    port: int = 22
    username: str
    os_type: str
    installed_services: List[str] = []
    installed_packages: List[str] = []
    forbidden_commands: List[str] = []
    disk_space: Optional[Dict[str, int]] = None
    memory_info: Optional[Dict[str, int]] = None

class Step(BaseModel):
    step_id: str
    description: str
    priority: int = 1
    dependencies: List[str] = []
    estimated_duration: Optional[int] = None

class Subtask(BaseModel):
    subtask_id: str
    step_id: str
    command: str
    expected_output: Optional[str] = None
    timeout: int = 30
    prerequisites: List[str] = []
    retry_count: int = 0

class CommandResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timestamp: datetime
    duration: Optional[float] = None
    
    @property
    def success(self) -> bool:
        return self.exit_code == 0

class ExecutionResult(BaseModel):
    success: bool
    result: CommandResult
    error_count: int = 0
    autocorrection_applied: bool = False

class ErrorReport(BaseModel):
    step_id: str
    error_count: int
    commands_executed: List[str]
    error_details: List[Dict[str, Any]]
    server_state: Dict[str, Any]
    suggestions: List[str]
    timestamp: datetime = datetime.now()

class TaskResult(BaseModel):
    task_id: str
    success: bool
    steps_completed: List[str]
    steps_failed: List[str]
    total_duration: float
    error_reports: List[ErrorReport]
    final_state: Dict[str, Any]
```

## Конфигурационные классы

```python
class SSHConfig(BaseModel):
    host: str
    port: int = 22
    username: str
    auth_method: str = "key"  # key, password
    key_path: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30

class TaskmasterConfig(BaseModel):
    enabled: bool = True
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 1000

class TaskAgentConfig(BaseModel):
    model: str = "gpt-4"
    temperature: float = 0.3
    max_steps: int = 10
    max_tokens: int = 2000

class SubtaskAgentConfig(BaseModel):
    model: str = "gpt-4"
    temperature: float = 0.1
    max_subtasks: int = 20
    max_tokens: int = 3000

class ExecutorConfig(BaseModel):
    max_retries_per_command: int = 2
    auto_correction_enabled: bool = True
    dry_run_mode: bool = False
    command_timeout: int = 30

class ErrorHandlerConfig(BaseModel):
    error_threshold_per_step: int = 4
    send_to_planner_after_threshold: bool = True
    human_escalation_threshold: int = 3
    max_error_reports: int = 10

class LLMConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4"
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 60
```

## Система логирования

```python
import loguru
from loguru import logger
import sys

class LoggerSetup:
    """Настройка системы логирования"""
    
    @staticmethod
    def setup_logging(log_level: str = "INFO", log_file: str = "agent.log"):
        # Удаляем стандартный обработчик
        logger.remove()
        
        # Консольный вывод
        logger.add(
            sys.stdout,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # Файловый вывод
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="zip"
        )
        
        # Отдельный файл для ошибок
        logger.add(
            "errors.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="5 MB",
            retention="30 days"
        )
```

## Система тестирования

### Структура тестов

```python
# tests/test_agents/test_task_agent.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.agents.task_agent import TaskAgent
from src.models.planning_model import Step

class TestTaskAgent:
    @pytest.fixture
    def task_agent(self):
        mock_llm = Mock()
        config = TaskAgentConfig()
        return TaskAgent(mock_llm, config)
    
    @pytest.mark.asyncio
    async def test_plan_task_success(self, task_agent):
        # Тест успешного планирования задачи
        task = "Установить PostgreSQL"
        server_info = ServerInfo(host="test.com", os_type="ubuntu")
        
        # Мокаем LLM ответ
        task_agent.llm_client.generate = AsyncMock(return_value="Step 1: Update packages\nStep 2: Install PostgreSQL")
        
        steps = await task_agent.plan_task(task, server_info)
        
        assert len(steps) == 2
        assert steps[0].description == "Update packages"
        assert steps[1].description == "Install PostgreSQL"
    
    @pytest.mark.asyncio
    async def test_plan_task_validation_error(self, task_agent):
        # Тест обработки ошибок валидации
        task = "Установить PostgreSQL"
        server_info = ServerInfo(host="test.com", os_type="ubuntu")
        
        # Мокаем некорректный ответ LLM
        task_agent.llm_client.generate = AsyncMock(return_value="Invalid response")
        
        with pytest.raises(ValidationError):
            await task_agent.plan_task(task, server_info)
```

### Интеграционные тесты

```python
# tests/integration/test_full_workflow.py
import pytest
from src.main import SSHAgent
from unittest.mock import Mock

class TestFullWorkflow:
    @pytest.mark.asyncio
    async def test_successful_task_execution(self):
        """Тест полного успешного выполнения задачи"""
        # Настройка моков
        mock_ssh = Mock()
        mock_llm = Mock()
        
        # Создание агента с моками
        agent = SSHAgent(ssh_connector=mock_ssh, llm_client=mock_llm)
        
        # Выполнение задачи
        result = await agent.execute_task("Установить nginx")
        
        # Проверка результата
        assert result.success
        assert len(result.steps_completed) > 0
        assert len(result.steps_failed) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_and_escalation(self):
        """Тест обработки ошибок и эскалации"""
        # Тест сценария с ошибками
        pass
```

## Развертывание и мониторинг

### Docker контейнеризация

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов проекта
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создание пользователя для безопасности
RUN useradd -m -u 1000 agent && chown -R agent:agent /app
USER agent

CMD ["python", "main.py"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  ssh-agent:
    build: .
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ~/.ssh:/home/agent/.ssh:ro
    environment:
      - LOG_LEVEL=INFO
      - CONFIG_PATH=/app/config
    restart: unless-stopped
    
  monitoring:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-storage:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  grafana-storage:
```

### Мониторинг с Prometheus

```python
# src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Метрики
TASK_EXECUTIONS = Counter('ssh_agent_tasks_total', 'Total number of tasks executed', ['status'])
COMMAND_EXECUTIONS = Counter('ssh_agent_commands_total', 'Total number of commands executed', ['status'])
TASK_DURATION = Histogram('ssh_agent_task_duration_seconds', 'Task execution duration')
ERROR_COUNT = Gauge('ssh_agent_errors_total', 'Total number of errors')
ACTIVE_CONNECTIONS = Gauge('ssh_agent_active_connections', 'Number of active SSH connections')

class MetricsCollector:
    def __init__(self, port: int = 8000):
        self.port = port
        start_http_server(port)
    
    def record_task_execution(self, status: str):
        TASK_EXECUTIONS.labels(status=status).inc()
    
    def record_command_execution(self, status: str):
        COMMAND_EXECUTIONS.labels(status=status).inc()
    
    def record_task_duration(self, duration: float):
        TASK_DURATION.observe(duration)
    
    def update_error_count(self, count: int):
        ERROR_COUNT.set(count)
    
    def update_active_connections(self, count: int):
        ACTIVE_CONNECTIONS.set(count)
```

Этот технический документ предоставляет детальную информацию о реализации каждого компонента системы, включая код, модели данных, конфигурацию и тестирование.
