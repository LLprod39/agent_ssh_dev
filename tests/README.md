# Тесты SSH Agent

Этот каталог содержит все тесты для проекта SSH Agent с LLM.

## Структура тестов

```
tests/
├── test_agents/           # Unit тесты для агентов
│   ├── test_task_agent.py
│   ├── test_subtask_agent.py
│   ├── test_error_handler.py
│   ├── test_escalation_system.py
│   └── test_human_operator_system.py
├── test_connectors/       # Unit тесты для коннекторов
│   └── test_ssh_connector.py
├── test_models/           # Unit тесты для моделей
│   ├── test_execution_model.py
│   ├── test_planning_model.py
│   └── test_llm_interface.py
├── test_utils/            # Unit тесты для утилит
│   ├── test_logger.py
│   ├── test_validator.py
│   ├── test_formatter.py
│   └── test_autocorrection.py
├── test_integration/      # Интеграционные тесты
│   ├── test_main_integration.py
│   └── test_error_scenarios.py
└── README.md             # Этот файл
```

## Запуск тестов

### Все тесты
```bash
python run_tests.py
```

### Только unit тесты
```bash
python run_tests.py --unit
```

### Только интеграционные тесты
```bash
python run_tests.py --integration
```

### С покрытием кода
```bash
python run_tests.py --coverage
```

### Конкретный файл
```bash
python run_tests.py --file tests/test_agents/test_task_agent.py
```

### Фильтр по паттерну
```bash
python run_tests.py --pattern "test_success"
```

### Подробный вывод
```bash
python run_tests.py --verbose
```

### Параллельное выполнение
```bash
python run_tests.py --parallel 8
```

## Использование pytest напрямую

### Базовый запуск
```bash
pytest
```

### Конкретная директория
```bash
pytest tests/test_agents/
```

### Конкретный файл
```bash
pytest tests/test_agents/test_task_agent.py
```

### Конкретная функция
```bash
pytest tests/test_agents/test_task_agent.py::TestTaskAgent::test_plan_task_success
```

### С покрытием
```bash
pytest --cov=src --cov-report=html
```

### Параллельно
```bash
pytest -n 4
```

### Асинхронные тесты
```bash
pytest -m asyncio
```

## Маркеры тестов

- `@pytest.mark.unit` - Unit тесты
- `@pytest.mark.integration` - Интеграционные тесты
- `@pytest.mark.slow` - Медленные тесты
- `@pytest.mark.network` - Тесты, требующие сетевого соединения
- `@pytest.mark.ssh` - Тесты, требующие SSH соединения
- `@pytest.mark.llm` - Тесты, требующие LLM API
- `@pytest.mark.asyncio` - Асинхронные тесты

### Запуск по маркерам
```bash
pytest -m "unit and not slow"
pytest -m "integration"
pytest -m "not network"
```

## Конфигурация

### pytest.ini
Основная конфигурация pytest находится в корне проекта в файле `pytest.ini`.

### requirements-test.txt
Зависимости для тестирования находятся в файле `requirements-test.txt`.

## Покрытие кода

### Генерация отчета
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Просмотр отчета
После генерации откройте `htmlcov/index.html` в браузере.

### Минимальное покрытие
```bash
pytest --cov=src --cov-fail-under=80
```

## Отладка тестов

### Подробный вывод
```bash
pytest -v -s
```

### Остановка на первой ошибке
```bash
pytest -x
```

### Запуск только упавших тестов
```bash
pytest --lf
```

### Запуск с отладчиком
```bash
pytest --pdb
```

## Моки и фикстуры

### Использование моков
```python
from unittest.mock import Mock, patch

@patch('src.agents.task_agent.LLMInterface')
def test_with_mock(mock_llm):
    mock_llm.return_value.generate_response.return_value = Mock(success=True)
    # тест
```

### Фикстуры pytest
```python
@pytest.fixture
def sample_config():
    return AgentConfig(...)

def test_with_fixture(sample_config):
    # тест
```

## Асинхронные тесты

### Базовый асинхронный тест
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result.success is True
```

### Моки для асинхронных функций
```python
@pytest.mark.asyncio
async def test_async_with_mock():
    with patch('module.async_function', new_callable=AsyncMock) as mock_func:
        mock_func.return_value = "mocked result"
        result = await test_function()
        assert result == "mocked result"
```

## Тестирование ошибок

### Тест исключений
```python
def test_raises_exception():
    with pytest.raises(ValueError, match="Invalid value"):
        function_that_raises()
```

### Тест предупреждений
```python
def test_warns():
    with pytest.warns(UserWarning, match="Deprecated"):
        deprecated_function()
```

## Производительность

### Бенчмарки
```python
def test_performance(benchmark):
    result = benchmark(expensive_function)
    assert result is not None
```

### Профилирование памяти
```python
@pytest.mark.slow
def test_memory_usage():
    from memory_profiler import profile
    
    @profile
    def memory_intensive_function():
        # код
        pass
    
    memory_intensive_function()
```

## Непрерывная интеграция

### GitHub Actions
Тесты автоматически запускаются в GitHub Actions при каждом push и pull request.

### Локальная проверка
```bash
# Перед коммитом
python run_tests.py --coverage
black src tests
isort src tests
flake8 src tests
mypy src
```

## Лучшие практики

1. **Именование тестов**: `test_<function>_<scenario>_<expected_result>`
2. **Один тест - одна проверка**: Каждый тест должен проверять одну вещь
3. **Используйте фикстуры**: Для повторяющихся данных и настройки
4. **Моки вместо реальных зависимостей**: Для изоляции тестов
5. **Тестируйте граничные случаи**: Пустые значения, None, исключения
6. **Документируйте сложные тесты**: Используйте docstrings
7. **Группируйте связанные тесты**: В классах TestClass
8. **Используйте параметризацию**: Для тестирования множественных входных данных

## Примеры

### Простой unit тест
```python
def test_add_numbers():
    assert add_numbers(2, 3) == 5
    assert add_numbers(-1, 1) == 0
    assert add_numbers(0, 0) == 0
```

### Тест с фикстурой
```python
@pytest.fixture
def sample_task():
    return Task(title="Test", description="Test task")

def test_task_creation(sample_task):
    assert sample_task.title == "Test"
    assert sample_task.status == TaskStatus.PENDING
```

### Интеграционный тест
```python
@pytest.mark.asyncio
async def test_full_workflow():
    agent = SSHAgent(config, server_config)
    result = await agent.execute_task("Install nginx")
    assert result.success is True
```

## Поддержка

Если у вас есть вопросы по тестам, создайте issue в репозитории или обратитесь к команде разработки.
