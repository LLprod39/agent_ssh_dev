# Dry-Run Система - Руководство по использованию

## Обзор

Dry-Run система позволяет выполнять предварительный просмотр команд без их реального выполнения на сервере. Это критически важная функция для безопасности и планирования автоматизации.

## Основные возможности

### 1. Симуляция выполнения команд
- Предварительный просмотр результатов команд
- Анализ потенциальных проблем
- Оценка времени выполнения
- Проверка зависимостей

### 2. Анализ рисков
- Классификация команд по уровням риска (LOW, MEDIUM, HIGH, CRITICAL)
- Идентификация опасных команд
- Анализ побочных эффектов
- Рекомендации по безопасности

### 3. Валидация планов
- Проверка корректности планов выполнения
- Выявление циклических зависимостей
- Анализ порядка выполнения команд
- Проверка совместимости команд

### 4. Генерация отчетов
- Текстовые отчеты для консоли
- JSON отчеты для программной обработки
- Markdown отчеты для документации
- Детальная аналитика выполнения

## Конфигурация

### Настройки в agent_config.yaml

```yaml
agents:
  executor:
    dry_run_mode: false  # Включить/выключить dry-run режим
    dry_run_settings:
      enabled: true                    # Включить dry-run систему
      generate_reports: true          # Генерировать отчеты
      report_formats: ["text", "json", "markdown"]  # Форматы отчетов
      validate_plans: true            # Валидировать планы
      analyze_risks: true             # Анализировать риски
      require_confirmation_for_high_risk: true  # Требовать подтверждение
      log_simulations: true           # Логировать симуляции
```

## Использование

### Базовое использование

```python
from src.utils.dry_run_system import DryRunSystem
from src.utils.logger import StructuredLogger

# Создание системы dry-run
logger = StructuredLogger("MyApp")
dry_run_system = DryRunSystem(logger)

# Команды для симуляции
commands = [
    "apt update",
    "apt install -y nginx",
    "systemctl start nginx",
    "systemctl enable nginx"
]

# Выполнение симуляции
result = dry_run_system.simulate_execution(commands)

# Проверка результатов
print(f"Успешно: {result.success}")
print(f"Уровень риска: {result.risk_summary['overall_risk']}")
print(f"Требуется подтверждение: {result.risk_summary['requires_confirmation']}")
```

### Интеграция с Execution Model

```python
from src.models.execution_model import ExecutionModel
from src.models.execution_context import ExecutionContext
from src.agents.subtask_agent import Subtask

# Создание подзадачи
subtask = Subtask(
    subtask_id="install_nginx",
    title="Установка Nginx",
    description="Установка веб-сервера Nginx",
    commands=[
        "apt update",
        "apt install -y nginx",
        "systemctl start nginx"
    ],
    health_checks=[
        "systemctl is-active nginx",
        "curl -I http://localhost"
    ]
)

# Создание контекста выполнения
context = ExecutionContext(
    subtask=subtask,
    ssh_connection=ssh_connector,
    server_info={"os": "ubuntu", "version": "20.04"}
)

# Предварительный просмотр
execution_model = ExecutionModel(config, ssh_connector)
preview_result = execution_model.preview_execution(context)

# Валидация плана
validation_result = execution_model.validate_plan(context)

# Генерация отчета
report = execution_model.generate_execution_report(context, "text")
print(report)
```

## Анализ рисков

### Уровни риска

1. **LOW** - Безопасные команды
   - `apt update`
   - `ls -la`
   - `cat /etc/hosts`

2. **MEDIUM** - Команды с умеренным риском
   - `rm /tmp/test`
   - `systemctl stop nginx`
   - `chmod 644 file`

3. **HIGH** - Команды высокого риска
   - `chmod 777 /var/www`
   - `rm -rf /tmp`
   - `systemctl disable nginx`

4. **CRITICAL** - Критически опасные команды
   - `rm -rf /`
   - `dd if=/dev/zero of=/dev/sda`
   - `mkfs.ext4 /dev/sda1`

### Анализ команд

```python
# Анализ отдельной команды
analysis = dry_run_system._analyze_command("rm -rf /tmp/test", 0)

print(f"Тип команды: {analysis.command_type}")
print(f"Уровень риска: {analysis.risk_level}")
print(f"Потенциальные проблемы: {analysis.potential_issues}")
print(f"Зависимости: {analysis.dependencies}")
print(f"Побочные эффекты: {analysis.side_effects}")
print(f"Требуется подтверждение: {analysis.requires_confirmation}")
```

## Валидация планов

### Проверки валидации

1. **Критические команды** - наличие команд критического риска
2. **Зависимости** - корректность зависимостей между командами
3. **Порядок выполнения** - логическая последовательность команд
4. **Совместимость** - совместимость команд с системой

### Пример валидации

```python
# Валидация плана
validation_result = dry_run_system._validate_plan(commands_analysis)

if validation_result.valid:
    print("План валиден")
else:
    print("Проблемы в плане:")
    for issue in validation_result.issues:
        print(f"  ❌ {issue}")
    
    print("Предупреждения:")
    for warning in validation_result.warnings:
        print(f"  ⚠️  {warning}")
```

## Генерация отчетов

### Форматы отчетов

#### Текстовый отчет
```python
report = dry_run_system.generate_dry_run_report(result, "text")
print(report)
```

#### JSON отчет
```python
report = dry_run_system.generate_dry_run_report(result, "json")
data = json.loads(report)
```

#### Markdown отчет
```python
report = dry_run_system.generate_dry_run_report(result, "markdown")
```

### Структура отчета

```json
{
  "dry_run_result": {
    "success": true,
    "execution_summary": {
      "total_commands": 4,
      "successful_commands": 4,
      "failed_commands": 0,
      "success_rate": 100.0,
      "estimated_total_duration": 15.0
    },
    "risk_summary": {
      "overall_risk": "low",
      "risk_percentage": 25.0,
      "requires_confirmation": false,
      "risk_breakdown": {
        "critical": 0,
        "high": 0,
        "medium": 1,
        "low": 3
      }
    },
    "validation_result": {
      "valid": true,
      "issues": [],
      "warnings": [],
      "recommendations": []
    }
  },
  "simulated_commands": [
    {
      "command": "apt update",
      "success": true,
      "exit_code": 0,
      "stdout": "[DRY-RUN] Команда 'apt update' выполнена успешно",
      "stderr": null,
      "duration": 1.0,
      "metadata": {
        "dry_run": true,
        "command_type": "install",
        "risk_level": "low"
      }
    }
  ]
}
```

## Рекомендации по использованию

### 1. Всегда используйте dry-run перед реальным выполнением
```python
# Сначала предварительный просмотр
preview_result = execution_model.preview_execution(context)

if preview_result.risk_summary['requires_confirmation']:
    print("⚠️  Требуется подтверждение для выполнения")
    user_input = input("Продолжить? (y/N): ")
    if user_input.lower() != 'y':
        return

# Затем реальное выполнение
execution_model.execute_subtask(context)
```

### 2. Анализируйте отчеты
```python
# Генерация и анализ отчета
report = execution_model.generate_execution_report(context, "text")

# Проверка критических проблем
if "КРИТИЧЕСКАЯ КОМАНДА" in report:
    print("❌ Обнаружены критические команды!")
    return

# Проверка предупреждений
if "ПРЕДУПРЕЖДЕНИЯ:" in report:
    print("⚠️  Есть предупреждения, рекомендуется проверить")
```

### 3. Используйте валидацию планов
```python
# Валидация перед выполнением
validation_result = execution_model.validate_plan(context)

if not validation_result['valid']:
    print("❌ План не прошел валидацию:")
    for issue in validation_result['issues']:
        print(f"  - {issue}")
    return

# План валиден, можно выполнять
execution_model.execute_subtask(context)
```

### 4. Настройте логирование
```yaml
logging:
  level: "INFO"
  log_file: "logs/dry_run.log"
  error_file: "logs/dry_run_errors.log"
```

## Примеры использования

### Пример 1: Установка веб-сервера
```python
commands = [
    "apt update",
    "apt install -y nginx",
    "systemctl start nginx",
    "systemctl enable nginx",
    "ufw allow 'Nginx Full'"
]

result = dry_run_system.simulate_execution(commands)
# Результат: LOW риск, все команды безопасны
```

### Пример 2: Опасные команды
```python
dangerous_commands = [
    "apt update",           # LOW
    "rm -rf /tmp/test",     # MEDIUM
    "chmod 777 /var/www",   # HIGH
    "rm -rf /"              # CRITICAL
]

result = dry_run_system.simulate_execution(dangerous_commands)
# Результат: CRITICAL риск, требуется подтверждение
```

### Пример 3: Комплексная задача
```python
# Создание подзадачи
subtask = Subtask(
    subtask_id="setup_database",
    title="Настройка PostgreSQL",
    commands=[
        "apt update",
        "apt install -y postgresql postgresql-contrib",
        "systemctl start postgresql",
        "systemctl enable postgresql",
        "sudo -u postgres createuser --interactive"
    ],
    health_checks=[
        "systemctl is-active postgresql",
        "sudo -u postgres psql -c '\\l'"
    ]
)

# Предварительный просмотр
context = ExecutionContext(subtask=subtask, ...)
preview = execution_model.preview_execution(context)

# Анализ результатов
print(f"Риск: {preview.risk_summary['overall_risk']}")
print(f"Время: {preview.execution_summary['estimated_total_duration']}с")
```

## Обработка ошибок

### Обработка ошибок симуляции
```python
try:
    result = dry_run_system.simulate_execution(commands)
except Exception as e:
    print(f"Ошибка симуляции: {e}")
    # Обработка ошибки
```

### Обработка ошибок валидации
```python
validation_result = execution_model.validate_plan(context)

if not validation_result['valid']:
    # Логирование проблем
    logger.error("План не прошел валидацию", 
                issues=validation_result['issues'])
    
    # Уведомление пользователя
    notify_user("План содержит проблемы", validation_result['issues'])
```

## Интеграция с другими системами

### Интеграция с системой безопасности
```python
# Проверка через систему безопасности
if not ssh_connector.is_command_safe(command):
    print(f"Команда заблокирована: {command}")
    return

# Dry-run анализ
analysis = dry_run_system._analyze_command(command, 0)
if analysis.risk_level == RiskLevel.CRITICAL:
    print(f"Критическая команда: {command}")
```

### Интеграция с системой идемпотентности
```python
# Проверка идемпотентности
if idempotency_system.should_skip_command(command, checks):
    print(f"Команда пропущена (идемпотентность): {command}")
    return

# Dry-run анализ
preview = execution_model.preview_execution(context)
```

## Заключение

Dry-Run система является критически важным компонентом для безопасной автоматизации. Она позволяет:

- Предварительно просматривать результаты команд
- Анализировать риски и потенциальные проблемы
- Валидировать планы выполнения
- Генерировать детальные отчеты

Используйте dry-run режим всегда перед реальным выполнением команд, особенно в production среде.
