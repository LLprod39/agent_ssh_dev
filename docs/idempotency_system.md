# Система идемпотентности

## Обзор

Система идемпотентности обеспечивает безопасное повторное выполнение операций без побочных эффектов. Это критически важно для автоматизации, где команды могут выполняться несколько раз из-за ошибок, перезапусков или повторных попыток.

## Основные компоненты

### 1. IdempotencySystem

Главный класс системы идемпотентности, который обеспечивает:

- **Генерацию идемпотентных команд** - преобразование обычных команд в безопасные для повторного выполнения
- **Проверки состояния** - анализ текущего состояния системы перед выполнением команд
- **Систему отката** - создание и выполнение команд для отмены изменений
- **Кэширование проверок** - оптимизация производительности через кэш результатов

### 2. IdempotencyCheck

Представляет отдельную проверку идемпотентности:

```python
@dataclass
class IdempotencyCheck:
    check_type: IdempotencyCheckType
    target: str  # Файл, сервис, пакет и т.д.
    expected_state: Any  # Ожидаемое состояние
    check_command: str  # Команда для проверки
    success_pattern: str  # Паттерн успешного результата
    description: str = ""
    timeout: int = 30
    retry_count: int = 3
```

### 3. StateSnapshot

Снимок состояния системы в определенный момент времени:

```python
@dataclass
class StateSnapshot:
    snapshot_id: str
    timestamp: datetime
    checks: List[IdempotencyResult]
    system_info: Dict[str, Any]
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    services_started: List[str] = field(default_factory=list)
    packages_installed: List[str] = field(default_factory=list)
    users_created: List[str] = field(default_factory=list)
    groups_created: List[str] = field(default_factory=list)
```

## Типы проверок идемпотентности

Система поддерживает следующие типы проверок:

- `FILE_EXISTS` - существование файла
- `DIRECTORY_EXISTS` - существование директории
- `SERVICE_RUNNING` - запуск сервиса
- `PACKAGE_INSTALLED` - установка пакета
- `USER_EXISTS` - существование пользователя
- `GROUP_EXISTS` - существование группы
- `PORT_OPEN` - открытый порт
- `PROCESS_RUNNING` - запущенный процесс
- `CONFIG_EXISTS` - существование конфигурации
- `CUSTOM_CHECK` - пользовательская проверка

## Генерация идемпотентных команд

### Примеры преобразований

| Исходная команда | Идемпотентная команда |
|------------------|----------------------|
| `apt-get install nginx` | `dpkg -l \| grep -q '^ii  nginx' \|\| apt-get install -y nginx` |
| `touch /tmp/file.txt` | `test -f /tmp/file.txt \|\| (mkdir -p $(dirname /tmp/file.txt) && touch /tmp/file.txt)` |
| `mkdir -p /tmp/dir` | `test -d /tmp/dir \|\| mkdir -p /tmp/dir` |
| `systemctl start nginx` | `systemctl is-active --quiet nginx \|\| systemctl start nginx` |
| `useradd testuser` | `id testuser >/dev/null 2>&1 \|\| useradd testuser` |

### Логика преобразования

1. **Проверка состояния** - команда проверяет, достигнуто ли уже желаемое состояние
2. **Условное выполнение** - основная команда выполняется только если состояние не достигнуто
3. **Безопасность** - добавление проверок безопасности и обработки ошибок

## Интеграция с компонентами системы

### ExecutionModel

```python
# Создание снимка состояния
snapshot = execution_model.create_idempotency_snapshot("task_001")

# Генерация идемпотентной команды
cmd, checks = execution_model.generate_idempotent_command(
    "apt-get install nginx", "install_package", "nginx"
)

# Проверка необходимости пропуска команды
should_skip = execution_model.check_command_idempotency("apt-get install nginx", checks)

# Выполнение отката
results = execution_model.execute_idempotency_rollback(snapshot.snapshot_id)
```

### SubtaskAgent

```python
# Улучшение подзадачи идемпотентностью
enhanced_subtask = subtask_agent.enhance_subtask_with_idempotency(subtask)

# Генерация идемпотентных команд
idempotent_commands = subtask_agent.generate_idempotent_commands(subtask)
```

## Конфигурация

### IdempotencyConfig

```yaml
idempotency:
  enabled: true
  cache_ttl: 300  # Время жизни кэша в секундах
  max_snapshots: 10  # Максимальное количество снимков
  auto_rollback: true  # Автоматический откат при ошибках
  check_timeout: 30  # Таймаут проверок в секундах
  
  # Настройки проверок
  enable_package_checks: true
  enable_file_checks: true
  enable_directory_checks: true
  enable_service_checks: true
  enable_user_checks: true
  enable_group_checks: true
  enable_port_checks: true
  
  # Настройки отката
  rollback_on_failure: true
  rollback_timeout: 60
  preserve_snapshots: true
  
  # Настройки логирования
  log_checks: true
  log_skips: true
  log_rollbacks: true
```

## Примеры использования

### Базовое использование

```python
from src.utils.idempotency_system import IdempotencySystem
from src.connectors.ssh_connector import SSHConnector

# Создание системы идемпотентности
ssh_connector = SSHConnector(server_config)
idempotency_system = IdempotencySystem(ssh_connector, config)

# Создание снимка состояния
snapshot = idempotency_system.create_state_snapshot("task_001")

# Генерация идемпотентной команды
cmd, checks = idempotency_system.generate_idempotent_command(
    "apt-get install nginx", "install_package", "nginx"
)

# Проверка идемпотентности
results = idempotency_system.check_idempotency(checks)

# Проверка необходимости пропуска команды
should_skip = idempotency_system.should_skip_command(cmd, checks)
```

### Интеграция с планированием задач

```python
from src.agents.subtask_agent import SubtaskAgent

# Создание агента с поддержкой идемпотентности
subtask_agent = SubtaskAgent(config, ssh_connector=ssh_connector)

# Планирование подзадач (автоматически применяется идемпотентность)
result = subtask_agent.plan_subtasks(step, context)

# Подзадачи уже содержат идемпотентные команды
for subtask in result.subtasks:
    print(f"Команды: {subtask.commands}")
    print(f"Проверки: {subtask.metadata.get('idempotency_checks', [])}")
```

### Система отката

```python
# Создание снимка перед выполнением
snapshot = idempotency_system.create_state_snapshot("risky_task")

try:
    # Выполнение операций
    execute_risky_operations()
except Exception as e:
    # Откат к предыдущему состоянию
    rollback_results = idempotency_system.execute_rollback(snapshot.snapshot_id)
    print(f"Откат выполнен: {len(rollback_results)} команд")
```

## Лучшие практики

### 1. Создание снимков состояния

- Создавайте снимки перед выполнением критических операций
- Используйте описательные идентификаторы снимков
- Очищайте старые снимки для экономии памяти

### 2. Генерация идемпотентных команд

- Всегда проверяйте состояние перед выполнением операций
- Используйте атомарные команды проверки
- Добавляйте обработку ошибок в команды

### 3. Система отката

- Создавайте снимки перед необратимыми операциями
- Тестируйте команды отката в безопасной среде
- Документируйте порядок выполнения команд отката

### 4. Производительность

- Используйте кэширование для часто выполняемых проверок
- Ограничивайте количество снимков состояния
- Настраивайте таймауты для проверок

## Отладка и мониторинг

### Логирование

Система предоставляет детальное логирование:

```python
# Включение логирования проверок
config.idempotency.log_checks = True

# Включение логирования пропусков команд
config.idempotency.log_skips = True

# Включение логирования откатов
config.idempotency.log_rollbacks = True
```

### Статистика

```python
# Получение статуса системы
status = idempotency_system.get_system_status()
print(f"Снимков: {status['snapshots_count']}")
print(f"Размер кэша: {status['cache_size']}")
print(f"Текущий снимок: {status['current_snapshot']}")
```

### Тестирование

```python
# Запуск тестов
pytest tests/test_utils/test_idempotency_system.py -v

# Тесты интеграции
pytest tests/test_models/test_execution_model_idempotency.py -v
pytest tests/test_agents/test_subtask_agent_idempotency.py -v
```

## Ограничения и известные проблемы

### 1. Производительность

- Проверки идемпотентности добавляют накладные расходы
- Кэширование помогает, но не устраняет полностью
- Рекомендуется использовать для критических операций

### 2. Сложность команд

- Не все команды можно легко сделать идемпотентными
- Требуется глубокое понимание логики команд
- Может потребоваться ручная настройка для сложных случаев

### 3. Состояние системы

- Проверки основаны на текущем состоянии системы
- Изменения между проверками могут привести к неожиданным результатам
- Рекомендуется выполнять проверки непосредственно перед выполнением команд

## Заключение

Система идемпотентности значительно повышает надежность автоматизации, обеспечивая:

- **Безопасность** - предотвращение побочных эффектов при повторном выполнении
- **Надежность** - возможность восстановления после ошибок
- **Предсказуемость** - одинаковый результат при многократном выполнении
- **Отладку** - возможность отката к предыдущему состоянию

Использование системы идемпотентности особенно важно для продакшн-сред, где стабильность и предсказуемость критически важны.
