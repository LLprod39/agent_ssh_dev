# Руководство по интеграции системы идемпотентности

## Быстрый старт

### 1. Установка и настройка

```python
from src.config.agent_config import AgentConfig
from src.connectors.ssh_connector import SSHConnector, ServerConfig
from src.utils.idempotency_system import IdempotencySystem

# Создание конфигурации
config = AgentConfig.from_yaml("config/idempotency_example.yaml")

# Создание SSH коннектора
server_config = ServerConfig(
    host="your-server.com",
    username="user",
    auth_method="key",
    key_path="~/.ssh/id_rsa"
)
ssh_connector = SSHConnector(server_config)

# Создание системы идемпотентности
idempotency_system = IdempotencySystem(ssh_connector, config.idempotency.dict())
```

### 2. Базовое использование

```python
# Создание снимка состояния
snapshot = idempotency_system.create_state_snapshot("my_task")

# Генерация идемпотентной команды
cmd, checks = idempotency_system.generate_idempotent_command(
    "apt-get install nginx", "install_package", "nginx"
)

# Проверка необходимости выполнения
should_skip = idempotency_system.should_skip_command(cmd, checks)

if not should_skip:
    # Выполнение команды
    result = ssh_connector.execute_command(cmd)
    print(f"Результат: {result.success}")
```

## Интеграция с существующими компонентами

### ExecutionModel

```python
from src.models.execution_model import ExecutionModel

# Создание ExecutionModel с поддержкой идемпотентности
execution_model = ExecutionModel(config, ssh_connector)

# Создание снимка перед выполнением задач
snapshot = execution_model.create_idempotency_snapshot("task_batch_001")

try:
    # Выполнение задач
    for task in tasks:
        result = execution_model.execute_subtask(context)
        if not result.success:
            break
except Exception as e:
    # Откат при ошибке
    rollback_results = execution_model.execute_idempotency_rollback(snapshot.snapshot_id)
    print(f"Выполнен откат: {len(rollback_results)} команд")
```

### SubtaskAgent

```python
from src.agents.subtask_agent import SubtaskAgent

# Создание SubtaskAgent с поддержкой идемпотентности
subtask_agent = SubtaskAgent(config, ssh_connector=ssh_connector)

# Планирование подзадач (автоматически применяется идемпотентность)
result = subtask_agent.plan_subtasks(step, context)

# Подзадачи уже содержат идемпотентные команды
for subtask in result.subtasks:
    print(f"Идемпотентные команды: {subtask.commands}")
    
    # Проверки идемпотентности доступны в метаданных
    checks = subtask.metadata.get('idempotency_checks', [])
    print(f"Проверки: {len(checks)}")
```

## Конфигурация

### YAML конфигурация

```yaml
# config/idempotency_example.yaml
idempotency:
  enabled: true
  cache_ttl: 300
  max_snapshots: 10
  auto_rollback: true
  check_timeout: 30
  
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

### Программная конфигурация

```python
idempotency_config = {
    "enabled": True,
    "cache_ttl": 300,
    "max_snapshots": 10,
    "auto_rollback": True,
    "check_timeout": 30,
    "enable_package_checks": True,
    "enable_file_checks": True,
    "enable_directory_checks": True,
    "enable_service_checks": True,
    "enable_user_checks": True,
    "enable_group_checks": True,
    "enable_port_checks": True,
    "rollback_on_failure": True,
    "rollback_timeout": 60,
    "preserve_snapshots": True,
    "log_checks": True,
    "log_skips": True,
    "log_rollbacks": True
}
```

## Примеры использования

### Установка пакетов

```python
# Обычная команда
command = "apt-get install nginx"

# Идемпотентная команда
idempotent_cmd, checks = idempotency_system.generate_idempotent_command(
    command, "install_package", "nginx"
)

print(f"Исходная: {command}")
print(f"Идемпотентная: {idempotent_cmd}")
# Вывод: dpkg -l | grep -q '^ii  nginx' || apt-get install -y nginx
```

### Создание файлов

```python
# Обычная команда
command = "touch /etc/nginx/nginx.conf"

# Идемпотентная команда
idempotent_cmd, checks = idempotency_system.generate_idempotent_command(
    command, "create_file", "/etc/nginx/nginx.conf"
)

print(f"Исходная: {command}")
print(f"Идемпотентная: {idempotent_cmd}")
# Вывод: test -f /etc/nginx/nginx.conf || (mkdir -p $(dirname /etc/nginx/nginx.conf) && touch /etc/nginx/nginx.conf)
```

### Управление сервисами

```python
# Обычная команда
command = "systemctl start nginx"

# Идемпотентная команда
idempotent_cmd, checks = idempotency_system.generate_idempotent_command(
    command, "start_service", "nginx"
)

print(f"Исходная: {command}")
print(f"Идемпотентная: {idempotent_cmd}")
# Вывод: systemctl is-active --quiet nginx || systemctl start nginx
```

## Система отката

### Создание снимка

```python
# Создание снимка перед выполнением операций
snapshot = idempotency_system.create_state_snapshot("web_server_setup")

# Выполнение операций
operations = [
    "apt-get update",
    "apt-get install nginx",
    "systemctl start nginx",
    "systemctl enable nginx"
]

for operation in operations:
    result = ssh_connector.execute_command(operation)
    if not result.success:
        print(f"Ошибка в операции: {operation}")
        break
```

### Выполнение отката

```python
# Откат к предыдущему состоянию
rollback_results = idempotency_system.execute_rollback(snapshot.snapshot_id)

print(f"Выполнено команд отката: {len(rollback_results)}")
for result in rollback_results:
    if result.success:
        print(f"✅ {result.command}")
    else:
        print(f"❌ {result.command} - {result.stderr}")
```

## Мониторинг и отладка

### Статистика системы

```python
# Получение статуса системы
status = idempotency_system.get_system_status()
print(f"Снимков состояния: {status['snapshots_count']}")
print(f"Размер кэша: {status['cache_size']}")
print(f"Текущий снимок: {status['current_snapshot']}")
print(f"TTL кэша: {status['cache_ttl']} сек")
```

### Логирование

```python
# Включение детального логирования
config.idempotency.log_checks = True
config.idempotency.log_skips = True
config.idempotency.log_rollbacks = True

# Логи будут содержать:
# - Детали проверок идемпотентности
# - Информацию о пропущенных командах
# - Результаты выполнения откатов
```

## Тестирование

### Запуск тестов

```bash
# Тесты системы идемпотентности
pytest tests/test_utils/test_idempotency_system.py -v

# Тесты интеграции с ExecutionModel
pytest tests/test_models/test_execution_model_idempotency.py -v

# Тесты интеграции с SubtaskAgent
pytest tests/test_agents/test_subtask_agent_idempotency.py -v

# Все тесты идемпотентности
pytest tests/ -k idempotency -v
```

### Пример теста

```python
def test_idempotency_integration():
    """Тест интеграции системы идемпотентности"""
    # Создание системы
    ssh_connector = MockSSHConnector()
    idempotency_system = IdempotencySystem(ssh_connector, config)
    
    # Создание снимка
    snapshot = idempotency_system.create_state_snapshot("test_task")
    assert snapshot is not None
    
    # Генерация идемпотентной команды
    cmd, checks = idempotency_system.generate_idempotent_command(
        "apt-get install nginx", "install_package", "nginx"
    )
    assert "dpkg -l | grep -q" in cmd
    assert len(checks) == 1
    
    # Проверка идемпотентности
    results = idempotency_system.check_idempotency(checks)
    assert len(results) == 1
```

## Лучшие практики

### 1. Планирование использования

- Определите критические операции, которые требуют идемпотентности
- Создавайте снимки состояния перед необратимыми операциями
- Используйте описательные идентификаторы для снимков

### 2. Конфигурация

- Настройте таймауты в соответствии с вашей инфраструктурой
- Включите логирование для отладки
- Ограничьте количество снимков для экономии памяти

### 3. Мониторинг

- Отслеживайте статистику системы идемпотентности
- Мониторьте производительность проверок
- Анализируйте логи для выявления проблем

### 4. Тестирование

- Создавайте тесты для критических сценариев
- Тестируйте систему отката в безопасной среде
- Проверяйте производительность под нагрузкой

## Устранение неполадок

### Частые проблемы

1. **Медленные проверки**
   - Увеличьте `check_timeout`
   - Оптимизируйте команды проверки
   - Используйте кэширование

2. **Неточные проверки**
   - Проверьте паттерны успешного результата
   - Убедитесь в корректности команд проверки
   - Добавьте дополнительные проверки

3. **Проблемы с откатом**
   - Проверьте порядок команд отката
   - Убедитесь в корректности команд отката
   - Тестируйте откат в изолированной среде

### Отладка

```python
# Включение детального логирования
import logging
logging.basicConfig(level=logging.DEBUG)

# Проверка состояния системы
status = idempotency_system.get_system_status()
print(f"Статус: {status}")

# Проверка кэша
print(f"Кэш: {idempotency_system.check_cache}")

# Проверка снимков
print(f"Снимки: {idempotency_system.state_snapshots}")
```

## Заключение

Система идемпотентности значительно повышает надежность автоматизации. Следуйте этому руководству для успешной интеграции и использования системы в ваших проектах.

Для получения дополнительной информации см.:
- [Полная документация системы идемпотентности](idempotency_system.md)
- [Примеры использования](examples/idempotency_example.py)
- [Тесты системы](tests/test_utils/test_idempotency_system.py)
