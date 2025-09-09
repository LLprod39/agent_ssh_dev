# Тестирование SSH Agent

Этот документ описывает структуру тестов и способы их запуска для проекта SSH Agent.

## Структура тестов

```
tests/
├── conftest.py                    # Общие фикстуры pytest
├── test_agents/                   # Тесты агентов
│   ├── test_task_agent.py
│   ├── test_subtask_agent.py
│   ├── test_error_handler.py
│   └── test_task_master_integration.py
├── test_connectors/               # Тесты коннекторов
│   └── test_ssh_connector.py
├── test_models/                   # Тесты моделей
│   ├── test_execution_model.py
│   └── test_planning_model.py
├── test_utils/                    # Тесты утилит
│   ├── test_autocorrection.py
│   ├── test_dry_run_system.py
│   ├── test_error_tracker.py
│   └── test_idempotency_system.py
├── test_integration/              # Интеграционные тесты
│   └── test_full_workflow.py
├── test_error_scenarios/          # Тесты сценариев ошибок
│   └── test_error_scenarios.py
└── README.md                      # Этот файл
```

## Типы тестов

### Unit тесты
- Тестируют отдельные компоненты изолированно
- Используют моки для внешних зависимостей
- Быстрые и надежные
- Маркер: `@pytest.mark.unit`

### Интеграционные тесты
- Тестируют взаимодействие между компонентами
- Проверяют полные рабочие процессы
- Могут использовать реальные зависимости
- Маркер: `@pytest.mark.integration`

### Тесты сценариев ошибок
- Тестируют обработку различных типов ошибок
- Проверяют системы автокоррекции и восстановления
- Маркер: `@pytest.mark.error_scenarios`

## Запуск тестов

### Использование Makefile (рекомендуется)

```bash
# Установить зависимости
make install

# Запустить unit тесты
make test-unit

# Запустить интеграционные тесты
make test-integration

# Запустить тесты сценариев ошибок
make test-error

# Запустить все тесты
make test-all

# Запустить тесты с покрытием кода
make test-coverage

# Запустить быстрые тесты (без медленных)
make test-fast

# Запустить тесты параллельно
make test-parallel
```

### Использование скрипта run_tests.py

```bash
# Unit тесты
python run_tests.py unit

# Интеграционные тесты
python run_tests.py integration

# Тесты сценариев ошибок
python run_tests.py error_scenarios

# Все тесты
python run_tests.py all

# Тесты с покрытием
python run_tests.py coverage
```

### Прямое использование pytest

```bash
# Все тесты
pytest

# Unit тесты
pytest -m unit

# Интеграционные тесты
pytest -m integration

# Тесты сценариев ошибок
pytest -m error_scenarios

# Конкретный файл
pytest tests/test_agents/test_task_agent.py

# Конкретный тест
pytest tests/test_agents/test_task_agent.py::TestTaskAgent::test_plan_task_success

# С подробным выводом
pytest -v

# С покрытием кода
pytest --cov=src --cov-report=html

# Параллельно
pytest -n auto
```

## Конфигурация тестов

### pytest.ini
Основная конфигурация pytest находится в файле `pytest.ini` в корне проекта.

### conftest.py
Общие фикстуры и настройки для всех тестов находятся в `tests/conftest.py`.

## Фикстуры

### Основные фикстуры
- `mock_agent_config` - Конфигурация агента
- `mock_server_config` - Конфигурация сервера
- `mock_ssh_connector` - SSH коннектор
- `mock_llm_interface` - LLM интерфейс
- `mock_task_master` - Task Master
- `sample_task` - Пример задачи
- `sample_subtask` - Пример подзадачи

### Использование фикстур

```python
def test_example(mock_agent_config, mock_ssh_connector):
    # Тест использует фикстуры
    agent = SomeAgent(mock_agent_config)
    result = agent.execute(mock_ssh_connector)
    assert result.success
```

## Маркеры тестов

### Доступные маркеры
- `unit` - Unit тесты
- `integration` - Интеграционные тесты
- `slow` - Медленные тесты
- `ssh` - Тесты, требующие SSH соединения
- `llm` - Тесты, требующие LLM API
- `mock` - Тесты с моками
- `error_scenarios` - Тесты сценариев ошибок
- `security` - Тесты безопасности
- `performance` - Тесты производительности

### Использование маркеров

```python
@pytest.mark.unit
def test_unit_function():
    pass

@pytest.mark.integration
def test_integration_workflow():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

## Покрытие кода

### Требования к покрытию
- Минимальное покрытие: 80%
- Критические компоненты: 90%+

### Генерация отчетов
```bash
# HTML отчет
pytest --cov=src --cov-report=html
open htmlcov/index.html

# XML отчет
pytest --cov=src --cov-report=xml

# Текстовый отчет
pytest --cov=src --cov-report=term-missing
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

### Запуск конкретного теста
```bash
pytest tests/test_agents/test_task_agent.py::TestTaskAgent::test_plan_task_success -v
```

### Отладка с pdb
```bash
pytest --pdb
```

## Лучшие практики

### Написание тестов
1. **Именование**: Используйте описательные имена тестов
2. **Изоляция**: Каждый тест должен быть независимым
3. **Моки**: Используйте моки для внешних зависимостей
4. **Фикстуры**: Переиспользуйте общие настройки через фикстуры
5. **Утверждения**: Используйте конкретные утверждения

### Структура тестов
```python
class TestComponent:
    def setup_method(self):
        """Настройка для каждого теста"""
        pass
    
    def test_success_case(self):
        """Тест успешного сценария"""
        # Arrange
        # Act
        # Assert
        pass
    
    def test_error_case(self):
        """Тест сценария ошибки"""
        # Arrange
        # Act
        # Assert
        pass
```

### Моки и фикстуры
```python
@pytest.fixture
def mock_dependency():
    mock = Mock()
    mock.method.return_value = "expected_value"
    return mock

def test_with_mock(mock_dependency):
    result = some_function(mock_dependency)
    assert result == "expected_value"
    mock_dependency.method.assert_called_once()
```

## CI/CD

### GitHub Actions
Тесты автоматически запускаются в CI/CD pipeline при каждом коммите.

### Локальная проверка
```bash
# Запустить все проверки как в CI
make ci
```

## Устранение неполадок

### Частые проблемы

1. **Импорты не работают**
   - Убедитесь, что `src/` добавлен в `PYTHONPATH`
   - Проверьте `conftest.py` на наличие правильных путей

2. **Тесты падают из-за таймаутов**
   - Используйте маркер `@pytest.mark.slow` для медленных тестов
   - Увеличьте таймауты в конфигурации

3. **Проблемы с моками**
   - Убедитесь, что моки правильно настроены
   - Проверьте, что моки не конфликтуют с реальными объектами

### Отладка
```bash
# Запуск с максимальной детализацией
pytest -vvv -s --tb=long

# Запуск только падающих тестов
pytest --lf

# Запуск с профилированием
pytest --profile
```

## Дополнительные ресурсы

- [Документация pytest](https://docs.pytest.org/)
- [Документация unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Руководство по тестированию Python](https://docs.python.org/3/library/unittest.html)
