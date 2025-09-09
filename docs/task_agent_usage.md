# Task Agent - Руководство по использованию

## Обзор

Task Agent - это компонент системы SSH Agent, отвечающий за планирование основных шагов выполнения задач. Он разбивает сложные задачи на логические, выполнимые шаги с учетом зависимостей и приоритетов.

## Основные возможности

- **Планирование задач**: Разбиение задач на логические шаги
- **Система ID**: Уникальная идентификация каждого шага
- **Управление зависимостями**: Определение порядка выполнения шагов
- **Интеграция с LLM**: Использование языковых моделей для планирования
- **Task Master интеграция**: Улучшение промтов через Task Master
- **Валидация планов**: Проверка корректности созданных планов
- **Оптимизация**: Автоматическая оптимизация порядка выполнения

## Архитектура

```
Task Agent
├── LLM Interface (OpenAI/Mock)
├── Task Master Integration
├── Planning Models
│   ├── Task
│   ├── TaskStep
│   └── PlanningResult
└── Validation & Optimization
```

## Быстрый старт

### 1. Инициализация

```python
from src.agents.task_agent import TaskAgent, TaskPlanningContext
from src.config.agent_config import AgentConfig

# Загрузка конфигурации
config = AgentConfig.from_yaml("config/agent_config.yaml")

# Создание Task Agent
task_agent = TaskAgent(config)
```

### 2. Простое планирование

```python
# Простая задача
task_description = "Установить и настроить nginx на сервере"

result = task_agent.plan_task(task_description)

if result.success:
    print(f"Задача спланирована: {result.task.title}")
    print(f"Количество шагов: {len(result.task.steps)}")
    
    for step in result.task.steps:
        print(f"- {step.title}: {step.description}")
```

### 3. Планирование с контекстом

```python
# Создание контекста
context = TaskPlanningContext(
    server_info={
        "os": "ubuntu",
        "version": "20.04",
        "memory": "4GB"
    },
    user_requirements="Настроить веб-сервер с SSL",
    constraints=["Не перезагружать сервер"],
    available_tools=["apt", "systemctl", "certbot"],
    environment={"production": True}
)

# Планирование с контекстом
result = task_agent.plan_task(task_description, context)
```

## Модели данных

### Task

Основная задача, содержащая список шагов.

```python
@dataclass
class Task:
    task_id: str                    # Уникальный ID задачи
    title: str                      # Заголовок задачи
    description: str                # Описание задачи
    status: TaskStatus              # Статус (PENDING, IN_PROGRESS, COMPLETED, FAILED)
    priority: Priority              # Приоритет (LOW, MEDIUM, HIGH, CRITICAL)
    steps: List[TaskStep]           # Список шагов
    created_at: datetime            # Время создания
    total_estimated_duration: int   # Общее время выполнения (минуты)
```

### TaskStep

Отдельный шаг выполнения задачи.

```python
@dataclass
class TaskStep:
    step_id: str                    # Уникальный ID шага
    title: str                      # Заголовок шага
    description: str                # Описание шага
    status: StepStatus              # Статус шага
    priority: Priority              # Приоритет шага
    estimated_duration: int         # Оценка времени (минуты)
    dependencies: List[str]         # ID зависимых шагов
    error_count: int                # Количество ошибок
    max_errors: int                 # Максимум ошибок
```

### PlanningResult

Результат планирования задачи.

```python
@dataclass
class PlanningResult:
    success: bool                   # Успешность планирования
    task: Optional[Task]            # Созданная задача
    error_message: Optional[str]    # Сообщение об ошибке
    planning_duration: float        # Время планирования (секунды)
    llm_usage: Dict[str, Any]      # Статистика использования LLM
```

## API Reference

### TaskAgent

#### `__init__(config: AgentConfig, task_master: Optional[TaskMasterIntegration] = None)`

Инициализация Task Agent.

**Параметры:**
- `config`: Конфигурация агентов
- `task_master`: Интеграция с Task Master (опционально)

#### `plan_task(task_description: str, context: Optional[TaskPlanningContext] = None) -> PlanningResult`

Планирование задачи - разбиение на основные шаги.

**Параметры:**
- `task_description`: Описание задачи для планирования
- `context`: Контекст планирования (опционально)

**Возвращает:**
- `PlanningResult`: Результат планирования

#### `get_task_status(task: Task) -> Dict[str, Any]`

Получение статуса задачи.

**Параметры:**
- `task`: Задача для получения статуса

**Возвращает:**
- Словарь со статусом задачи и прогрессом

#### `update_step_status(task: Task, step_id: str, status: StepStatus, error_count: Optional[int] = None) -> bool`

Обновление статуса шага.

**Параметры:**
- `task`: Задача, содержащая шаг
- `step_id`: ID шага для обновления
- `status`: Новый статус шага
- `error_count`: Количество ошибок (опционально)

**Возвращает:**
- `True` если обновление успешно, `False` иначе

### TaskPlanningContext

Контекст для планирования задачи.

```python
@dataclass
class TaskPlanningContext:
    server_info: Dict[str, Any]         # Информация о сервере
    user_requirements: str              # Требования пользователя
    constraints: List[str]              # Ограничения
    available_tools: List[str]          # Доступные инструменты
    previous_tasks: List[Dict[str, Any]] # Предыдущие задачи
    environment: Dict[str, Any]         # Окружение
```

## Конфигурация

### agent_config.yaml

```yaml
agents:
  task_agent:
    model: "gpt-4"              # Модель LLM
    temperature: 0.3            # Температура генерации
    max_steps: 10               # Максимум шагов в плане
    max_tokens: 2000            # Максимум токенов в ответе

llm:
  api_key: "your-api-key"       # API ключ
  base_url: "https://api.openai.com/v1"  # Базовый URL
  timeout: 60                   # Таймаут запроса
```

## Примеры использования

### Пример 1: Установка веб-сервера

```python
task_description = """
Установить и настроить веб-сервер nginx на Ubuntu 20.04:
1. Обновить систему
2. Установить nginx
3. Настроить конфигурацию
4. Запустить и включить автозапуск
5. Проверить работоспособность
"""

result = task_agent.plan_task(task_description)

if result.success:
    print("План создан успешно!")
    for i, step in enumerate(result.task.steps, 1):
        print(f"{i}. {step.title}")
        print(f"   Время: {step.estimated_duration} мин")
        print(f"   Приоритет: {step.priority.value}")
```

### Пример 2: Настройка с SSL

```python
context = TaskPlanningContext(
    server_info={"os": "ubuntu", "version": "20.04"},
    user_requirements="Настроить nginx с SSL сертификатом",
    constraints=["Не перезагружать сервер", "Использовать Let's Encrypt"],
    available_tools=["apt", "systemctl", "certbot", "nginx"],
    environment={"domain": "example.com", "email": "admin@example.com"}
)

result = task_agent.plan_task("Настроить nginx с SSL", context)
```

### Пример 3: Мониторинг прогресса

```python
# Планирование задачи
result = task_agent.plan_task("Установить Docker")

if result.success:
    task = result.task
    
    # Получение статуса
    status = task_agent.get_task_status(task)
    print(f"Прогресс: {status['progress']['progress_percentage']:.1f}%")
    
    # Обновление статуса шага
    first_step = task.steps[0]
    task_agent.update_step_status(task, first_step.step_id, StepStatus.EXECUTING)
    
    # Проверка обновленного статуса
    updated_status = task_agent.get_task_status(task)
    print(f"Статус задачи: {updated_status['status']}")
```

## Интеграция с Task Master

Task Agent может использовать Task Master для улучшения промтов:

```python
from src.agents.task_master_integration import TaskMasterIntegration

# Инициализация Task Master
task_master = TaskMasterIntegration(config.taskmaster)

# Создание Task Agent с Task Master
task_agent = TaskAgent(config, task_master)

# Планирование с улучшенными промтами
result = task_agent.plan_task(task_description)
```

## Обработка ошибок

### Типичные ошибки

1. **Ошибка LLM API**
   ```python
   if not result.success:
       print(f"Ошибка планирования: {result.error_message}")
   ```

2. **Невалидный JSON ответ**
   - Task Agent автоматически обрабатывает невалидные ответы
   - Возвращает ошибку с описанием проблемы

3. **Циклические зависимости**
   - Валидация автоматически обнаруживает циклы
   - План помечается как невалидный

### Валидация планов

```python
# Создание задачи с проблемами
task = Task(title="Проблемная задача")
step1 = TaskStep(title="Шаг 1", step_id="step_1", dependencies=["step_2"])
step2 = TaskStep(title="Шаг 2", step_id="step_2", dependencies=["step_1"])
task.add_step(step1)
task.add_step(step2)

# Валидация
validation_result = task_agent._validate_plan(task)
if not validation_result["valid"]:
    print("Проблемы в плане:")
    for issue in validation_result["issues"]:
        print(f"- {issue}")
```

## Логирование

Task Agent использует структурированное логирование:

```python
# Логирование планирования
task_agent.logger.info("Начало планирования задачи", task_description=description)

# Логирование ошибок
task_agent.logger.error("Ошибка планирования", error=str(e))

# Логирование метрик
task_agent.logger.info("Планирование завершено", 
                      duration=planning_duration, 
                      steps_count=len(steps))
```

## Тестирование

Запуск тестов:

```bash
# Все тесты Task Agent
pytest tests/test_agents/test_task_agent.py -v

# Конкретный тест
pytest tests/test_agents/test_task_agent.py::TestTaskAgent::test_plan_task_success -v
```

## Производительность

### Оптимизация

- **Кэширование**: LLM ответы могут кэшироваться
- **Параллелизм**: Независимые шаги могут планироваться параллельно
- **Валидация**: Быстрая проверка планов без обращения к LLM

### Метрики

- Время планирования
- Количество токенов LLM
- Количество шагов в плане
- Процент успешных планирований

## Ограничения

1. **Зависимость от LLM**: Требует доступ к языковой модели
2. **Качество промтов**: Результат зависит от качества входных промтов
3. **Валидация**: Не все ошибки могут быть обнаружены автоматически
4. **Производительность**: Планирование может занимать время

## Будущие улучшения

- [ ] Кэширование планов
- [ ] Машинное обучение для оптимизации
- [ ] Поддержка множественных LLM провайдеров
- [ ] Автоматическое исправление планов
- [ ] Интеграция с системами мониторинга
