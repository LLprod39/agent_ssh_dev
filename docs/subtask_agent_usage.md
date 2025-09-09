# Subtask Agent - Руководство по использованию

## Обзор

Subtask Agent - это компонент системы SSH Agent, отвечающий за разбиение основных шагов на детальные подзадачи с конкретными командами Linux. Он обеспечивает:

- Разбиение основных шагов на подзадачи
- Генерацию команд Linux для выполнения
- Систему health-check для проверки результатов
- Интеграцию с Task Master для улучшения планов

## Архитектура

### Основные компоненты

1. **SubtaskAgent** - основной класс агента
2. **Subtask** - модель подзадачи
3. **SubtaskPlanningContext** - контекст планирования
4. **LinuxCommandGenerator** - генератор команд Linux
5. **HealthChecker** - система проверки состояния

### Схема работы

```
Основной шаг → SubtaskAgent → LLM → Парсинг → Подзадачи → Валидация → Оптимизация
```

## Использование

### Базовое использование

```python
from src.agents.subtask_agent import SubtaskAgent, SubtaskPlanningContext
from src.config.agent_config import AgentConfig
from src.models.planning_model import TaskStep, Priority

# Загрузка конфигурации
config = AgentConfig.from_yaml("config/agent_config.yaml")

# Создание агента
subtask_agent = SubtaskAgent(config)

# Создание основного шага
step = TaskStep(
    title="Установка Nginx",
    description="Установить и настроить веб-сервер Nginx",
    priority=Priority.HIGH
)

# Создание контекста
context = SubtaskPlanningContext(
    step=step,
    server_info={"os": "linux", "arch": "x86_64"},
    os_type="ubuntu",
    installed_services=["ssh"],
    available_tools=["apt", "systemctl", "curl"],
    constraints=["Безопасные команды"],
    previous_subtasks=[],
    environment={}
)

# Планирование подзадач
result = subtask_agent.plan_subtasks(step, context)

if result.success:
    print(f"Создано {len(result.subtasks)} подзадач")
    for subtask in result.subtasks:
        print(f"- {subtask.title}")
        print(f"  Команды: {subtask.commands}")
        print(f"  Health-check: {subtask.health_checks}")
```

### Интеграция с Task Master

```python
from src.agents.task_master_integration import TaskMasterIntegration

# Создание Task Master интеграции
task_master = TaskMasterIntegration(config.taskmaster)

# Создание агента с Task Master
subtask_agent = SubtaskAgent(config, task_master)

# Планирование с улучшенными промтами
result = subtask_agent.plan_subtasks(step, context)
```

## Модель данных

### Subtask

```python
@dataclass
class Subtask:
    subtask_id: str
    title: str
    description: str
    commands: List[str]           # Команды для выполнения
    health_checks: List[str]      # Команды проверки
    expected_output: Optional[str] # Ожидаемый результат
    rollback_commands: List[str]   # Команды отката
    dependencies: List[str]        # Зависимости
    timeout: int                   # Таймаут выполнения
    retry_count: int              # Количество повторов
    max_retries: int              # Максимум повторов
    metadata: Dict[str, Any]      # Метаданные
```

### SubtaskPlanningContext

```python
@dataclass
class SubtaskPlanningContext:
    step: TaskStep                    # Основной шаг
    server_info: Dict[str, Any]       # Информация о сервере
    os_type: str                      # Тип ОС
    installed_services: List[str]     # Установленные сервисы
    available_tools: List[str]        # Доступные инструменты
    constraints: List[str]            # Ограничения
    previous_subtasks: List[Dict]     # Предыдущие подзадачи
    environment: Dict[str, Any]       # Окружение
```

## Генератор команд Linux

### Использование

```python
from src.utils.command_generator import LinuxCommandGenerator

generator = LinuxCommandGenerator()

# Генерация команд для установки пакета
commands = generator.generate_install_commands("nginx", "ubuntu")
# ['sudo apt update', 'sudo apt install -y nginx', 'dpkg -l | grep nginx']

# Генерация команд для управления сервисом
service_commands = generator.generate_service_commands("nginx", "start")
# ['sudo systemctl start nginx', 'sudo systemctl enable nginx', 'systemctl is-active nginx']

# Генерация команд для настройки Nginx
nginx_commands = generator.generate_nginx_setup_commands()

# Проверка безопасности команды
safety = generator.validate_command_safety("sudo apt update")
print(safety["is_safe"])  # True
```

### Доступные шаблоны команд

- **package_management**: управление пакетами
- **service_management**: управление сервисами
- **file_operations**: операции с файлами
- **network_operations**: сетевые операции
- **system_checks**: проверки системы

## Система Health-Check

### Использование

```python
from src.utils.health_checker import HealthChecker, HealthCheckConfig

checker = HealthChecker()

# Простая проверка
result = checker.run_health_check("systemctl is-active nginx", "service_active")

# Проверка с конфигурацией
config = HealthCheckConfig(
    timeout=30,
    retry_count=3,
    expected_exit_code=0,
    expected_output_pattern="active",
    critical=True
)
result = checker.run_health_check("systemctl is-active nginx", "service_active", config)

# Специализированные проверки
service_result = checker.check_service_status("nginx")
port_result = checker.check_port_listening(80)
http_result = checker.check_http_endpoint("http://localhost")

# Комплексные проверки
nginx_health = checker.check_nginx_health()
system_health = checker.check_system_health()

# Агрегация результатов
aggregated = checker.aggregate_results(nginx_health)
print(f"Общий статус: {aggregated['overall_status']}")
print(f"Успешность: {aggregated['success_rate']:.1f}%")
```

### Типы проверок

- **system_running**: состояние системы
- **service_active**: активность сервиса
- **port_listening**: прослушивание порта
- **disk_space**: дисковое пространство
- **memory_usage**: использование памяти
- **http_response**: HTTP ответ

## Конфигурация

### agent_config.yaml

```yaml
agents:
  subtask_agent:
    model: "gpt-4"
    temperature: 0.1
    max_subtasks: 20
    max_tokens: 3000
```

### Параметры конфигурации

- **model**: модель LLM для генерации
- **temperature**: температура генерации (0.0-2.0)
- **max_subtasks**: максимальное количество подзадач
- **max_tokens**: максимальное количество токенов

## Примеры

### Пример 1: Установка Nginx

```python
# Создание шага
step = TaskStep(
    title="Установка Nginx",
    description="Установить веб-сервер Nginx с базовой конфигурацией",
    priority=Priority.HIGH
)

# Планирование подзадач
result = subtask_agent.plan_subtasks(step, context)

# Результат:
# 1. Обновление системы
#    - sudo apt update
#    - apt list --upgradable | wc -l
# 2. Установка Nginx
#    - sudo apt install -y nginx
#    - dpkg -l | grep nginx
# 3. Запуск Nginx
#    - sudo systemctl start nginx
#    - sudo systemctl enable nginx
#    - systemctl is-active nginx
#    - curl -I http://localhost
```

### Пример 2: Настройка PostgreSQL

```python
step = TaskStep(
    title="Настройка PostgreSQL",
    description="Установить и настроить базу данных PostgreSQL",
    priority=Priority.HIGH
)

result = subtask_agent.plan_subtasks(step, context)

# Результат:
# 1. Установка PostgreSQL
#    - sudo apt update
#    - sudo apt install -y postgresql postgresql-contrib
#    - dpkg -l | grep postgresql
# 2. Запуск сервиса
#    - sudo systemctl start postgresql
#    - sudo systemctl enable postgresql
#    - systemctl is-active postgresql
# 3. Проверка подключения
#    - sudo -u postgres psql -c 'SELECT version();'
#    - netstat -tlnp | grep :5432
```

## Безопасность

### Проверка опасных команд

Система автоматически проверяет команды на наличие опасных паттернов:

- `rm -rf /` - удаление корневой директории
- `dd if=/dev/zero` - запись нулей в устройство
- `mkfs` - создание файловой системы
- `chmod 777 /` - изменение прав на корневую директорию
- `halt`, `poweroff`, `reboot` - команды выключения

### Валидация команд

```python
# Проверка безопасности
safety = generator.validate_command_safety("sudo apt update")
if not safety["is_safe"]:
    print(f"Опасная команда: {safety['dangerous_patterns']}")

# Валидация подзадач
validation = subtask_agent._validate_subtasks(subtasks, context)
if not validation["valid"]:
    print(f"Проблемы валидации: {validation['issues']}")
```

## Обработка ошибок

### Типы ошибок

1. **Ошибки LLM**: недоступность или некорректный ответ
2. **Ошибки парсинга**: невалидный JSON ответ
3. **Ошибки валидации**: небезопасные или некорректные команды
4. **Ошибки зависимостей**: циклические зависимости

### Обработка ошибок

```python
result = subtask_agent.plan_subtasks(step, context)

if not result.success:
    print(f"Ошибка планирования: {result.error_message}")
    
    # Логирование ошибки
    logger.error("Ошибка планирования подзадач", 
                error=result.error_message,
                step_id=step.step_id)
    
    # Попытка восстановления или эскалация
    if "LLM" in result.error_message:
        # Переключение на мок-режим
        pass
    elif "JSON" in result.error_message:
        # Попытка исправления JSON
        pass
```

## Мониторинг и логирование

### Логирование

```python
# Структурированное логирование
logger.info("Планирование подзадач завершено",
           step_id=step.step_id,
           subtasks_count=len(result.subtasks),
           duration=result.planning_duration)

# Логирование ошибок
logger.error("Ошибка планирования подзадач",
            error=result.error_message,
            step_id=step.step_id)
```

### Метрики

- Время планирования
- Количество подзадач
- Количество команд
- Количество health-check
- Использование LLM токенов
- Успешность валидации

## Тестирование

### Запуск тестов

```bash
# Запуск всех тестов
pytest tests/test_agents/test_subtask_agent.py

# Запуск конкретного теста
pytest tests/test_agents/test_subtask_agent.py::TestSubtaskAgent::test_plan_subtasks_success

# Запуск с покрытием
pytest --cov=src.agents.subtask_agent tests/test_agents/test_subtask_agent.py
```

### Примеры тестов

```python
def test_plan_subtasks_success():
    """Тест успешного планирования подзадач"""
    agent = SubtaskAgent(mock_config, mock_task_master)
    result = agent.plan_subtasks(sample_step, sample_context)
    
    assert result.success is True
    assert len(result.subtasks) > 0
    assert result.planning_duration is not None

def test_dangerous_command_detection():
    """Тест обнаружения опасных команд"""
    agent = SubtaskAgent(mock_config)
    
    assert agent._is_dangerous_command("sudo apt update") is False
    assert agent._is_dangerous_command("rm -rf /") is True
```

## Расширение функциональности

### Добавление новых типов команд

```python
# Расширение генератора команд
class CustomCommandGenerator(LinuxCommandGenerator):
    def generate_custom_commands(self, param):
        return [
            f"custom_command {param}",
            f"check_custom_result {param}"
        ]

# Добавление новых health-check
class CustomHealthChecker(HealthChecker):
    def check_custom_service(self):
        return self.run_health_check("custom_check_command", "custom_type")
```

### Кастомные валидаторы

```python
def custom_subtask_validator(subtasks, context):
    """Кастомная валидация подзадач"""
    issues = []
    
    for subtask in subtasks:
        # Кастомная логика валидации
        if "custom_pattern" in str(subtask.commands):
            issues.append("Найден кастомный паттерн")
    
    return {"valid": len(issues) == 0, "issues": issues}
```

## Заключение

Subtask Agent предоставляет мощный инструментарий для автоматизации планирования подзадач с использованием LLM. Он обеспечивает безопасность, валидацию и интеграцию с другими компонентами системы.

Ключевые преимущества:
- Автоматическая генерация команд Linux
- Система health-check для проверки результатов
- Интеграция с Task Master для улучшения промтов
- Валидация безопасности команд
- Гибкая конфигурация и расширяемость
