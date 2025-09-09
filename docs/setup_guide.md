# Руководство по настройке SSH Agent

## Содержание

1. [Системные требования](#системные-требования)
2. [Установка](#установка)
3. [Первоначальная настройка](#первоначальная-настройка)
4. [Конфигурация сервера](#конфигурация-сервера)
5. [Конфигурация агентов](#конфигурация-агентов)
6. [Настройка безопасности](#настройка-безопасности)
7. [Настройка LLM](#настройка-llm)
8. [Настройка Task Master](#настройка-task-master)
9. [Тестирование конфигурации](#тестирование-конфигурации)
10. [Устранение неполадок](#устранение-неполадок)

## Системные требования

### Минимальные требования

- **Python**: 3.9 или выше
- **Node.js**: 18.0 или выше
- **ОС**: Linux, macOS, Windows
- **Память**: 2 GB RAM
- **Диск**: 1 GB свободного места

### Рекомендуемые требования

- **Python**: 3.11 или выше
- **Node.js**: 20.0 или выше
- **Память**: 4 GB RAM
- **Диск**: 5 GB свободного места
- **Сеть**: Стабильное интернет-соединение для LLM API

### Целевые серверы

- **SSH доступ**: Обязательно
- **ОС**: Ubuntu 18.04+, CentOS 7+, Debian 10+
- **Права**: sudo доступ для выполнения команд
- **Сеть**: Доступ к интернету для загрузки пакетов

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd agent_ssh_dev
```

### 2. Создание виртуального окружения

```bash
# Создание виртуального окружения
python -m venv venv

# Активация (Linux/macOS)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate
```

### 3. Установка Python зависимостей

```bash
# Установка основных зависимостей
pip install -r requirements.txt

# Установка зависимостей для разработки (опционально)
pip install -r requirements-test.txt
```

### 4. Установка Node.js зависимостей

```bash
# Установка зависимостей для Task Master
npm install
```

### 5. Инициализация конфигурации

```bash
# Создание конфигурационных файлов
python -m src.main init
```

## Первоначальная настройка

### Создание структуры проекта

```bash
# Создание необходимых директорий
mkdir -p logs
mkdir -p .taskmaster/docs
mkdir -p .taskmaster/tasks
mkdir -p .taskmaster/templates
```

### Настройка прав доступа

```bash
# Установка прав на конфигурационные файлы
chmod 600 config/server_config.yaml
chmod 600 config/agent_config.yaml

# Установка прав на SSH ключи (если используются)
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

## Конфигурация сервера

### Базовая конфигурация (server_config.yaml)

```yaml
server:
  # Основные параметры подключения
  host: "your-server.com"           # IP адрес или домен сервера
  port: 22                          # SSH порт (по умолчанию 22)
  username: "deploy"                # Имя пользователя для SSH
  auth_method: "key"                # "key" или "password"
  
  # Аутентификация по ключу
  key_path: "/home/user/.ssh/id_rsa"  # Путь к приватному ключу
  key_passphrase: ""                # Пароль для ключа (если есть)
  
  # Аутентификация по паролю
  password: ""                      # Пароль (не рекомендуется)
  
  # Параметры соединения
  timeout: 30                       # Таймаут подключения в секундах
  keepalive: True                   # Поддержание соединения
  keepalive_interval: 30            # Интервал keepalive
  
  # Информация о системе
  os_type: "ubuntu"                 # "ubuntu", "centos", "debian"
  os_version: "22.04"               # Версия ОС
  
  # Безопасность
  forbidden_commands:               # Запрещенные команды
    - "rm -rf /"
    - "dd if=/dev/zero"
    - "mkfs"
    - "fdisk"
    - "parted"
    - "mkfs.ext4 /dev/sda1"
    - "shutdown"
    - "reboot"
    - "halt"
    - "poweroff"
  
  # Установленные сервисы
  installed_services:
    - "docker"
    - "nginx"
    - "postgresql"
    - "redis"
    - "systemd"
  
  # Дополнительные инструменты
  available_tools:
    - "apt"
    - "systemctl"
    - "docker"
    - "nginx"
    - "curl"
    - "wget"
    - "git"
    - "python3"
    - "pip"
  
  # Переменные окружения
  environment:
    DEBIAN_FRONTEND: "noninteractive"
    PYTHONUNBUFFERED: "1"
```

### Расширенная конфигурация

```yaml
server:
  # Множественные серверы
  servers:
    - name: "web-server"
      host: "web.example.com"
      port: 22
      username: "webuser"
      auth_method: "key"
      key_path: "/home/user/.ssh/web_key"
      os_type: "ubuntu"
      role: "web"
    
    - name: "db-server"
      host: "db.example.com"
      port: 2222
      username: "dbuser"
      auth_method: "key"
      key_path: "/home/user/.ssh/db_key"
      os_type: "centos"
      role: "database"
  
  # Прокси настройки
  proxy:
    enabled: false
    host: "proxy.example.com"
    port: 8080
    username: ""
    password: ""
  
  # SSH туннели
  tunnels:
    - name: "database-tunnel"
      local_port: 5432
      remote_host: "localhost"
      remote_port: 5432
  
  # Мониторинг
  monitoring:
    enabled: true
    health_check_interval: 60
    metrics_endpoint: "http://localhost:9090/metrics"
```

## Конфигурация агентов

### Базовая конфигурация (agent_config.yaml)

```yaml
# Конфигурация LLM
llm:
  api_key: "your-openai-api-key"    # API ключ OpenAI
  base_url: "https://api.openai.com/v1"  # Базовый URL API
  model: "gpt-4"                    # Модель для использования
  temperature: 0.1                  # Температура генерации
  max_tokens: 4000                  # Максимальное количество токенов
  timeout: 60                       # Таймаут запроса в секундах
  retry_attempts: 3                 # Количество попыток повтора
  retry_delay: 2                    # Задержка между попытками

# Конфигурация Task Master
taskmaster:
  enabled: true                     # Включить Task Master
  project_path: "."                 # Путь к проекту Task Master
  model: "gpt-4"                    # Модель для Task Master
  temperature: 0.7                  # Температура для планирования
  max_tokens: 2000                  # Максимальные токены для планирования

# Конфигурация Task Agent
task_agent:
  model: "gpt-4"                    # Модель для планирования задач
  temperature: 0.3                  # Температура для планирования
  max_steps: 10                     # Максимальное количество шагов
  planning_timeout: 120             # Таймаут планирования
  retry_planning: 2                 # Количество попыток планирования

# Конфигурация Subtask Agent
subtask_agent:
  model: "gpt-4"                    # Модель для детального планирования
  temperature: 0.1                  # Низкая температура для точности
  max_subtasks: 20                  # Максимальное количество подзадач
  command_generation_timeout: 60    # Таймаут генерации команд
  health_check_enabled: true        # Включить проверки здоровья

# Конфигурация Execution Model
executor:
  max_retries_per_command: 2        # Максимальные повторы команды
  auto_correction_enabled: true     # Включить автокоррекцию
  dry_run_mode: false               # Режим dry-run по умолчанию
  command_timeout: 300              # Таймаут выполнения команды
  parallel_execution: false         # Параллельное выполнение
  max_parallel_commands: 3          # Максимум параллельных команд

# Конфигурация Error Handler
error_handler:
  error_threshold_per_step: 4       # Порог ошибок на шаг
  send_to_planner_after_threshold: true  # Отправка планировщику
  human_escalation_threshold: 3     # Порог эскалации к человеку
  error_reporting_enabled: true     # Включить отчеты об ошибках
  auto_rollback_enabled: true       # Автоматический откат
  rollback_timeout: 600             # Таймаут отката

# Конфигурация логирования
logging:
  level: "INFO"                     # Уровень логирования
  file: "logs/ssh_agent.log"        # Файл логов
  max_size: "10MB"                  # Максимальный размер файла
  backup_count: 5                   # Количество резервных файлов
  format: "json"                    # Формат логов (json/text)
  console_output: true              # Вывод в консоль

# Конфигурация уведомлений
notifications:
  enabled: true                     # Включить уведомления
  email:
    enabled: false
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: ""
    password: ""
    to_addresses: []
  
  slack:
    enabled: false
    webhook_url: ""
    channel: "#alerts"
  
  webhook:
    enabled: false
    url: ""
    timeout: 30
```

### Расширенная конфигурация

```yaml
# Конфигурация для продакшена
production:
  llm:
    api_key: "${OPENAI_API_KEY}"    # Из переменной окружения
    model: "gpt-4"
    temperature: 0.05               # Очень низкая температура
    max_tokens: 2000
    timeout: 30
  
  executor:
    max_retries_per_command: 1      # Меньше повторов в продакшене
    auto_correction_enabled: true
    dry_run_mode: false
    command_timeout: 180            # Короче таймаут
  
  error_handler:
    error_threshold_per_step: 2     # Строже пороги
    human_escalation_threshold: 1   # Быстрая эскалация
    auto_rollback_enabled: true
  
  logging:
    level: "WARNING"                # Только предупреждения и ошибки
    file: "/var/log/ssh_agent.log"
    max_size: "50MB"
    backup_count: 10

# Конфигурация для разработки
development:
  llm:
    api_key: "your-dev-api-key"
    model: "gpt-3.5-turbo"          # Более дешевая модель
    temperature: 0.3
    max_tokens: 1000
  
  executor:
    max_retries_per_command: 3      # Больше повторов для отладки
    auto_correction_enabled: true
    dry_run_mode: true              # По умолчанию dry-run
  
  error_handler:
    error_threshold_per_step: 5     # Более мягкие пороги
    human_escalation_threshold: 5
  
  logging:
    level: "DEBUG"                  # Подробное логирование
    console_output: true
```

## Настройка безопасности

### 1. SSH ключи

```bash
# Генерация SSH ключа
ssh-keygen -t rsa -b 4096 -C "ssh-agent@yourdomain.com"

# Копирование публичного ключа на сервер
ssh-copy-id -i ~/.ssh/id_rsa.pub user@your-server.com

# Тестирование подключения
ssh -i ~/.ssh/id_rsa user@your-server.com
```

### 2. Настройка sudo

```bash
# Создание файла sudoers для агента
sudo visudo -f /etc/sudoers.d/ssh-agent

# Содержимое файла:
# deploy ALL=(ALL) NOPASSWD: /usr/bin/apt, /usr/bin/systemctl, /usr/bin/docker
# deploy ALL=(ALL) NOPASSWD: /usr/bin/nginx, /usr/bin/curl, /usr/bin/wget
```

### 3. Ограничение доступа

```yaml
# В server_config.yaml
server:
  security:
    # Ограничение по IP
    allowed_ips:
      - "192.168.1.0/24"
      - "10.0.0.0/8"
    
    # Ограничение по времени
    allowed_hours:
      start: 8
      end: 18
    
    # Ограничение команд
    command_whitelist:
      - "apt"
      - "systemctl"
      - "docker"
      - "nginx"
      - "curl"
      - "wget"
    
    # Запрещенные директории
    forbidden_paths:
      - "/etc/shadow"
      - "/etc/passwd"
      - "/root"
      - "/boot"
```

### 4. Шифрование конфигурации

```bash
# Установка ansible-vault для шифрования
pip install ansible

# Шифрование конфигурации
ansible-vault encrypt config/server_config.yaml
ansible-vault encrypt config/agent_config.yaml

# Расшифровка при использовании
ansible-vault decrypt config/server_config.yaml
```

## Настройка LLM

### 1. OpenAI API

```yaml
# В agent_config.yaml
llm:
  api_key: "sk-your-openai-api-key"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4"
  temperature: 0.1
  max_tokens: 4000
  timeout: 60
```

### 2. Альтернативные провайдеры

```yaml
# Anthropic Claude
llm:
  api_key: "your-anthropic-key"
  base_url: "https://api.anthropic.com/v1"
  model: "claude-3-sonnet-20240229"
  temperature: 0.1

# Google Gemini
llm:
  api_key: "your-google-key"
  base_url: "https://generativelanguage.googleapis.com/v1"
  model: "gemini-pro"
  temperature: 0.1

# Локальная модель (Ollama)
llm:
  api_key: "dummy"
  base_url: "http://localhost:11434/v1"
  model: "llama2"
  temperature: 0.1
```

### 3. Переменные окружения

```bash
# Установка переменных окружения
export OPENAI_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export GOOGLE_API_KEY="your-google-key"

# Или в .env файле
echo "OPENAI_API_KEY=your-api-key" > .env
echo "ANTHROPIC_API_KEY=your-anthropic-key" >> .env
```

## Настройка Task Master

### 1. Инициализация Task Master

```bash
# Инициализация в проекте
npx task-master-ai init

# Создание PRD (Product Requirements Document)
cat > .taskmaster/docs/prd.txt << EOF
# SSH Agent Requirements

## Цель
Автоматизация выполнения задач на удаленных серверах через SSH с использованием LLM.

## Основные функции
- Планирование задач с помощью LLM
- Выполнение команд через SSH
- Автоматическая коррекция ошибок
- Мониторинг и отчетность

## Ограничения
- Только безопасные команды
- Dry-run режим по умолчанию
- Эскалация к человеку при критических ошибках
EOF
```

### 2. Конфигурация Task Master

```json
// .taskmaster/config.json
{
  "project": {
    "name": "SSH Agent",
    "description": "Automated SSH task execution with LLM",
    "version": "1.0.0"
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "maxTokens": 2000
  },
  "planning": {
    "maxSteps": 10,
    "timeout": 120,
    "retryAttempts": 2
  },
  "execution": {
    "dryRun": true,
    "maxRetries": 3,
    "timeout": 300
  }
}
```

### 3. Шаблоны задач

```yaml
# .taskmaster/templates/web-server-setup.yaml
name: "Web Server Setup"
description: "Setup and configure web server"
steps:
  - name: "Install packages"
    commands:
      - "apt update"
      - "apt install -y nginx"
  - name: "Configure nginx"
    commands:
      - "systemctl enable nginx"
      - "systemctl start nginx"
  - name: "Setup SSL"
    commands:
      - "certbot --nginx -d example.com"
```

## Тестирование конфигурации

### 1. Проверка подключения

```bash
# Тест SSH подключения
python -c "
from src.connectors.ssh_connector import SSHConnector
from src.config.server_config import ServerConfig

config = ServerConfig.from_yaml('config/server_config.yaml')
connector = SSHConnector(config)

import asyncio
async def test():
    if await connector.connect():
        print('✅ SSH подключение успешно')
        await connector.disconnect()
    else:
        print('❌ Ошибка SSH подключения')

asyncio.run(test())
"
```

### 2. Тест LLM подключения

```bash
# Тест LLM API
python -c "
from src.config.agent_config import AgentConfig
from src.models.llm_interface import LLMInterface

config = AgentConfig.from_yaml('config/agent_config.yaml')
llm = LLMInterface(config.llm)

import asyncio
async def test():
    response = await llm.generate_response('Test message')
    if response:
        print('✅ LLM подключение успешно')
    else:
        print('❌ Ошибка LLM подключения')

asyncio.run(test())
"
```

### 3. Полный тест системы

```bash
# Запуск полного теста
python -m src.main execute "Проверить статус системы" --dry-run
```

### 4. Автоматические тесты

```bash
# Запуск unit тестов
pytest tests/

# Запуск интеграционных тестов
pytest tests/integration/

# Запуск тестов с покрытием
pytest --cov=src tests/
```

## Устранение неполадок

### Частые проблемы

#### 1. Ошибка SSH подключения

```bash
# Проверка SSH ключей
ssh-add -l

# Тест подключения
ssh -v user@server.com

# Проверка прав доступа
ls -la ~/.ssh/
```

**Решение:**
- Проверить правильность пути к ключу
- Убедиться в правильности прав доступа (600)
- Проверить доступность сервера

#### 2. Ошибка LLM API

```bash
# Проверка API ключа
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

**Решение:**
- Проверить правильность API ключа
- Убедиться в наличии средств на счете
- Проверить доступность API

#### 3. Ошибки прав доступа

```bash
# Проверка sudo прав
sudo -l

# Тест команды
sudo apt update
```

**Решение:**
- Настроить sudoers файл
- Проверить права пользователя
- Убедиться в правильности команд

#### 4. Проблемы с Task Master

```bash
# Проверка Node.js
node --version
npm --version

# Переустановка зависимостей
rm -rf node_modules package-lock.json
npm install
```

### Логи и диагностика

#### 1. Просмотр логов

```bash
# Логи SSH Agent
tail -f logs/ssh_agent.log

# Логи системы
journalctl -u ssh-agent -f

# Логи SSH
tail -f /var/log/auth.log
```

#### 2. Отладка

```bash
# Запуск с отладкой
python -m src.main execute "test" --dry-run --log-level DEBUG

# Проверка конфигурации
python -c "
from src.config.server_config import ServerConfig
from src.config.agent_config import AgentConfig

try:
    server_config = ServerConfig.from_yaml('config/server_config.yaml')
    agent_config = AgentConfig.from_yaml('config/agent_config.yaml')
    print('✅ Конфигурация корректна')
except Exception as e:
    print(f'❌ Ошибка конфигурации: {e}')
"
```

#### 3. Мониторинг производительности

```bash
# Мониторинг ресурсов
htop

# Мониторинг сети
netstat -tulpn

# Мониторинг диска
df -h
```

### Восстановление после сбоев

#### 1. Восстановление конфигурации

```bash
# Восстановление из резервной копии
cp config/server_config.yaml.backup config/server_config.yaml
cp config/agent_config.yaml.backup config/agent_config.yaml

# Пересоздание конфигурации
python -m src.main init
```

#### 2. Очистка данных

```bash
# Очистка логов
rm -rf logs/*.log

# Очистка кэша
rm -rf .taskmaster/cache/

# Очистка временных файлов
find /tmp -name "ssh_agent_*" -delete
```

#### 3. Переустановка

```bash
# Деактивация виртуального окружения
deactivate

# Удаление виртуального окружения
rm -rf venv

# Переустановка
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install
```

## Рекомендации по безопасности

### 1. Регулярное обновление

```bash
# Обновление зависимостей
pip install --upgrade -r requirements.txt
npm update

# Обновление системы
sudo apt update && sudo apt upgrade
```

### 2. Мониторинг безопасности

```bash
# Проверка уязвимостей
pip install safety
safety check

# Аудит безопасности
npm audit
npm audit fix
```

### 3. Резервное копирование

```bash
# Создание резервных копий
tar -czf backup_$(date +%Y%m%d).tar.gz config/ .taskmaster/

# Автоматическое резервное копирование
crontab -e
# Добавить: 0 2 * * * /path/to/backup_script.sh
```

### 4. Мониторинг логов

```bash
# Настройка logrotate
sudo nano /etc/logrotate.d/ssh-agent

# Содержимое:
# /path/to/logs/*.log {
#     daily
#     rotate 30
#     compress
#     delaycompress
#     missingok
#     notifempty
# }
```

Это руководство поможет вам правильно настроить и запустить SSH Agent в различных средах. При возникновении проблем обращайтесь к разделу устранения неполадок или создавайте issue в репозитории.
