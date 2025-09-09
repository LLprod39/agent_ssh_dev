# CLI Интерфейс SSH Agent

SSH Agent предоставляет мощный командный интерфейс для автоматизации задач на удаленных серверах с использованием LLM.

## Установка и настройка

### 1. Инициализация конфигурации

```bash
# Создать файлы конфигурации
ssh-agent init

# Или с указанием путей
ssh-agent init --server-config my_server.yaml --agent-config my_agent.yaml
```

### 2. Редактирование конфигурации

Отредактируйте созданные файлы:
- `config/server_config.yaml` - настройки сервера
- `config/agent_config.yaml` - настройки агента и LLM

### 3. Валидация конфигурации

```bash
# Проверить корректность конфигурации
ssh-agent config validate
```

## Основные команды

### Выполнение задач

```bash
# Выполнить задачу
ssh-agent execute "Установить nginx на сервере"

# Предварительный просмотр (dry-run)
ssh-agent execute "Настроить SSL сертификат" --dry-run

# Подробный вывод
ssh-agent execute "Обновить систему" --verbose

# С указанием конфигурации
ssh-agent execute "Задача" --server-config prod.yaml --agent-config prod_agent.yaml
```

### Интерактивный режим

```bash
# Запустить интерактивный режим
ssh-agent interactive
```

В интерактивном режиме доступны команды:
- `execute <задача>` - выполнить задачу
- `dry-run <задача>` - предварительный просмотр
- `status` - показать статус агента
- `history [количество]` - показать историю выполнения
- `config` - показать текущую конфигурацию
- `cleanup [дни]` - очистить старые данные
- `help` - показать справку
- `exit` - выход

### Мониторинг и управление

```bash
# Показать статус агента
ssh-agent status

# Показать историю выполнения
ssh-agent history

# Показать последние 5 задач
ssh-agent history --limit 5

# Очистить старые данные
ssh-agent cleanup

# Очистить данные старше 3 дней
ssh-agent cleanup --days 3
```

### Управление конфигурацией

```bash
# Показать текущую конфигурацию
ssh-agent config show

# Валидировать конфигурацию
ssh-agent config validate

# Получить информацию о редактировании
ssh-agent config edit
```

## Параметры командной строки

### Общие параметры

- `--server-config`, `-s` - путь к файлу конфигурации сервера
- `--agent-config`, `-a` - путь к файлу конфигурации агента
- `--help`, `-h` - показать справку

### Параметры выполнения

- `--dry-run`, `-d` - режим предварительного просмотра
- `--verbose`, `-v` - подробный вывод
- `--interactive`, `-i` - интерактивный режим подтверждения

### Параметры очистки

- `--days`, `-d` - количество дней для хранения данных
- `--yes`, `-y` - подтвердить очистку без запроса

## Примеры использования

### Базовые задачи

```bash
# Установка пакетов
ssh-agent execute "Установить docker и docker-compose"

# Настройка сервисов
ssh-agent execute "Настроить nginx с SSL сертификатом"

# Обновление системы
ssh-agent execute "Обновить все пакеты системы"

# Создание пользователей
ssh-agent execute "Создать пользователя deploy с sudo правами"
```

### Сложные задачи

```bash
# Развертывание приложения
ssh-agent execute "Развернуть Django приложение с PostgreSQL и Redis"

# Настройка мониторинга
ssh-agent execute "Установить и настроить Prometheus с Grafana"

# Резервное копирование
ssh-agent execute "Настроить автоматическое резервное копирование базы данных"
```

### Предварительный просмотр

```bash
# Посмотреть что будет выполнено
ssh-agent execute "Установить LAMP стек" --dry-run

# Подробный просмотр
ssh-agent execute "Настроить кластер Docker Swarm" --dry-run --verbose
```

## Интерактивный режим

Интерактивный режим предоставляет удобный интерфейс для работы с агентом:

```bash
ssh-agent interactive
```

### Команды в интерактивном режиме

1. **Выполнение задач:**
   ```
   SSH Agent> execute Установить nginx
   SSH Agent> dry-run Настроить SSL
   ```

2. **Мониторинг:**
   ```
   SSH Agent> status
   SSH Agent> history 10
   ```

3. **Управление:**
   ```
   SSH Agent> config
   SSH Agent> cleanup 7
   ```

4. **Справка:**
   ```
   SSH Agent> help
   ```

## Конфигурация

### Server Config (server_config.yaml)

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
  installed_services:
    - "docker"
    - "nginx"
    - "postgresql"
```

### Agent Config (agent_config.yaml)

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
  
  subtask_agent:
    model: "gpt-4"
    temperature: 0.1
    max_subtasks: 20
  
  executor:
    max_retries_per_command: 2
    auto_correction_enabled: true
    dry_run_mode: false
  
  error_handler:
    error_threshold_per_step: 4
    send_to_planner_after_threshold: true
    human_escalation_threshold: 3

llm:
  api_key: "your-api-key"
  base_url: "https://api.openai.com/v1"
  max_tokens: 4000
  timeout: 60

logging:
  level: "INFO"
  file: "logs/ssh_agent.log"
```

## Безопасность

### Запрещенные команды

SSH Agent автоматически блокирует выполнение опасных команд:
- `rm -rf /` - удаление корневой файловой системы
- `dd if=/dev/zero` - перезапись диска
- `mkfs` - форматирование файловых систем
- `fdisk`, `parted` - изменение разделов диска

### Dry-run режим

Всегда используйте `--dry-run` для предварительного просмотра:
```bash
ssh-agent execute "Ваша задача" --dry-run
```

### Валидация конфигурации

Перед использованием проверьте конфигурацию:
```bash
ssh-agent config validate
```

## Устранение неполадок

### Проблемы с подключением

```bash
# Проверить статус агента
ssh-agent status

# Проверить конфигурацию
ssh-agent config validate
```

### Проблемы с выполнением

```bash
# Посмотреть историю ошибок
ssh-agent history --limit 20

# Очистить старые данные
ssh-agent cleanup --days 1
```

### Логи

Логи сохраняются в файл, указанный в конфигурации:
```bash
tail -f logs/ssh_agent.log
```

## Автодополнение

Для включения автодополнения в bash:

```bash
# Добавить в ~/.bashrc
eval "$(ssh-agent --install-completion bash)"
```

Для zsh:

```bash
# Добавить в ~/.zshrc
eval "$(ssh-agent --install-completion zsh)"
```

## Примеры сценариев

### Сценарий 1: Настройка нового сервера

```bash
# 1. Инициализация
ssh-agent init

# 2. Редактирование конфигурации
nano config/server_config.yaml
nano config/agent_config.yaml

# 3. Валидация
ssh-agent config validate

# 4. Предварительный просмотр
ssh-agent execute "Настроить базовую систему безопасности" --dry-run

# 5. Выполнение
ssh-agent execute "Настроить базовую систему безопасности"
```

### Сценарий 2: Развертывание приложения

```bash
# 1. Планирование
ssh-agent execute "Развернуть Django приложение" --dry-run --verbose

# 2. Выполнение
ssh-agent execute "Развернуть Django приложение"

# 3. Проверка статуса
ssh-agent status

# 4. Просмотр истории
ssh-agent history
```

### Сценарий 3: Интерактивная работа

```bash
# Запуск интерактивного режима
ssh-agent interactive

# В интерактивном режиме:
SSH Agent> execute Установить docker
SSH Agent> dry-run Настроить nginx
SSH Agent> status
SSH Agent> history 5
SSH Agent> exit
```

## Дополнительные возможности

### Интеграция с CI/CD

```bash
# В скрипте развертывания
ssh-agent execute "Развернуть приложение версии $VERSION" --server-config prod.yaml
```

### Мониторинг

```bash
# Регулярная проверка статуса
ssh-agent status > status.log

# Очистка старых данных
ssh-agent cleanup --days 7 --yes
```

### Автоматизация

```bash
# Создание скрипта
cat > deploy.sh << 'EOF'
#!/bin/bash
ssh-agent execute "Развернуть $1" --dry-run
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ssh-agent execute "Развернуть $1"
fi
EOF

chmod +x deploy.sh
./deploy.sh my-app
```
