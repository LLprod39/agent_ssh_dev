# Система подсчета ошибок

## Обзор

Система подсчета ошибок (Error Tracking System) - это компонент SSH Agent, который обеспечивает:

- Подсчет ошибок на уровне шага
- Пороговые значения для эскалации
- Систему трекинга попыток
- Анализ паттернов ошибок
- Статистику выполнения

## Архитектура

### Основные компоненты

1. **ErrorTracker** - основной класс для управления системой подсчета ошибок
2. **ErrorRecord** - запись об ошибке с метаданными
3. **AttemptRecord** - запись о попытке выполнения команды
4. **StepErrorStats** - статистика ошибок для конкретного шага
5. **EscalationLevel** - уровни эскалации ошибок

### Уровни эскалации

```python
class EscalationLevel(Enum):
    NONE = "none"                           # Нет эскалации
    RETRY = "retry"                         # Повторная попытка
    AUTOCORRECTION = "autocorrection"       # Автокоррекция
    PLANNER_NOTIFICATION = "planner_notification"  # Уведомление планировщика
    HUMAN_ESCALATION = "human_escalation"   # Эскалация к человеку
```

### Серьезность ошибок

```python
class ErrorSeverity(Enum):
    LOW = "low"         # Низкая серьезность
    MEDIUM = "medium"   # Средняя серьезность
    HIGH = "high"       # Высокая серьезность
    CRITICAL = "critical"  # Критическая серьезность
```

## Конфигурация

### Параметры конфигурации

```yaml
error_handler:
  # Основные пороги
  error_threshold_per_step: 4        # Порог ошибок для эскалации к планировщику
  human_escalation_threshold: 3      # Порог для эскалации к человеку
  
  # Настройки системы подсчета ошибок
  enable_error_tracking: true        # Включить систему подсчета ошибок
  max_retention_days: 7              # Максимальное время хранения записей
  track_error_patterns: true         # Отслеживать паттерны ошибок
  enable_escalation: true            # Включить систему эскалации
  escalation_cooldown_minutes: 5     # Время ожидания между эскалациями
```

## Использование

### Инициализация

```python
from src.utils.error_tracker import ErrorTracker

# Создание системы подсчета ошибок
error_tracker = ErrorTracker(
    error_threshold=4,           # Порог для эскалации к планировщику
    escalation_threshold=3,      # Порог для эскалации к человеку
    max_retention_days=7         # Время хранения записей
)
```

### Запись попыток выполнения

```python
# Запись успешной попытки
attempt_id = error_tracker.record_attempt(
    step_id="step_1",
    command="sudo apt update",
    success=True,
    duration=2.5,
    exit_code=0,
    metadata={"command_type": "main_command"}
)

# Запись неудачной попытки
attempt_id = error_tracker.record_attempt(
    step_id="step_1",
    command="sudo apt install nonexistent-package",
    success=False,
    duration=0.1,
    exit_code=1,
    error_message="Package not found",
    autocorrection_used=False,
    metadata={"command_type": "main_command"}
)
```

### Запись ошибок

```python
# Запись ошибки
error_id = error_tracker.record_error(
    step_id="step_1",
    command="sudo apt install nonexistent-package",
    error_message="Package not found",
    exit_code=1,
    autocorrection_applied=False,
    metadata={"error_type": "package_not_found"}
)
```

### Проверка эскалации

```python
# Проверка необходимости эскалации
if error_tracker.should_escalate_to_planner("step_1"):
    print("Требуется эскалация к планировщику")

if error_tracker.should_escalate_to_human("step_1"):
    print("Требуется эскалация к человеку")

# Получение текущего уровня эскалации
escalation_level = error_tracker.get_escalation_level("step_1")
print(f"Уровень эскалации: {escalation_level}")
```

### Получение статистики

```python
# Статистика для конкретного шага
step_summary = error_tracker.get_error_summary("step_1")
print(f"Ошибок: {step_summary['error_count']}")
print(f"Попыток: {step_summary['attempt_count']}")
print(f"Процент успеха: {step_summary['success_rate']:.1f}%")

# Глобальная статистика
global_stats = error_tracker.get_global_stats()
print(f"Всего попыток: {global_stats['total_attempts']}")
print(f"Всего ошибок: {global_stats['total_errors']}")
print(f"Процент успеха: {global_stats['success_rate']:.1f}%")
```

## Интеграция с компонентами

### Execution Model

```python
class ExecutionModel:
    def __init__(self, config, ssh_connector, task_master=None):
        # Инициализация системы подсчета ошибок
        self.error_tracker = ErrorTracker(
            error_threshold=config.error_handler.error_threshold_per_step,
            escalation_threshold=config.error_handler.human_escalation_threshold,
            max_retention_days=config.error_handler.max_retention_days
        )
    
    def _execute_single_command(self, command, context):
        # ... выполнение команды ...
        
        # Запись попытки выполнения
        self.error_tracker.record_attempt(
            step_id=context.subtask.subtask_id,
            command=command,
            success=result.success,
            duration=result.duration,
            exit_code=result.exit_code,
            error_message=result.error_message,
            autocorrection_used=False,
            metadata={"command_type": "main_command"}
        )
        
        return result
```

### Task Agent

```python
class TaskAgent:
    def __init__(self, config, task_master=None):
        # Инициализация системы подсчета ошибок
        self.error_tracker = ErrorTracker(
            error_threshold=config.error_handler.error_threshold_per_step,
            escalation_threshold=config.error_handler.human_escalation_threshold,
            max_retention_days=config.error_handler.max_retention_days
        )
    
    def update_step_status(self, task, step_id, status, error_count=None):
        # ... обновление статуса ...
        
        # Проверка эскалации
        escalation_level = self.error_tracker.get_escalation_level(step_id)
        if escalation_level == EscalationLevel.PLANNER_NOTIFICATION:
            self.logger.warning("Эскалация к планировщику", step_id=step_id)
        elif escalation_level == EscalationLevel.HUMAN_ESCALATION:
            self.logger.error("Эскалация к человеку", step_id=step_id)
```

## Анализ паттернов ошибок

Система автоматически анализирует паттерны ошибок и группирует их по типам:

- `permission_denied` - ошибки прав доступа
- `command_not_found` - команды не найдены
- `connection_error` - сетевые ошибки
- `syntax_error` - синтаксические ошибки
- `file_not_found` - файлы не найдены
- `package_error` - ошибки пакетов
- `service_error` - ошибки сервисов

```python
# Получение паттернов ошибок
patterns = error_tracker.get_error_patterns("step_1")
print(patterns)
# {'permission_denied': 3, 'command_not_found': 1, 'connection_error': 2}
```

## Управление данными

### Очистка старых записей

```python
# Очистка записей старше max_retention_days
error_tracker.cleanup_old_records()
```

### Сброс статистики

```python
# Сброс статистики для конкретного шага
error_tracker.reset_step_stats("step_1")

# Сброс всей статистики
error_tracker.reset_stats()
```

## Мониторинг и алерты

### Получение недавних ошибок

```python
# Ошибки за последние 24 часа
recent_errors = error_tracker.get_recent_errors("step_1", hours=24)

# Ошибки за последний час
recent_errors = error_tracker.get_recent_errors("step_1", hours=1)
```

### Проверка состояния системы

```python
# Проверка общего состояния
global_stats = error_tracker.get_global_stats()

if global_stats['success_rate'] < 80:
    print("ВНИМАНИЕ: Низкий процент успеха выполнения команд")

if global_stats['escalations_to_human'] > 0:
    print("ВНИМАНИЕ: Требуется вмешательство человека")
```

## Примеры использования

### Базовый пример

```python
from src.utils.error_tracker import ErrorTracker

# Создание системы
tracker = ErrorTracker(error_threshold=3, escalation_threshold=5)

# Симуляция выполнения команд
commands = [
    ("sudo apt update", True),
    ("sudo apt install nginx", True),
    ("systemctl start nginx", False),
    ("systemctl status nginx", False),
    ("curl http://localhost", False)
]

for i, (command, success) in enumerate(commands):
    tracker.record_attempt(
        step_id="install_nginx",
        command=command,
        success=success,
        duration=1.0,
        exit_code=0 if success else 1,
        error_message=None if success else f"Error in {command}"
    )
    
    # Проверка эскалации
    escalation = tracker.get_escalation_level("install_nginx")
    print(f"Команда: {command}")
    print(f"Успех: {success}")
    print(f"Эскалация: {escalation.value}")
    print("---")
```

### Расширенный пример с автокоррекцией

```python
# Оригинальная команда
original_command = "sudo apt install nginx"
result = tracker.record_attempt(
    step_id="install_nginx",
    command=original_command,
    success=False,
    duration=0.1,
    exit_code=1,
    error_message="Package not found"
)

# Автокоррекция
corrected_command = "sudo apt update && sudo apt install nginx"
corrected_result = tracker.record_attempt(
    step_id="install_nginx",
    command=corrected_command,
    success=True,
    duration=2.0,
    exit_code=0,
    autocorrection_used=True,
    metadata={
        "original_command": original_command,
        "autocorrection_strategy": "package_update"
    }
)

# Анализ результатов
summary = tracker.get_error_summary("install_nginx")
print(f"Всего попыток: {summary['attempt_count']}")
print(f"Ошибок: {summary['error_count']}")
print(f"Процент успеха: {summary['success_rate']:.1f}%")
```

## Лучшие практики

1. **Регулярная очистка**: Периодически очищайте старые записи для экономии памяти
2. **Мониторинг эскалаций**: Отслеживайте случаи эскалации к человеку
3. **Анализ паттернов**: Используйте анализ паттернов для улучшения автокоррекции
4. **Настройка порогов**: Адаптируйте пороги эскалации под ваши потребности
5. **Логирование**: Всегда логируйте важные события эскалации

## Производительность

- Система оптимизирована для быстрой записи и поиска
- Использует in-memory хранение для максимальной производительности
- Автоматическая очистка старых записей предотвращает утечки памяти
- Минимальное влияние на производительность выполнения команд

## Безопасность

- Все записи содержат только метаданные, без чувствительной информации
- Автоматическая очистка старых записей
- Возможность отключения системы через конфигурацию
- Логирование всех операций эскалации

