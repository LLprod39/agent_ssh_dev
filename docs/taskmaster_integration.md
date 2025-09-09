# Task Master Integration

## Обзор

TaskMasterIntegration - это модуль для интеграции с [light-task-master](https://github.com/mrsions/light-task-master), который обеспечивает улучшение промтов, парсинг PRD документов и генерацию задач.

## Основные возможности

### 1. Улучшение промтов
- Автоматическое улучшение промтов через Task Master API
- Поддержка контекстной информации
- Настраиваемые параметры модели (температура, max_tokens)

### 2. Парсинг PRD документов
- Автоматический парсинг Product Requirements Document
- Извлечение структурированной информации
- Поддержка кастомных PRD файлов

### 3. Генерация задач
- Создание задач на основе PRD
- Настраиваемое количество задач
- Структурированный вывод с метаданными

### 4. Валидация и форматирование
- Валидация промтов по типам
- Форматирование промтов в различные стили
- Оценка качества промтов

## Установка и настройка

### Предварительные требования
- Node.js 18+
- npm 8+
- Python 3.9+

### Установка Task Master
```bash
# Глобальная установка
npm install -g task-master-ai

# Или через package.json
npm install
```

### Инициализация в проекте
```bash
# Инициализация Task Master
npx task-master-ai init --rules cursor,windsurf,vscode
```

## Использование

### Базовое использование

```python
from src.agents.task_master_integration import TaskMasterIntegration
from src.config.agent_config import TaskmasterConfig

# Создание конфигурации
config = TaskmasterConfig(
    enabled=True,
    model="gpt-4",
    temperature=0.7,
    max_tokens=1000
)

# Инициализация интеграции
integration = TaskMasterIntegration(config)

# Улучшение промта
result = integration.improve_prompt("Исходный промт")
if result.success:
    improved_prompt = result.data["improved_prompt"]
    print(improved_prompt)
```

### Улучшение промта с контекстом

```python
context = {
    "task_type": "database_setup",
    "os": "ubuntu",
    "complexity": "medium"
}

result = integration.improve_prompt(
    "Установи PostgreSQL на сервере",
    context=context
)
```

### Парсинг PRD

```python
# Парсинг основного PRD
result = integration.parse_prd()

# Парсинг кастомного PRD
result = integration.parse_prd("path/to/custom_prd.txt")
```

### Генерация задач

```python
# Генерация 10 задач из PRD
result = integration.generate_tasks_from_prd(num_tasks=10)

if result.success:
    tasks = result.data["tasks"]
    for task in tasks:
        print(f"Задача: {task['title']}")
        print(f"Описание: {task['description']}")
```

### Валидация промтов

```python
# Валидация промта для планирования
result = integration.validate_prompt(
    "Создай план установки PostgreSQL",
    prompt_type="planning"
)

if result.success and result.data["valid"]:
    print("Промт валиден")
    print(f"Оценка: {result.data.get('score', 'N/A')}")
```

### Форматирование промтов

```python
# Структурированное форматирование
result = integration.format_prompt(
    "install postgresql create database",
    format_type="structured"
)

# Краткое форматирование
result = integration.format_prompt(
    "Длинный промт с множеством деталей...",
    format_type="concise"
)
```

## Конфигурация

### TaskmasterConfig

```python
class TaskmasterConfig(BaseModel):
    enabled: bool = True                    # Включен ли Task Master
    model: str = "gpt-4"                   # Модель LLM
    temperature: float = 0.7               # Температура (0.0-2.0)
    max_tokens: int = 1000                 # Максимальное количество токенов
```

### YAML конфигурация

```yaml
agents:
  taskmaster:
    enabled: true
    model: "gpt-4"
    temperature: 0.7
    max_tokens: 1000
```

## Структура данных

### TaskMasterResult

```python
@dataclass
class TaskMasterResult:
    success: bool                          # Успешность операции
    data: Optional[Dict[str, Any]] = None  # Данные результата
    error: Optional[str] = None            # Сообщение об ошибке
    raw_output: Optional[str] = None       # Сырой вывод
```

### ParsedPRD

```python
@dataclass
class ParsedPRD:
    overview: str                          # Обзор проекта
    core_features: List[Dict[str, str]]    # Основные функции
    user_experience: Dict[str, Any]        # Пользовательский опыт
    technical_architecture: Dict[str, Any] # Техническая архитектура
    development_roadmap: List[Dict[str, Any]] # План разработки
    risks_and_mitigations: List[Dict[str, str]] # Риски и митигация
    raw_content: str                       # Исходный контент
```

### GeneratedTask

```python
@dataclass
class GeneratedTask:
    task_id: str                           # ID задачи
    title: str                             # Заголовок
    description: str                       # Описание
    priority: str                          # Приоритет
    estimated_effort: str                  # Оценка усилий
    dependencies: List[str]                # Зависимости
    acceptance_criteria: List[str]         # Критерии приемки
    subtasks: List[Dict[str, str]]         # Подзадачи
```

## Обработка ошибок

### Типичные ошибки

1. **Task Master не установлен**
   ```python
   result = integration.improve_prompt("промт")
   if not result.success:
       print(f"Ошибка: {result.error}")
   ```

2. **PRD файл не найден**
   ```python
   result = integration.parse_prd("nonexistent.txt")
   if not result.success:
       print(f"Файл не найден: {result.error}")
   ```

3. **Таймаут операции**
   ```python
   result = integration.generate_tasks_from_prd()
   if not result.success and "Таймаут" in result.error:
       print("Операция заняла слишком много времени")
   ```

### Проверка статуса

```python
status = integration.get_taskmaster_status()
print(f"Task Master включен: {status['enabled']}")
print(f"Статус установки: {status['installation_status']}")
print(f"Версия: {status.get('version', 'неизвестна')}")
```

## Отключение Task Master

Для отключения Task Master установите `enabled: false` в конфигурации:

```python
config = TaskmasterConfig(enabled=False)
integration = TaskMasterIntegration(config)

# При отключенном Task Master операции возвращают исходные данные
result = integration.improve_prompt("промт")
# result.data["improved_prompt"] будет равен исходному промту
```

## Тестирование

Запуск тестов:

```bash
# Все тесты
pytest tests/test_agents/test_task_master_integration.py

# Конкретный тест
pytest tests/test_agents/test_task_master_integration.py::TestTaskMasterIntegration::test_improve_prompt_success

# С подробным выводом
pytest -v tests/test_agents/test_task_master_integration.py
```

## Примеры

См. файл `examples/task_master_integration_example.py` для полных примеров использования.

## Troubleshooting

### Проблема: Task Master не найден
**Решение**: Убедитесь, что Task Master установлен глобально:
```bash
npm install -g task-master-ai
npx task-master-ai --version
```

### Проблема: Ошибки при парсинге PRD
**Решение**: Проверьте формат PRD файла и убедитесь, что он соответствует ожидаемой структуре.

### Проблема: Таймауты при выполнении операций
**Решение**: Увеличьте таймауты в коде или проверьте стабильность интернет-соединения.

### Проблема: JSON ошибки парсинга
**Решение**: Task Master может возвращать не-JSON ответы. Код автоматически обрабатывает это, возвращая текстовый результат.

## Интеграция с другими компонентами

TaskMasterIntegration используется в:

1. **TaskAgent** - для улучшения промтов планирования
2. **SubtaskAgent** - для детализации планов
3. **Executor** - для валидации команд
4. **ErrorHandler** - для анализа ошибок

## Будущие улучшения

- Поддержка локальных LLM моделей
- Кэширование результатов
- Пакетная обработка промтов
- Интеграция с другими инструментами планирования
- Расширенная аналитика качества промтов
