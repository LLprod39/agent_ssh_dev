# Система автокоррекции SSH Agent

## Обзор

Система автокоррекции SSH Agent представляет собой интеллектуальный механизм автоматического исправления ошибок при выполнении команд на удаленных серверах. Система анализирует ошибки выполнения и применяет различные стратегии для их исправления без вмешательства человека.

## Архитектура

### Основные компоненты

1. **AutocorrectionEngine** - основной движок автокоррекции
2. **CorrectionStrategy** - перечисление стратегий исправления
3. **CorrectionAttempt** - класс для хранения попыток исправления
4. **AutocorrectionResult** - результат процесса автокоррекции

### Стратегии исправления

#### 1. SYNTAX_CHECK - Проверка синтаксических ошибок
- Исправление двойных пробелов
- Замена неправильных кавычек
- Исправление неправильных слешей
- Нормализация синтаксиса команд

**Пример:**
```bash
# Исходная команда
ls  -la   /tmp

# Исправленная команда
ls -la /tmp
```

#### 2. PERMISSION_FIX - Исправление ошибок прав доступа
- Автоматическое добавление `sudo` для команд, требующих повышенных прав
- Определение команд, которые обычно требуют sudo

**Пример:**
```bash
# Исходная команда
apt install nginx

# Исправленная команда
sudo apt install nginx
```

#### 3. ALTERNATIVE_FLAGS - Альтернативные флаги команд
- Использование альтернативных флагов для команд
- Замена несуществующих опций на рабочие аналоги

**Пример:**
```bash
# Исходная команда
ls -l

# Исправленная команда (если -l не работает)
ls -la
```

#### 4. NETWORK_CHECK - Проверка сетевого соединения
- Проверка доступности сети перед выполнением сетевых команд
- Добавление ping-проверки для curl/wget команд

**Пример:**
```bash
# Исходная команда
curl -O https://example.com/file.txt

# Исправленная команда
ping -c 1 8.8.8.8 > /dev/null 2>&1 && curl -O https://example.com/file.txt
```

#### 5. SERVICE_RESTART - Перезапуск сервисов
- Перезагрузка демона systemd перед перезапуском сервиса
- Исправление проблем с сервисами

**Пример:**
```bash
# Исходная команда
systemctl start nginx

# Исправленная команда
sudo systemctl daemon-reload && sudo systemctl restart nginx
```

#### 6. PACKAGE_UPDATE - Обновление пакетов
- Автоматическое обновление списка пакетов перед установкой
- Исправление проблем с репозиториями

**Пример:**
```bash
# Исходная команда
apt install nginx

# Исправленная команда
sudo apt update && apt install nginx
```

#### 7. PATH_CORRECTION - Исправление путей
- Создание необходимых директорий
- Исправление относительных путей

**Пример:**
```bash
# Исходная команда
mkdir /var/log/test

# Исправленная команда
sudo mkdir /var/log/test
```

#### 8. COMMAND_SUBSTITUTION - Замена команд
- Замена устаревших команд на современные аналоги
- Использование альтернативных утилит

**Пример:**
```bash
# Исходная команда
service nginx start

# Исправленная команда
systemctl nginx start
```

## Конфигурация

### Настройки в agent_config.yaml

```yaml
agents:
  executor:
    # Основные настройки
    max_retries_per_command: 2
    auto_correction_enabled: true
    dry_run_mode: false
    command_timeout: 30
    
    # Настройки автокоррекции
    autocorrection_max_attempts: 3
    autocorrection_timeout: 30
    enable_syntax_correction: true
    enable_permission_correction: true
    enable_network_correction: true
    enable_service_correction: true
    enable_package_correction: true
    enable_command_substitution: true
```

### Параметры конфигурации

- **autocorrection_max_attempts** - максимальное количество попыток исправления (1-10)
- **autocorrection_timeout** - таймаут для автокоррекции в секундах (5-120)
- **enable_*_correction** - включение/отключение конкретных стратегий исправления

## Использование

### Базовое использование

```python
from src.utils.autocorrection import AutocorrectionEngine
from src.models.execution_model import CommandResult, ExecutionStatus

# Создание движка автокоррекции
engine = AutocorrectionEngine(max_attempts=3, timeout=30)

# Создание результата с ошибкой
command_result = CommandResult(
    command="apt install nginx",
    success=False,
    exit_code=1,
    stderr="permission denied",
    status=ExecutionStatus.FAILED,
    error_message="permission denied"
)

# Применение автокоррекции
result = engine.correct_command(command_result, context)

if result.success:
    print(f"Команда исправлена: {result.final_command}")
else:
    print("Автокоррекция не удалась")
```

### Интеграция с Execution Model

Система автокоррекции автоматически интегрируется с Execution Model:

```python
from src.models.execution_model import ExecutionModel

# Execution Model автоматически использует автокоррекцию
execution_model = ExecutionModel(config, ssh_connector, task_master)

# При выполнении подзадачи автокоррекция применяется автоматически
result = execution_model.execute_subtask(context)
```

## Статистика и мониторинг

### Получение статистики

```python
# Статистика движка автокоррекции
stats = engine.get_correction_stats()
print(f"Максимальные попытки: {stats['max_attempts']}")
print(f"Таймаут: {stats['timeout']}")

# Статистика выполнения с автокоррекцией
execution_stats = execution_model.get_execution_stats()
print(f"Всего автокоррекций: {execution_stats['autocorrections']}")
print(f"Успешных автокоррекций: {execution_stats['autocorrection_successes']}")
```

### Логирование

Система автокоррекции ведет подробное логирование:

```python
# Логи автокоррекции
logger.info("Начало автокоррекции команды", 
           original_command="apt install nginx",
           error_message="permission denied")

logger.info("Применение автокоррекции",
           original_command="apt install nginx", 
           corrected_command="sudo apt install nginx",
           strategy="permission_fix")
```

## Расширение системы

### Добавление новых стратегий

```python
class CustomCorrectionStrategy(Enum):
    CUSTOM_FIX = "custom_fix"

# Расширение движка
class CustomAutocorrectionEngine(AutocorrectionEngine):
    def _apply_custom_fix(self, command: str, error_message: str) -> Optional[str]:
        # Ваша логика исправления
        return corrected_command
```

### Добавление новых паттернов ошибок

```python
# Добавление в AutocorrectionEngine
self.syntax_patterns["custom_error"] = re.compile(r"custom error pattern")
```

## Тестирование

### Запуск тестов

```bash
# Запуск всех тестов автокоррекции
python -m pytest tests/test_utils/test_autocorrection.py -v

# Запуск примера
python examples/autocorrection_example.py
```

### Тестовые сценарии

1. **Синтаксические ошибки** - тестирование исправления синтаксиса
2. **Ошибки прав доступа** - тестирование добавления sudo
3. **Сетевые ошибки** - тестирование проверки сети
4. **Ошибки сервисов** - тестирование перезапуска сервисов
5. **Ошибки пакетов** - тестирование обновления репозиториев
6. **Замена команд** - тестирование замены устаревших команд

## Ограничения и рекомендации

### Ограничения

1. **Безопасность** - система не выполняет опасные команды
2. **Контекст** - исправления основаны на общих паттернах
3. **Производительность** - множественные попытки могут замедлить выполнение

### Рекомендации

1. **Настройка таймаутов** - установите разумные таймауты для вашей сети
2. **Мониторинг** - отслеживайте статистику автокоррекции
3. **Тестирование** - тестируйте автокоррекцию в безопасной среде
4. **Логирование** - включите подробное логирование для отладки

## Примеры использования

### Пример 1: Исправление ошибки прав доступа

```python
# Исходная команда
command = "apt install nginx"
error = "permission denied"

# Результат автокоррекции
corrected = "sudo apt install nginx"
strategy = "permission_fix"
```

### Пример 2: Исправление сетевой ошибки

```python
# Исходная команда
command = "curl https://example.com"
error = "connection refused"

# Результат автокоррекции
corrected = "ping -c 1 8.8.8.8 > /dev/null 2>&1 && curl https://example.com"
strategy = "network_check"
```

### Пример 3: Замена устаревшей команды

```python
# Исходная команда
command = "service nginx start"
error = "command not found"

# Результат автокоррекции
corrected = "systemctl nginx start"
strategy = "command_substitution"
```

## Заключение

Система автокоррекции SSH Agent значительно повышает надежность автоматизированного выполнения задач на удаленных серверах. Благодаря множественным стратегиям исправления и интеллектуальному анализу ошибок, система способна автоматически решать большинство типичных проблем без вмешательства человека.

Ключевые преимущества:
- **Автоматичность** - исправления применяются без участия человека
- **Множественность стратегий** - различные подходы к исправлению ошибок
- **Настраиваемость** - гибкая конфигурация под конкретные нужды
- **Мониторинг** - подробная статистика и логирование
- **Безопасность** - защита от выполнения опасных команд
