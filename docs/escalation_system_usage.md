# Система эскалации - Шаг 4.2

## Обзор

Система эскалации реализует Шаг 4.2 из плана реализации и включает в себя:

1. **Отправку логов планировщику при превышении порога**
2. **Механизм пересмотра планов**
3. **Систему эскалации к человеку-оператору**

## Архитектура

### Основные компоненты

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Error Handler │───▶│ Escalation System│───▶│ Human Operator      │
│                 │    │                  │    │ System              │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Task Agent    │    │ Plan Revision    │    │ Notifications       │
│                 │    │ System           │    │ (Email, Webhook,    │
└─────────────────┘    └──────────────────┘    │  Console, Log)      │
                                               └─────────────────────┘
```

### Типы эскалации

1. **PLANNER_NOTIFICATION** - Уведомление планировщика
2. **PLAN_REVISION** - Пересмотр плана
3. **HUMAN_ESCALATION** - Эскалация к человеку
4. **EMERGENCY_STOP** - Экстренная остановка

## Конфигурация

### agent_config.yaml

```yaml
agents:
  error_handler:
    error_threshold_per_step: 4
    send_to_planner_after_threshold: true
    human_escalation_threshold: 3
    max_error_reports: 10
    enable_error_tracking: true
    max_retention_days: 7
    track_error_patterns: true
    enable_escalation: true
    escalation_cooldown_minutes: 5
```

### Конфигурация оператора

```yaml
operator:
  email_notifications:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: "your-email@gmail.com"
    password: "your-password"
    from_address: "alerts@yourcompany.com"
    to_addresses: ["operator@yourcompany.com"]
  
  webhook_notifications:
    enabled: true
    url: "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
    headers:
      Content-Type: "application/json"
    timeout: 30
  
  console_notifications:
    enabled: true
```

## Использование

### Базовое использование

```python
from src.config.agent_config import AgentConfig
from src.agents.error_handler import ErrorHandler
from src.agents.escalation_system import EscalationSystem
from src.agents.human_operator_system import HumanOperatorSystem
from src.agents.task_agent import TaskAgent
from src.agents.subtask_agent import SubtaskAgent

# Создание конфигурации
config = AgentConfig()

# Инициализация компонентов
error_handler = ErrorHandler(config)
task_agent = TaskAgent(config)
subtask_agent = SubtaskAgent(config)
escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)

# Настройка системы оператора
operator_config = {
    "email_notifications": {
        "enabled": True,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "your-email@gmail.com",
        "password": "your-password",
        "from_address": "alerts@yourcompany.com",
        "to_addresses": ["operator@yourcompany.com"]
    },
    "console_notifications": {
        "enabled": True
    }
}

human_operator_system = HumanOperatorSystem(operator_config)

# Установка системы эскалации
error_handler.set_escalation_system(escalation_system)

# Регистрация колбэков
def handle_human_escalation(escalation_request):
    notification = human_operator_system.handle_escalation(escalation_request)
    print(f"Уведомление создано: {notification.notification_id}")

escalation_system.register_human_escalation_callback(handle_human_escalation)
```

### Обработка эскалации

```python
# Симуляция ошибок
error_count = 5
error_details = {
    "recent_errors": [
        {
            "command": "apt install postgresql",
            "error_message": "package not found",
            "timestamp": datetime.now().isoformat()
        }
    ]
}

# Обработка эскалации
escalation_request = escalation_system.handle_escalation(
    step_id="step_1",
    task=task,
    error_count=error_count,
    error_details=error_details
)

if escalation_request:
    print(f"Эскалация создана: {escalation_request.escalation_id}")
    print(f"Тип: {escalation_request.escalation_type.value}")
    print(f"Причина: {escalation_request.reason}")
```

### Разрешение эскалации

```python
# Разрешение эскалации
resolution = "Проблема решена: добавлены права sudo для пользователя"
success = escalation_system.resolve_escalation(
    escalation_request.escalation_id,
    resolution
)

if success:
    print("Эскалация успешно разрешена")
```

### Работа с оператором

```python
# Подтверждение уведомления
success = human_operator_system.acknowledge_notification(
    notification_id="notification_123",
    operator_id="operator_1"
)

# Разрешение уведомления
success = human_operator_system.resolve_notification(
    notification_id="notification_123",
    operator_id="operator_1",
    resolution_notes="Проблема решена через перезапуск сервиса"
)
```

## Пороги эскалации

### Настройка порогов

```python
escalation_config = {
    "planner_notification_threshold": 4,      # Уведомление планировщика
    "plan_revision_threshold": 5,             # Пересмотр плана
    "human_escalation_threshold": 3,          # Эскалация к человеку
    "emergency_stop_threshold": 5,            # Экстренная остановка
    "escalation_cooldown_minutes": 5,         # Cooldown между эскалациями
    "max_concurrent_escalations": 5,          # Максимум одновременных эскалаций
    "auto_resolve_timeout_hours": 24          # Авторазрешение через 24 часа
}
```

### Логика эскалации

```
Количество ошибок → Тип эскалации
─────────────────────────────────
0-3 ошибки        → Нет эскалации
4 ошибки          → Уведомление планировщика
5 ошибок          → Пересмотр плана
3+ ошибок         → Эскалация к человеку
5+ ошибок         → Экстренная остановка
```

## Методы уведомления

### Email уведомления

```python
email_config = {
    "enabled": True,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-email@gmail.com",
    "password": "your-password",
    "from_address": "alerts@yourcompany.com",
    "to_addresses": ["operator@yourcompany.com", "admin@yourcompany.com"]
}
```

### Webhook уведомления

```python
webhook_config = {
    "enabled": True,
    "url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
    "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-token"
    },
    "timeout": 30
}
```

### Консольные уведомления

```python
console_config = {
    "enabled": True  # Всегда включены для отладки
}
```

## Мониторинг и статистика

### Получение статистики эскалаций

```python
stats = escalation_system.get_escalation_stats()
print(f"Всего эскалаций: {stats['total_escalations']}")
print(f"Уведомления планировщику: {stats['planner_notifications']}")
print(f"Пересмотры планов: {stats['plan_revisions']}")
print(f"Эскалации к человеку: {stats['human_escalations']}")
print(f"Экстренные остановки: {stats['emergency_stops']}")
print(f"Разрешенные эскалации: {stats['resolved_escalations']}")
```

### Получение статистики оператора

```python
operator_stats = human_operator_system.get_operator_stats()
print(f"Всего уведомлений: {operator_stats['total_notifications']}")
print(f"Подтвержденные уведомления: {operator_stats['acknowledged_notifications']}")
print(f"Разрешенные уведомления: {operator_stats['resolved_notifications']}")
print(f"Ожидающие уведомления: {operator_stats['pending_notifications']}")
```

### Активные эскалации

```python
active_escalations = escalation_system.get_active_escalations()
for escalation in active_escalations:
    print(f"ID: {escalation['escalation_id']}")
    print(f"Тип: {escalation['escalation_type']}")
    print(f"Статус: {escalation['status']}")
    print(f"Причина: {escalation['reason']}")
```

## Пересмотр планов

### Анализ ошибок для пересмотра

Система автоматически анализирует ошибки и предлагает изменения:

```python
# Пример предложений по изменению плана
suggested_changes = [
    "Добавить проверку прав доступа перед выполнением команд",
    "Использовать sudo для команд, требующих повышенных прав",
    "Проверить владельца файлов и директорий",
    "Добавить проверку установки необходимых пакетов",
    "Обновить PATH переменную окружения",
    "Установить отсутствующие зависимости"
]
```

### Создание запроса на пересмотр

```python
revision_request = PlanRevisionRequest(
    revision_id="revision_123",
    task_id="task_456",
    step_id="step_789",
    original_plan=plan_data,
    error_analysis=error_analysis,
    suggested_changes=suggested_changes,
    priority="high",
    timestamp=datetime.now()
)
```

## Обработка ошибок

### Типы ошибок

Система классифицирует ошибки по типам:

- `permission_denied` - Ошибки прав доступа
- `command_not_found` - Команды не найдены
- `connection_error` - Ошибки соединения
- `syntax_error` - Синтаксические ошибки
- `file_not_found` - Файлы не найдены
- `package_error` - Ошибки пакетов
- `service_error` - Ошибки сервисов

### Анализ паттернов

```python
# Получение паттернов ошибок
patterns = error_handler.analyze_error_patterns(time_window_hours=24)
for pattern in patterns:
    print(f"Паттерн: {pattern.pattern_name}")
    print(f"Частота: {pattern.frequency}")
    print(f"Затронутые шаги: {pattern.affected_steps}")
    print(f"Предложенные решения: {pattern.suggested_solutions}")
```

## Очистка данных

### Очистка старых эскалаций

```python
# Очистка эскалаций старше 7 дней
escalation_system.cleanup_old_escalations(days=7)
```

### Очистка старых уведомлений

```python
# Очистка уведомлений старше 30 дней
human_operator_system.cleanup_old_notifications(days=30)
```

## Примеры использования

### Полный пример

```python
#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.agent_config import AgentConfig
from agents.error_handler import ErrorHandler
from agents.escalation_system import EscalationSystem
from agents.human_operator_system import HumanOperatorSystem
from agents.task_agent import TaskAgent
from agents.subtask_agent import SubtaskAgent
from models.planning_model import Task, TaskStep, Priority

def main():
    # Конфигурация
    config = AgentConfig()
    
    # Инициализация компонентов
    error_handler = ErrorHandler(config)
    task_agent = TaskAgent(config)
    subtask_agent = SubtaskAgent(config)
    escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)
    
    # Система оператора
    operator_config = {
        "email_notifications": {"enabled": False},
        "console_notifications": {"enabled": True}
    }
    human_operator_system = HumanOperatorSystem(operator_config)
    
    # Установка системы эскалации
    error_handler.set_escalation_system(escalation_system)
    
    # Регистрация колбэков
    def handle_human_escalation(escalation_request):
        notification = human_operator_system.handle_escalation(escalation_request)
        print(f"Уведомление создано: {notification.notification_id}")
    
    escalation_system.register_human_escalation_callback(handle_human_escalation)
    
    # Создание тестовой задачи
    task = Task(title="Тестовая задача", description="Описание задачи")
    step = TaskStep(title="Тестовый шаг", description="Описание шага", priority=Priority.HIGH)
    task.add_step(step)
    
    # Симуляция ошибок
    for i in range(5):
        error_handler.error_tracker.record_error(
            step_id=step.step_id,
            command=f"test_command_{i}",
            error_message=f"Error {i}: permission denied",
            exit_code=1
        )
    
    # Обработка эскалации
    error_details = {"recent_errors": []}
    escalation_request = escalation_system.handle_escalation(
        step_id=step.step_id,
        task=task,
        error_count=5,
        error_details=error_details
    )
    
    if escalation_request:
        print(f"Эскалация создана: {escalation_request.escalation_id}")
        print(f"Тип: {escalation_request.escalation_type.value}")
        
        # Разрешение эскалации
        escalation_system.resolve_escalation(
            escalation_request.escalation_id,
            "Проблема решена"
        )
        print("Эскалация разрешена")

if __name__ == "__main__":
    main()
```

## Лучшие практики

### 1. Настройка порогов

- Установите разумные пороги для каждого типа эскалации
- Учитывайте специфику ваших задач и среды
- Регулярно пересматривайте пороги на основе статистики

### 2. Мониторинг

- Регулярно проверяйте статистику эскалаций
- Настройте алерты для критических ситуаций
- Ведите журнал всех эскалаций и их разрешений

### 3. Уведомления

- Настройте несколько методов уведомления для надежности
- Используйте приоритизацию уведомлений
- Настройте cooldown для предотвращения спама

### 4. Разрешение эскалаций

- Всегда документируйте причины и решения
- Анализируйте паттерны ошибок для предотвращения
- Регулярно очищайте старые данные

## Устранение неполадок

### Частые проблемы

1. **Эскалации не создаются**
   - Проверьте настройки порогов
   - Убедитесь что система эскалации установлена
   - Проверьте логи на ошибки

2. **Уведомления не отправляются**
   - Проверьте конфигурацию email/webhook
   - Убедитесь в правильности учетных данных
   - Проверьте сетевое соединение

3. **Cooldown блокирует эскалации**
   - Уменьшите время cooldown
   - Проверьте активные эскалации
   - Очистите старые эскалации

### Логирование

Все действия системы эскалации логируются с соответствующими уровнями:

- `INFO` - Обычные операции
- `WARNING` - Предупреждения
- `ERROR` - Ошибки
- `CRITICAL` - Критические ситуации

## Заключение

Система эскалации обеспечивает надежную обработку ошибок и автоматическую эскалацию критических ситуаций. Она интегрируется со всеми компонентами системы и предоставляет гибкие настройки для различных сценариев использования.

Ключевые преимущества:
- Автоматическая эскалация по порогам
- Множественные методы уведомления
- Анализ паттернов ошибок
- Пересмотр планов
- Подробная статистика и мониторинг
