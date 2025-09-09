# SSH Connector - Руководство по использованию

## Обзор

SSH Connector - это мощный и безопасный инструмент для подключения к удаленным серверам через SSH. Он поддерживает различные методы аутентификации, безопасное хранение учетных данных и автоматическое восстановление соединений.

## Основные возможности

- ✅ Безопасное SSH подключение с поддержкой ключей и паролей
- ✅ Автоматическое восстановление соединений с retry логикой
- ✅ Безопасное хранение учетных данных (keyring + шифрование)
- ✅ Выполнение команд с детальным логированием
- ✅ Загрузка и скачивание файлов через SFTP
- ✅ Контекстный менеджер для автоматического управления соединениями
- ✅ Получение информации о сервере
- ✅ Статистика подключений и выполнения команд

## Установка

```bash
# Установка зависимостей
pip install -r requirements.txt
```

## Быстрый старт

### Базовое использование

```python
import asyncio
from src.connectors.ssh_connector import SSHConnector
from src.config.server_config import ServerConfig

async def main():
    # Создаем конфигурацию сервера
    config = ServerConfig(
        host="your-server.com",
        port=22,
        username="your_username",
        auth_method="password",  # или "key"
        password="your_password",
        timeout=30,
        os_type="ubuntu"
    )
    
    # Создаем SSH Connector
    connector = SSHConnector(config)
    
    try:
        # Подключаемся
        await connector.connect()
        
        # Выполняем команду
        result = await connector.execute_command("whoami")
        print(f"Пользователь: {result.stdout.strip()}")
        
    finally:
        # Отключаемся
        await connector.disconnect()

# Запуск
asyncio.run(main())
```

### Использование контекстного менеджера

```python
async def main():
    config = ServerConfig(
        host="your-server.com",
        username="your_username",
        auth_method="password",
        password="your_password"
    )
    
    connector = SSHConnector(config)
    
    # Автоматическое управление соединением
    async with connector.connection_context() as conn:
        result = await conn.execute_command("date")
        print(f"Время на сервере: {result.stdout.strip()}")
    # Соединение автоматически закрывается
```

## Методы аутентификации

### 1. Аутентификация по паролю

```python
config = ServerConfig(
    host="server.com",
    username="user",
    auth_method="password",
    password="secret_password"
)
```

### 2. Аутентификация по SSH ключу

```python
config = ServerConfig(
    host="server.com",
    username="user",
    auth_method="key",
    key_path="/path/to/private/key"
)
```

### 3. Автоматический поиск SSH ключей

Если путь к ключу не указан, SSH Connector автоматически ищет доступные ключи в `~/.ssh/`:

```python
config = ServerConfig(
    host="server.com",
    username="user",
    auth_method="key"
    # key_path не указан - будет автоматический поиск
)
```

## Безопасное хранение учетных данных

### Использование системного keyring

```python
# Создаем connector с менеджером учетных данных
connector = SSHConnector(config, use_credentials_manager=True)

# Сохраняем пароль в keyring
connector.store_credentials(password="secret_password")

# При следующем подключении пароль будет загружен автоматически
await connector.connect()
```

### Использование файлового менеджера с шифрованием

```python
from src.utils.credentials_manager import CredentialsManager

# Создаем менеджер учетных данных
manager = CredentialsManager()

# Сохраняем учетные данные
manager.store_credentials(
    host="server.com",
    username="user",
    password="secret_password"
)

# Загружаем учетные данные
credentials = manager.load_credentials("server.com", "user")
```

## Выполнение команд

### Одиночная команда

```python
result = await connector.execute_command("ls -la")

if result.success:
    print(f"Успешно: {result.stdout}")
else:
    print(f"Ошибка: {result.stderr}")
```

### Несколько команд подряд

```python
commands = ["pwd", "whoami", "date"]
results = await connector.execute_commands_batch(commands)

for i, result in enumerate(results):
    print(f"Команда {i+1}: {'✓' if result.success else '✗'}")
```

### Команды с таймаутом

```python
# Команда с таймаутом 60 секунд
result = await connector.execute_command("long_running_command", timeout=60)
```

## Работа с файлами

### Загрузка файла на сервер

```python
success = await connector.upload_file(
    local_path="/local/file.txt",
    remote_path="/remote/file.txt"
)

if success:
    print("Файл загружен успешно")
```

### Скачивание файла с сервера

```python
success = await connector.download_file(
    remote_path="/remote/file.txt",
    local_path="/local/file.txt"
)

if success:
    print("Файл скачан успешно")
```

## Получение информации о сервере

```python
server_info = await connector.get_server_info()

print("Информация о сервере:")
for key, value in server_info.items():
    print(f"{key}: {value}")
```

## Проверка соединения

```python
# Проверяем, активно ли соединение
is_connected = await connector.check_connection()

if is_connected:
    print("Соединение активно")
else:
    print("Соединение неактивно")
```

## Статистика

```python
stats = connector.get_stats()

print("Статистика подключения:")
for key, value in stats.items():
    print(f"{key}: {value}")
```

## Обработка ошибок

```python
from src.connectors.ssh_connector import SSHConnectionError, SSHCommandError

try:
    await connector.connect()
    result = await connector.execute_command("some_command")
    
except SSHConnectionError as e:
    print(f"Ошибка подключения: {e}")
    
except SSHCommandError as e:
    print(f"Ошибка выполнения команды: {e}")
    
except Exception as e:
    print(f"Неожиданная ошибка: {e}")
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
  installed_services:
    - "docker"
    - "nginx"
    - "postgresql"
  installed_packages:
    - "curl"
    - "wget"
    - "git"
  disk_space_threshold: 1024  # MB
  memory_threshold: 512  # MB
```

### Загрузка конфигурации из файла

```python
config = ServerConfig.from_yaml("config/server_config.yaml")
connector = SSHConnector(config)
```

## Безопасность

### Запрещенные команды

SSH Connector автоматически блокирует выполнение опасных команд:

```python
# Эта команда будет заблокирована
try:
    result = await connector.execute_command("rm -rf /")
except SSHCommandError as e:
    print(f"Команда заблокирована: {e}")
```

### Проверка команд

```python
# Проверяем, запрещена ли команда
if config.is_command_forbidden("rm -rf /"):
    print("Команда запрещена!")
```

## Логирование

SSH Connector использует структурированное логирование:

```python
import logging

# Настройка уровня логирования
logging.getLogger("SSHConnector").setLevel(logging.DEBUG)

# Логи будут содержать:
# - Время подключения
# - Выполняемые команды
# - Результаты выполнения
# - Ошибки и предупреждения
```

## Примеры использования

### Мониторинг сервера

```python
async def monitor_server():
    config = ServerConfig(
        host="monitoring-server.com",
        username="monitor",
        auth_method="key"
    )
    
    connector = SSHConnector(config)
    
    async with connector.connection_context() as conn:
        # Проверяем использование диска
        result = await conn.execute_command("df -h")
        print("Использование диска:")
        print(result.stdout)
        
        # Проверяем использование памяти
        result = await conn.execute_command("free -h")
        print("Использование памяти:")
        print(result.stdout)
        
        # Проверяем загрузку системы
        result = await conn.execute_command("uptime")
        print(f"Загрузка системы: {result.stdout.strip()}")
```

### Автоматическое развертывание

```python
async def deploy_application():
    config = ServerConfig(
        host="production-server.com",
        username="deploy",
        auth_method="key"
    )
    
    connector = SSHConnector(config)
    
    async with connector.connection_context() as conn:
        # Загружаем файлы приложения
        await conn.upload_file("app.tar.gz", "/tmp/app.tar.gz")
        
        # Распаковываем
        await conn.execute_command("cd /opt && tar -xzf /tmp/app.tar.gz")
        
        # Устанавливаем зависимости
        await conn.execute_command("cd /opt/app && pip install -r requirements.txt")
        
        # Перезапускаем сервис
        await conn.execute_command("systemctl restart myapp")
        
        # Проверяем статус
        result = await conn.execute_command("systemctl status myapp")
        print(f"Статус сервиса: {result.stdout}")
```

## Устранение неполадок

### Проблемы с подключением

1. **Ошибка аутентификации**
   - Проверьте правильность имени пользователя и пароля
   - Убедитесь, что SSH ключ существует и имеет правильные права доступа

2. **Таймаут подключения**
   - Увеличьте значение `timeout` в конфигурации
   - Проверьте сетевое соединение

3. **Ошибка "Host key verification failed"**
   - SSH Connector автоматически добавляет новые хосты
   - Для продакшена рекомендуется предварительно добавить ключи хостов

### Проблемы с выполнением команд

1. **Команда не найдена**
   - Проверьте, что команда доступна на сервере
   - Убедитесь, что путь к команде указан правильно

2. **Недостаточно прав**
   - Проверьте права пользователя на выполнение команды
   - Используйте `sudo` если необходимо

### Проблемы с файлами

1. **Ошибка загрузки файла**
   - Проверьте права доступа к локальному файлу
   - Убедитесь, что на сервере достаточно места

2. **Ошибка скачивания файла**
   - Проверьте, что файл существует на сервере
   - Убедитесь, что у пользователя есть права на чтение файла

## Дополнительные ресурсы

- [Документация paramiko](https://docs.paramiko.org/)
- [SSH ключи - руководство](https://www.ssh.com/academy/ssh/key)
- [Безопасность SSH](https://www.ssh.com/academy/ssh/security)
