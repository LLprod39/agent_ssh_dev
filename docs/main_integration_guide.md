# Руководство по интеграции SSH Agent

## Обзор

SSH Agent представляет собой интегрированную систему для автоматизации задач на удаленных серверах с использованием LLM для планирования и выполнения команд. Главный класс `SSHAgent` координирует все компоненты системы.

## Архитектура интеграции

### Основные компоненты

1. **SSHAgent** - главный класс, координирующий все компоненты
2. **TaskAgent** - планирование основных шагов
3. **SubtaskAgent** - планирование подзадач
4. **ExecutionModel** - выполнение команд
5. **ErrorHandler** - обработка ошибок и эскалация
6. **SSHConnector** - подключение к серверу
7. **TaskMasterIntegration** - интеграция с Task Master

### Система управления состоянием

```python
@dataclass
class TaskExecutionState:
    """Состояние выполнения задачи"""
    task_id: str
    task: Task
    current_step_index: int = 0
    execution_start_time: Optional[datetime] = None
    execution_end_time: Optional[datetime] = None
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    error_count: int = 0
    is_dry_run: bool = False
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

## Инициализация

### Базовая инициализация

```python
from src.main import SSHAgent

# Инициализация с файлами конфигурации
agent = SSHAgent(
    server_config_path="config/server_config.yaml",
    agent_config_path="config/agent_config.yaml"
)

# Инициализация с конфигурацией по умолчанию
agent = SSHAgent()

# Инициализация с пользовательской конфигурацией
config = {
    "server": {
        "host": "example.com",
        "username": "user",
        "auth_method": "key"
    },
    "agents": {
        "llm": {
            "api_key": "your-api-key"
        }
    }
}
agent = SSHAgent(config=config)
```

### Проверка статуса

```python
# Получение статуса агента
status = agent.get_agent_status()

print(f"Задач выполнено: {status['agent_stats']['tasks_executed']}")
print(f"Компонентов инициализировано: {sum(status['components_status'].values())}")
print(f"Текущее выполнение: {'Активно' if status['current_execution']['is_running'] else 'Неактивно'}")
```

## Выполнение задач

### Базовое выполнение

```python
import asyncio

async def execute_task():
    # Выполнение задачи
    result = await agent.execute_task("Установить и настроить nginx на сервере")
    
    if result["success"]:
        print(f"Задача выполнена успешно!")
        print(f"Шагов выполнено: {result['steps_completed']}/{result['total_steps']}")
        print(f"Время выполнения: {result['execution_duration']:.2f}с")
    else:
        print(f"Задача завершена с ошибками: {result['error']}")

# Запуск
asyncio.run(execute_task())
```

### Dry-run режим

```python
# Предварительный просмотр выполнения
result = await agent.execute_task(
    "Установить PostgreSQL", 
    dry_run=True
)

print(f"Будет выполнено шагов: {result['total_steps']}")
print(f"Ожидаемое время: {result['execution_duration']:.2f}с")
```

## Координация компонентов

### Поток выполнения

1. **Планирование задачи** - TaskAgent разбивает задачу на основные шаги
2. **Планирование подзадач** - SubtaskAgent создает детальные подзадачи для каждого шага
3. **Выполнение** - ExecutionModel выполняет подзадачи последовательно
4. **Обработка ошибок** - ErrorHandler отслеживает ошибки и эскалирует при необходимости
5. **Завершение** - Создается итоговый отчет и обновляется статистика

### Управление состоянием

```python
# Получение текущего состояния
if agent.current_execution_state:
    state = agent.current_execution_state
    print(f"Текущая задача: {state.task.title}")
    print(f"Прогресс: {state.get_progress_percentage():.1f}%")
    print(f"Выполнено шагов: {state.completed_steps}/{state.total_steps}")
```

## Обработка ошибок

### Система эскалации

```python
# Настройка колбэков для обработки ошибок
def planner_callback(error_report):
    print(f"Эскалация к планировщику: {error_report.title}")

def human_escalation_callback(error_report):
    print(f"КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ: {error_report.title}")

# Регистрация колбэков (выполняется автоматически при инициализации)
agent.error_handler.register_planner_callback(planner_callback)
agent.error_handler.register_human_escalation_callback(human_escalation_callback)
```

### Получение отчетов об ошибках

```python
# Получение недавних отчетов
recent_reports = agent.error_handler.get_recent_reports(hours=24)

for report in recent_reports:
    print(f"Отчет: {report.title}")
    print(f"Тип: {report.report_type.value}")
    print(f"Рекомендации: {report.recommendations}")
```

## Мониторинг и статистика

### Статистика агента

```python
stats = agent.agent_stats

print(f"Задач выполнено: {stats['tasks_executed']}")
print(f"Задач завершено: {stats['tasks_completed']}")
print(f"Задач провалено: {stats['tasks_failed']}")
print(f"Общее время выполнения: {stats['total_execution_time']:.2f}с")
print(f"Общее количество ошибок: {stats['total_errors']}")
print(f"Эскалаций: {stats['escalations']}")
```

### История выполнения

```python
# Получение истории выполнения
history = agent.get_execution_history(limit=10)

for execution in history:
    print(f"Задача: {execution['task_title']}")
    print(f"Статус: {'✓' if execution['success'] else '✗'}")
    print(f"Шагов: {execution['completed_steps']}/{execution['total_steps']}")
    print(f"Время: {execution['duration']:.2f}с")
    print(f"Dry-run: {'Да' if execution['is_dry_run'] else 'Нет'}")
    print("---")
```

## CLI интерфейс

### Основные команды

```bash
# Выполнение задачи
python -m src.main execute "Установить nginx" --dry-run

# Интерактивный режим
python -m src.main interactive

# Просмотр статуса
python -m src.main status

# Просмотр истории
python -m src.main history --limit 5

# Очистка старых данных
python -m src.main cleanup --days 7

# Инициализация конфигурации
python -m src.main init
```

### Интерактивный режим

```bash
python -m src.main interactive
```

Доступные команды в интерактивном режиме:
- Введите описание задачи для выполнения
- `status` - показать статус агента
- `history` - показать историю выполнения
- `cleanup` - очистить старые данные
- `exit` или `quit` - выход

## Очистка данных

### Автоматическая очистка

```python
# Очистка данных старше 7 дней
agent.cleanup_old_data(days=7)
```

### Ручная очистка

```python
# Очистка истории выполнения
agent.execution_history.clear()

# Очистка данных обработчика ошибок
agent.error_handler.cleanup_old_data(days=7)
```

## Обработка исключений

### Обработка ошибок инициализации

```python
try:
    agent = SSHAgent(server_config_path="config/server_config.yaml")
except RuntimeError as e:
    print(f"Ошибка инициализации: {e}")
    # Обработка ошибки
```

### Обработка ошибок выполнения

```python
try:
    result = await agent.execute_task("Задача")
    if not result["success"]:
        print(f"Задача завершена с ошибками: {result['error']}")
except Exception as e:
    print(f"Критическая ошибка: {e}")
```

## Лучшие практики

### 1. Всегда используйте dry-run для новых задач

```python
# Сначала проверяем план
dry_run_result = await agent.execute_task("Новая задача", dry_run=True)

if dry_run_result["success"]:
    # Выполняем реальную задачу
    result = await agent.execute_task("Новая задача", dry_run=False)
```

### 2. Мониторьте статистику выполнения

```python
# Регулярно проверяйте статистику
status = agent.get_agent_status()
if status['agent_stats']['escalations'] > 0:
    print("Обнаружены эскалации, требуется внимание")
```

### 3. Очищайте старые данные

```python
# Регулярная очистка
agent.cleanup_old_data(days=7)
```

### 4. Обрабатывайте ошибки gracefully

```python
try:
    result = await agent.execute_task(task_description)
    # Обработка результата
except Exception as e:
    logger.error(f"Ошибка выполнения задачи: {e}")
    # Восстановление или уведомление
```

## Расширение функциональности

### Добавление новых колбэков

```python
def custom_callback(error_report):
    # Пользовательская обработка ошибок
    pass

agent.error_handler.register_planner_callback(custom_callback)
```

### Кастомная конфигурация

```python
# Создание агента с кастомной конфигурацией
custom_config = {
    "server": {
        "host": "custom-server.com",
        "username": "custom-user",
        "auth_method": "key"
    },
    "agents": {
        "executor": {
            "max_retries_per_command": 3,
            "auto_correction_enabled": True
        },
        "error_handler": {
            "error_threshold_per_step": 5,
            "human_escalation_threshold": 4
        }
    }
}

agent = SSHAgent(config=custom_config)
```

## Заключение

SSH Agent предоставляет мощную и гибкую систему для автоматизации задач на удаленных серверах. Интеграция всех компонентов обеспечивает надежное выполнение задач с автоматической обработкой ошибок и эскалацией.

Ключевые преимущества:
- Полная координация между компонентами
- Автоматическая обработка ошибок
- Система управления состоянием
- Мониторинг и статистика
- Dry-run режим для безопасного тестирования
- Гибкая конфигурация
- CLI и программный интерфейсы
