# SSH Agent с LLM

Автоматизированная система для выполнения задач на удаленных серверах через SSH с использованием LLM для планирования и выполнения команд.

## Возможности

- 🤖 **Многоуровневое планирование** - разбиение задач на основные шаги и подзадачи
- 🔧 **Автоматическая коррекция ошибок** - система автокоррекции с множественными стратегиями
- 🔒 **Безопасность** - проверка запрещенных команд и валидация
- 📊 **Мониторинг** - детальное логирование и отчеты о выполнении
- 🎯 **Task Master интеграция** - улучшение промтов через light-task-master
- 🔄 **Идемпотентность** - безопасное повторное выполнение задач с проверками состояния
- 📸 **Снимки состояния** - создание и восстановление состояний системы
- ⏪ **Система отката** - автоматический откат изменений при ошибках

## Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Task Master   │    │   Task Agent    │    │  Subtask Agent  │
│   Integration   │───▶│  (Планирование) │───▶│ (Детализация)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Error Handler  │◀───│  Execution      │
                       │  (Обработка)    │    │  Model          │
                       └─────────────────┘    └─────────────────┘
                                                       │
                                               ┌─────────────────┐
                                               │  SSH Connector  │
                                               │  (Выполнение)   │
                                               └─────────────────┘
```

## Установка

### Требования

- Python 3.9+
- Node.js 18+
- SSH доступ к целевым серверам

### Быстрая установка

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd agent_ssh_dev

# 2. Создайте виртуальное окружение Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# 3. Установите Python зависимости
pip install -r requirements.txt

# 4. Установите Node.js зависимости (для Task Master)
npm install

# 5. Инициализируйте конфигурацию
python -m src.main init
```

### Установка зависимостей

```bash
# Python зависимости
pip install -r requirements.txt

# Node.js зависимости (для Task Master)
npm install
```

### Настройка

1. Скопируйте примеры конфигурации:
```bash
cp config/server_config.yaml.example config/server_config.yaml
cp config/agent_config.yaml.example config/agent_config.yaml
```

2. Настройте параметры сервера в `config/server_config.yaml`
3. Настройте параметры агентов в `config/agent_config.yaml`

## Использование

### Базовое использование
```python
from agent_ssh_dev import SSHAgent

# Инициализация агента
agent = SSHAgent(
    server_config="config/server_config.yaml",
    agent_config="config/agent_config.yaml"
)

# Выполнение задачи
result = agent.execute_task("Установить и настроить PostgreSQL на сервере")
print(result)
```

### CLI использование

```bash
# Выполнение задачи
ssh-agent execute "Установить nginx"

# Dry-run режим
ssh-agent execute "Настроить SSL" --dry-run

# Интерактивный режим
ssh-agent interactive
```

## Конфигурация

### server_config.yaml

```yaml
server:
  host: "example.com"
  port: 22
  username: "user"
  auth_method: "key"  # key, password
  key_path: "/path/to/private/key"
  timeout: 30
  os_type: "ubuntu"  # ubuntu, centos, debian
  forbidden_commands:
    - "rm -rf /"
    - "dd if=/dev/zero"
    - "mkfs"
```

### agent_config.yaml

```yaml
agents:
  taskmaster:
    enabled: true
    model: "gpt-4"
    temperature: 0.7
  
  task_agent:
    model: "gpt-4"
    temperature: 0.3
    max_steps: 10
  
  executor:
    max_retries_per_command: 2
    auto_correction_enabled: true
    dry_run_mode: false
```

## Разработка

### Установка для разработки

```bash
pip install -e ".[dev]"
```

### Запуск тестов

```bash
pytest
```

### Форматирование кода

```bash
black src/
isort src/
```

## Идемпотентность

Система обеспечивает безопасное повторное выполнение операций без побочных эффектов:

### Основные возможности

- **Генерация идемпотентных команд** - автоматическое преобразование команд в безопасные для повторного выполнения
- **Проверки состояния** - анализ текущего состояния системы перед выполнением команд
- **Снимки состояния** - создание точек восстановления для отката изменений
- **Система отката** - автоматический откат к предыдущему состоянию при ошибках

### Примеры идемпотентных команд

```bash
# Обычная команда
apt-get install nginx

# Идемпотентная команда
dpkg -l | grep -q '^ii  nginx' || apt-get install -y nginx
```

### Использование

```python
from src.utils.idempotency_system import IdempotencySystem

# Создание системы идемпотентности
idempotency_system = IdempotencySystem(ssh_connector, config)

# Создание снимка состояния
snapshot = idempotency_system.create_state_snapshot("task_001")

# Генерация идемпотентной команды
cmd, checks = idempotency_system.generate_idempotent_command(
    "apt-get install nginx", "install_package", "nginx"
)

# Проверка необходимости выполнения
should_skip = idempotency_system.should_skip_command(cmd, checks)
```

Подробнее см. [Документацию по идемпотентности](docs/idempotency_system.md)

## Безопасность

- ✅ Проверка запрещенных команд
- ✅ Dry-run режим для предварительного просмотра
- ✅ Валидация команд перед выполнением
- ✅ Безопасное хранение учетных данных
- ✅ Детальное логирование всех операций
- ✅ Идемпотентность для безопасного повторного выполнения

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создайте issue в репозитории.
