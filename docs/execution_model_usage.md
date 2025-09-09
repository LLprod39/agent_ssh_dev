# Execution Model - Руководство по использованию

## Обзор

Execution Model - это ключевой компонент системы SSH Agent, отвечающий за выполнение команд на удаленных серверах. Он обеспечивает надежное выполнение подзадач с автоматической коррекцией ошибок, сбором результатов и интеграцией с Task Master.

## Основные возможности

### 1. Выполнение команд
- Выполнение команд через SSH соединение
- Сбор stdout, stderr и exit codes
- Обработка таймаутов
- Поддержка dry-run режима

### 2. Последовательное выполнение подзадач
- Выполнение команд в правильном порядке
- Обработка зависимостей между командами
- Прерывание при критических ошибках

### 3. Автокоррекция ошибок
- Автоматическое исправление типичных ошибок
- Добавление sudo для команд, требующих привилегий
- Обновление пакетов перед установкой
- Проверка сетевого соединения

### 4. Health-check команды
- Выполнение проверок работоспособности
- Валидация результатов выполнения
- Автоматические проверки для различных типов команд

### 5. Интеграция с Task Master
- Отправка прогресса выполнения
- Отчеты об ошибках
- Трекинг статистики

## Архитектура

### Основные классы

#### ExecutionModel
Главный класс для выполнения команд и подзадач.

```python
from models.execution_model import ExecutionModel
from config.agent_config import AgentConfig
from connectors.ssh_connector import SSHConnector

# Создание Execution Model
config = AgentConfig.from_yaml("config/agent_config.yaml")
ssh_connector = SSHConnector()
execution_model = ExecutionModel(config, ssh_connector)
```

#### CommandResult
Результат выполнения одной команды.

```python
@dataclass
class CommandResult:
    command: str
    success: bool
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration: Optional[float] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    retry_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### SubtaskExecutionResult
Результат выполнения подзадачи.

```python
@dataclass
class SubtaskExecutionResult:
    subtask_id: str
    success: bool
    commands_results: List[CommandResult] = field(default_factory=list)
    health_check_results: List[CommandResult] = field(default_factory=list)
    total_duration: Optional[float] = None
    error_count: int = 0
    autocorrection_applied: bool = False
    rollback_executed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### ExecutionContext
Контекст выполнения подзадачи.

```python
@dataclass
class ExecutionContext:
    subtask: Subtask
    ssh_connection: SSHConnection
    server_info: Dict[str, Any]
    environment: Dict[str, Any]
    progress_callback: Optional[Callable] = None
    task_master: Optional[TaskMasterIntegration] = None
```

## Использование

### Базовое использование

```python
from models.execution_model import ExecutionModel, ExecutionContext
from agents.subtask_agent import Subtask

# Создание подзадачи
subtask = Subtask(
    subtask_id="install_nginx",
    title="Установка Nginx",
    description="Установить и настроить Nginx",
    commands=[
        "sudo apt update",
        "sudo apt install -y nginx",
        "sudo systemctl start nginx",
        "sudo systemctl enable nginx"
    ],
    health_checks=[
        "systemctl is-active nginx",
        "curl -I http://localhost"
    ],
    rollback_commands=[
        "sudo systemctl stop nginx",
        "sudo apt remove -y nginx"
    ]
)

# Создание контекста выполнения
context = ExecutionContext(
    subtask=subtask,
    ssh_connection=ssh_connection,
    server_info={"os": "ubuntu", "version": "20.04"},
    environment={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
)

# Выполнение подзадачи
result = execution_model.execute_subtask(context)

# Проверка результата
if result.success:
    print(f"Подзадача выполнена успешно за {result.total_duration:.2f} секунд")
    for cmd_result in result.commands_results:
        print(f"✓ {cmd_result.command}")
else:
    print(f"Подзадача не выполнена. Ошибок: {result.error_count}")
    for cmd_result in result.commands_results:
        if not cmd_result.success:
            print(f"✗ {cmd_result.command}: {cmd_result.error_message}")
```

### Dry-run режим

```python
# Включение dry-run режима
config.executor.dry_run_mode = True
execution_model = ExecutionModel(config, ssh_connector)

# В dry-run режиме команды не выполняются реально
result = execution_model.execute_subtask(context)
print("Команды выполнены в режиме симуляции")
```

### Автокоррекция

```python
# Включение автокоррекции
config.executor.auto_correction_enabled = True
config.executor.max_retries_per_command = 2

execution_model = ExecutionModel(config, ssh_connector)

# При ошибке "permission denied" команда автоматически исправится на "sudo command"
# При ошибке "package not found" добавится "apt update &&"
result = execution_model.execute_subtask(context)
```

### Интеграция с Task Master

```python
from agents.task_master_integration import TaskMasterIntegration

# Создание Task Master интеграции
task_master = TaskMasterIntegration(config)

# Создание Execution Model с Task Master
execution_model = ExecutionModel(config, ssh_connector, task_master)

# Task Master будет получать отчеты о прогрессе
context = ExecutionContext(
    subtask=subtask,
    ssh_connection=ssh_connection,
    server_info=server_info,
    environment=environment,
    task_master=task_master
)

result = execution_model.execute_subtask(context)
```

## Конфигурация

### ExecutorConfig

```yaml
agents:
  executor:
    max_retries_per_command: 2          # Максимальное количество повторов
    auto_correction_enabled: true       # Включить автокоррекцию
    dry_run_mode: false                 # Режим симуляции
    command_timeout: 30                 # Таймаут команды в секундах
```

### Параметры автокоррекции

Execution Model автоматически исправляет следующие типы ошибок:

1. **Permission denied** - добавляет `sudo` к команде
2. **Command not found** - добавляет `sudo` для системных команд
3. **Package not found** - добавляет `apt update &&` перед установкой
4. **Service not found** - проверяет наличие сервиса
5. **Connection refused** - проверяет сетевое соединение
6. **No such file or directory** - создает необходимые директории

## Безопасность

### Проверка опасных команд

Execution Model автоматически блокирует выполнение опасных команд:

```python
dangerous_commands = [
    "rm -rf /",
    "dd if=/dev/zero",
    "mkfs",
    "fdisk",
    "parted",
    "> /dev/sda",
    "chmod 777 /",
    "chown -R root:root /",
    "passwd root",
    "userdel -r",
    "groupdel",
    "killall -9",
    "pkill -9",
    "halt",
    "poweroff",
    "reboot",
    "shutdown"
]
```

### Критические команды

Некоторые команды считаются критическими, и при их неудаче выполнение прерывается:

```python
critical_commands = [
    "systemctl start",
    "systemctl enable", 
    "service start",
    "docker start",
    "nginx -t",
    "apache2ctl configtest"
]
```

## Статистика и мониторинг

### Получение статистики

```python
stats = execution_model.get_execution_stats()
print(f"Всего команд: {stats['total_commands']}")
print(f"Успешных: {stats['successful_commands']}")
print(f"Неудачных: {stats['failed_commands']}")
print(f"Процент успеха: {stats['success_rate']:.1f}%")
print(f"Средняя длительность: {stats['average_duration']:.2f} сек")
print(f"Попыток повтора: {stats['retry_attempts']}")
print(f"Автокоррекций: {stats['autocorrections']}")
```

### Сброс статистики

```python
execution_model.reset_stats()
```

## Обработка ошибок

### Типы ошибок

1. **Ошибки выполнения команды** - команда завершилась с ненулевым кодом
2. **Таймауты** - команда не завершилась в установленное время
3. **Ошибки SSH соединения** - проблемы с подключением к серверу
4. **Ошибки автокоррекции** - не удалось исправить команду

### Стратегии обработки

1. **Повторные попытки** - автоматический повтор команды
2. **Автокоррекция** - исправление команды на основе ошибки
3. **Откат** - выполнение rollback команд при неудаче
4. **Эскалация** - отправка ошибок в Task Master

## Примеры использования

### Установка веб-сервера

```python
subtask = Subtask(
    subtask_id="install_web_server",
    title="Установка веб-сервера",
    description="Установить Nginx с SSL сертификатом",
    commands=[
        "sudo apt update",
        "sudo apt install -y nginx certbot python3-certbot-nginx",
        "sudo systemctl start nginx",
        "sudo systemctl enable nginx",
        "sudo ufw allow 'Nginx Full'",
        "sudo certbot --nginx -d example.com --non-interactive --agree-tos --email admin@example.com"
    ],
    health_checks=[
        "systemctl is-active nginx",
        "curl -I http://example.com",
        "curl -I https://example.com",
        "nginx -t"
    ],
    rollback_commands=[
        "sudo systemctl stop nginx",
        "sudo systemctl disable nginx",
        "sudo ufw delete allow 'Nginx Full'"
    ],
    timeout=120
)
```

### Настройка базы данных

```python
subtask = Subtask(
    subtask_id="setup_database",
    title="Настройка PostgreSQL",
    description="Установить и настроить PostgreSQL",
    commands=[
        "sudo apt update",
        "sudo apt install -y postgresql postgresql-contrib",
        "sudo systemctl start postgresql",
        "sudo systemctl enable postgresql",
        "sudo -u postgres createuser --interactive",
        "sudo -u postgres createdb myapp"
    ],
    health_checks=[
        "systemctl is-active postgresql",
        "sudo -u postgres psql -c '\\l'",
        "sudo -u postgres psql -c 'SELECT version();'"
    ],
    rollback_commands=[
        "sudo systemctl stop postgresql",
        "sudo systemctl disable postgresql"
    ],
    timeout=60
)
```

## Лучшие практики

### 1. Структура команд
- Используйте атомарные команды
- Добавляйте проверки после каждой критической операции
- Включайте команды отката для необратимых операций

### 2. Health-check команды
- Проверяйте статус сервисов
- Тестируйте функциональность
- Валидируйте конфигурацию

### 3. Обработка ошибок
- Включайте автокоррекцию для типичных ошибок
- Настраивайте разумные таймауты
- Используйте rollback команды для критических операций

### 4. Безопасность
- Избегайте опасных команд
- Используйте sudo только когда необходимо
- Проверяйте команды перед выполнением

### 5. Мониторинг
- Отслеживайте статистику выполнения
- Логируйте все операции
- Интегрируйтесь с Task Master для отчетности

## Отладка

### Включение подробного логирования

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Execution Model будет выводить подробную информацию о выполнении
```

### Проверка результатов

```python
result = execution_model.execute_subtask(context)

# Детальная информация о каждой команде
for i, cmd_result in enumerate(result.commands_results, 1):
    print(f"Команда {i}: {cmd_result.command}")
    print(f"  Успех: {cmd_result.success}")
    print(f"  Код выхода: {cmd_result.exit_code}")
    print(f"  Длительность: {cmd_result.duration:.2f} сек")
    if cmd_result.stdout:
        print(f"  Вывод: {cmd_result.stdout}")
    if cmd_result.stderr:
        print(f"  Ошибка: {cmd_result.stderr}")
    print()
```

### Тестирование в dry-run режиме

```python
# Всегда тестируйте подзадачи в dry-run режиме перед реальным выполнением
config.executor.dry_run_mode = True
execution_model = ExecutionModel(config, ssh_connector)

result = execution_model.execute_subtask(context)
print("Тест в dry-run режиме завершен")
```
