# API Документация SSH Agent

## Обзор

SSH Agent предоставляет программный интерфейс для автоматизированного выполнения задач на удаленных серверах через SSH с использованием LLM для планирования и выполнения команд.

## Основные классы

### SSHAgent

Главный класс для работы с SSH Agent.

#### Конструктор

```python
SSHAgent(
    server_config_path: Optional[str] = None,
    agent_config_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
)
```

**Параметры:**
- `server_config_path` - путь к файлу конфигурации сервера (YAML)
- `agent_config_path` - путь к файлу конфигурации агентов (YAML)
- `config` - опциональный словарь конфигурации

**Пример:**
```python
from src.main import SSHAgent

# Инициализация с файлами конфигурации
agent = SSHAgent(
    server_config_path="config/server_config.yaml",
    agent_config_path="config/agent_config.yaml"
)

# Инициализация с конфигурацией из словаря
config = {
    "server": {
        "host": "example.com",
        "username": "user",
        "auth_method": "key",
        "key_path": "/path/to/key"
    },
    "agents": {
        "llm": {"api_key": "your-api-key"}
    }
}
agent = SSHAgent(config=config)
```

#### Методы

##### execute_task

```python
async def execute_task(
    self, 
    task_description: str, 
    dry_run: bool = False
) -> Dict[str, Any]
```

Выполнение задачи на удаленном сервере.

**Параметры:**
- `task_description` - описание задачи для выполнения
- `dry_run` - если True, только показать что будет выполнено

**Возвращает:**
```python
{
    "success": bool,           # Успешность выполнения
    "task_id": str,           # ID задачи
    "steps_completed": int,   # Количество выполненных шагов
    "steps_failed": int,      # Количество проваленных шагов
    "total_steps": int,       # Общее количество шагов
    "execution_duration": float,  # Время выполнения в секундах
    "progress_percentage": float, # Процент выполнения
    "step_results": List[Dict],   # Результаты выполнения шагов
    "final_report": Dict,     # Финальный отчет
    "dry_run": bool          # Режим dry-run
}
```

**Пример:**
```python
result = await agent.execute_task("Установить и настроить PostgreSQL")
if result["success"]:
    print(f"Задача выполнена за {result['execution_duration']:.2f}с")
else:
    print(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
```

##### get_agent_status

```python
def get_agent_status(self) -> Dict[str, Any]
```

Получение статуса агента и статистики.

**Возвращает:**
```python
{
    "agent_stats": {
        "tasks_executed": int,      # Выполнено задач
        "tasks_completed": int,     # Завершено задач
        "tasks_failed": int,        # Провалено задач
        "total_execution_time": float,  # Общее время выполнения
        "total_errors": int,        # Общее количество ошибок
        "escalations": int          # Количество эскалаций
    },
    "current_execution": {
        "task_id": str,            # ID текущей задачи
        "progress": float,         # Прогресс выполнения
        "is_running": bool         # Выполняется ли задача
    },
    "execution_history_count": int,  # Количество записей в истории
    "components_status": {         # Статус компонентов
        "ssh_connector": bool,
        "task_master": bool,
        "task_agent": bool,
        "subtask_agent": bool,
        "execution_model": bool,
        "error_handler": bool
    }
}
```

##### get_execution_history

```python
def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]
```

Получение истории выполнения задач.

**Параметры:**
- `limit` - количество последних записей для возврата (0 = все)

**Возвращает:**
```python
[
    {
        "task_id": str,                    # ID задачи
        "task_title": str,                 # Название задачи
        "completed_steps": int,            # Выполнено шагов
        "total_steps": int,                # Всего шагов
        "failed_steps": int,               # Провалено шагов
        "error_count": int,                # Количество ошибок
        "duration": float,                 # Длительность выполнения
        "is_dry_run": bool,                # Режим dry-run
        "execution_start_time": str,       # Время начала (ISO)
        "execution_end_time": str,         # Время окончания (ISO)
        "success": bool                    # Успешность
    }
]
```

##### cleanup_old_data

```python
def cleanup_old_data(self, days: int = 7)
```

Очистка старых данных.

**Параметры:**
- `days` - количество дней для хранения данных

## Конфигурационные классы

### ServerConfig

Конфигурация сервера для SSH подключения.

```python
from src.config.server_config import ServerConfig

config = ServerConfig(
    host="example.com",
    port=22,
    username="user",
    auth_method="key",  # "key" или "password"
    key_path="/path/to/private/key",
    password="password",  # если auth_method="password"
    timeout=30,
    os_type="ubuntu",  # "ubuntu", "centos", "debian"
    forbidden_commands=[
        "rm -rf /",
        "dd if=/dev/zero",
        "mkfs"
    ],
    installed_services=[
        "docker",
        "nginx",
        "postgresql"
    ]
)
```

### AgentConfig

Конфигурация агентов и LLM.

```python
from src.config.agent_config import AgentConfig

config = AgentConfig(
    taskmaster={
        "enabled": True,
        "model": "gpt-4",
        "temperature": 0.7
    },
    task_agent={
        "model": "gpt-4",
        "temperature": 0.3,
        "max_steps": 10
    },
    subtask_agent={
        "model": "gpt-4",
        "temperature": 0.1,
        "max_subtasks": 20
    },
    executor={
        "max_retries_per_command": 2,
        "auto_correction_enabled": True,
        "dry_run_mode": False
    },
    error_handler={
        "error_threshold_per_step": 4,
        "send_to_planner_after_threshold": True,
        "human_escalation_threshold": 3
    },
    llm={
        "api_key": "your-api-key",
        "base_url": "https://api.openai.com/v1",
        "max_tokens": 4000,
        "timeout": 60
    }
)
```

## Модели данных

### Task

```python
from src.models.planning_model import Task

task = Task(
    task_id="task_001",
    title="Установить PostgreSQL",
    description="Установка и настройка PostgreSQL сервера",
    status="pending",  # "pending", "in_progress", "completed", "failed"
    steps=[...],       # Список TaskStep
    metadata={}        # Дополнительные данные
)
```

### TaskStep

```python
from src.models.planning_model import TaskStep

step = TaskStep(
    step_id="step_001",
    title="Установка пакетов",
    description="Установка PostgreSQL пакетов",
    status="pending",
    error_count=0,
    metadata={}
)
```

### CommandResult

```python
from src.models.command_result import CommandResult

result = CommandResult(
    command="apt-get install postgresql",
    exit_code=0,
    stdout="Reading package lists...",
    stderr="",
    duration=5.2,
    success=True,
    error_count=0,
    retry_count=0,
    auto_corrections=[]
)
```

## Обработка ошибок

### ErrorHandler

```python
from src.agents.error_handler import ErrorHandler

error_handler = ErrorHandler(config, ssh_connector)

# Обработка ошибки шага
error_report = error_handler.handle_step_error(
    step_id="step_001",
    task=task,
    step_result=step_result
)

# Обработка завершения задачи
final_report = error_handler.handle_task_completion(
    task=task,
    execution_result=execution_result
)
```

### ErrorReport

```python
{
    "report_id": str,           # ID отчета
    "report_type": str,         # Тип отчета
    "timestamp": str,           # Время создания (ISO)
    "task_id": str,             # ID задачи
    "step_id": str,             # ID шага
    "error_count": int,         # Количество ошибок
    "details": Dict,            # Детали ошибки
    "server_snapshot": Dict,    # Снимок состояния сервера
    "recommendations": List[str] # Рекомендации
}
```

## Система идемпотентности

### IdempotencySystem

```python
from src.utils.idempotency_system import IdempotencySystem

idempotency = IdempotencySystem(ssh_connector, config)

# Создание снимка состояния
snapshot = idempotency.create_state_snapshot("task_001")

# Генерация идемпотентной команды
cmd, checks = idempotency.generate_idempotent_command(
    "apt-get install nginx",
    "install_package",
    "nginx"
)

# Проверка необходимости выполнения
should_skip = idempotency.should_skip_command(cmd, checks)

# Восстановление состояния
idempotency.restore_state_snapshot(snapshot)
```

## CLI Интерфейс

### Команды

```bash
# Выполнение задачи
ssh-agent execute "Установить nginx" --server-config config/server.yaml

# Dry-run режим
ssh-agent execute "Настроить SSL" --dry-run

# Интерактивный режим
ssh-agent interactive

# Показать статус
ssh-agent status

# Показать историю
ssh-agent history --limit 5

# Очистка данных
ssh-agent cleanup --days 7

# Инициализация конфигурации
ssh-agent init
```

### Опции

- `--server-config` - путь к конфигурации сервера
- `--agent-config` - путь к конфигурации агентов
- `--dry-run` - режим предварительного просмотра
- `--limit` - количество записей для показа
- `--days` - количество дней для хранения данных

## Примеры использования

### Базовое использование

```python
import asyncio
from src.main import SSHAgent

async def main():
    agent = SSHAgent(
        server_config_path="config/server_config.yaml",
        agent_config_path="config/agent_config.yaml"
    )
    
    result = await agent.execute_task("Установить и настроить nginx")
    
    if result["success"]:
        print(f"Задача выполнена успешно!")
        print(f"Время выполнения: {result['execution_duration']:.2f}с")
        print(f"Шагов выполнено: {result['steps_completed']}/{result['total_steps']}")
    else:
        print(f"Ошибка выполнения: {result.get('error', 'Неизвестная ошибка')}")

asyncio.run(main())
```

### Расширенное использование

```python
import asyncio
from src.main import SSHAgent

async def main():
    # Кастомная конфигурация
    config = {
        "server": {
            "host": "production-server.com",
            "username": "deploy",
            "auth_method": "key",
            "key_path": "/home/user/.ssh/id_rsa",
            "os_type": "ubuntu",
            "forbidden_commands": ["rm -rf /", "dd if=/dev/zero"]
        },
        "agents": {
            "executor": {
                "max_retries_per_command": 3,
                "auto_correction_enabled": True,
                "dry_run_mode": False
            },
            "error_handler": {
                "error_threshold_per_step": 3,
                "human_escalation_threshold": 2
            },
            "llm": {
                "api_key": "your-openai-api-key",
                "model": "gpt-4",
                "temperature": 0.1
            }
        }
    }
    
    agent = SSHAgent(config=config)
    
    # Выполнение с dry-run
    dry_run_result = await agent.execute_task(
        "Настроить веб-сервер с SSL",
        dry_run=True
    )
    
    print("Dry-run результат:")
    print(f"Шагов запланировано: {dry_run_result['total_steps']}")
    
    # Реальное выполнение
    if input("Выполнить задачу? (y/n): ").lower() == 'y':
        result = await agent.execute_task("Настроить веб-сервер с SSL")
        
        # Получение статуса
        status = agent.get_agent_status()
        print(f"Статистика агента: {status['agent_stats']}")
        
        # Получение истории
        history = agent.get_execution_history(5)
        print(f"Последние 5 задач: {len(history)}")

asyncio.run(main())
```

### Обработка ошибок

```python
import asyncio
from src.main import SSHAgent

async def main():
    agent = SSHAgent()
    
    try:
        result = await agent.execute_task("Установить несуществующий пакет")
        
        if not result["success"]:
            print(f"Задача провалена: {result.get('error')}")
            
            # Получение детального отчета
            if result.get("final_report"):
                report = result["final_report"]
                print(f"Отчет об ошибке: {report['report_id']}")
                print(f"Рекомендации: {report.get('recommendations', [])}")
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    
    finally:
        # Очистка старых данных
        agent.cleanup_old_data(days=7)

asyncio.run(main())
```

## Логирование

Система использует структурированное логирование с различными уровнями:

- **DEBUG** - детальная отладочная информация
- **INFO** - общая информация о работе
- **WARNING** - предупреждения и эскалации
- **ERROR** - ошибки выполнения
- **CRITICAL** - критические ошибки

```python
from src.utils.logger import StructuredLogger

logger = StructuredLogger("MyModule")
logger.info("Выполнение задачи", task_id="task_001", step="install_packages")
logger.warning("Эскалация к планировщику", error_count=5)
logger.error("Ошибка выполнения", error="Connection timeout")
```

## Безопасность

### Запрещенные команды

Система автоматически блокирует выполнение опасных команд:

```python
forbidden_commands = [
    "rm -rf /",
    "dd if=/dev/zero",
    "mkfs",
    "fdisk",
    "parted",
    "mkfs.ext4 /dev/sda1"
]
```

### Dry-run режим

Всегда тестируйте команды в dry-run режиме перед реальным выполнением:

```python
# Предварительный просмотр
result = await agent.execute_task("Опасная операция", dry_run=True)
print(f"Будет выполнено {result['total_steps']} шагов")

# Реальное выполнение только после проверки
if result["total_steps"] > 0:
    real_result = await agent.execute_task("Опасная операция")
```

### Валидация команд

```python
from src.utils.validator import CommandValidator

validator = CommandValidator(config)
is_safe = validator.validate_command("apt-get install nginx")
if not is_safe:
    print("Команда не прошла валидацию")
```

## Производительность

### Оптимизация

- Используйте кэширование для повторных операций
- Настройте таймауты для SSH соединений
- Ограничьте количество параллельных операций
- Регулярно очищайте старые данные

### Мониторинг

```python
# Получение статистики
status = agent.get_agent_status()
print(f"Среднее время выполнения: {status['agent_stats']['total_execution_time'] / status['agent_stats']['tasks_executed']:.2f}с")

# Мониторинг ошибок
if status['agent_stats']['total_errors'] > 10:
    print("Высокий уровень ошибок!")
```

## Расширение функциональности

### Создание кастомных агентов

```python
from src.agents.task_agent import TaskAgent

class CustomTaskAgent(TaskAgent):
    def plan_task(self, task_description, context):
        # Кастомная логика планирования
        return super().plan_task(task_description, context)
```

### Добавление новых стратегий автокоррекции

```python
from src.utils.autocorrection import AutocorrectionSystem

class CustomAutocorrection(AutocorrectionSystem):
    def apply_correction_strategy(self, command, error_output):
        # Кастомная стратегия исправления
        return self._custom_fix(command, error_output)
```

## Поддержка

Для получения помощи:

1. Проверьте документацию в папке `docs/`
2. Изучите примеры в папке `examples/`
3. Создайте issue в репозитории
4. Обратитесь к логам для диагностики проблем
