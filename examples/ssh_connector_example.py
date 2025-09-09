"""
Пример использования SSH Connector
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к src для импорта
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.connectors.ssh_connector import SSHConnector
from src.config.server_config import ServerConfig
from src.utils.credentials_manager import CredentialsManager, KeyringCredentialsManager


async def basic_ssh_example():
    """Базовый пример использования SSH Connector"""
    print("=== Базовый пример SSH Connector ===")
    
    # Создаем конфигурацию сервера
    config = ServerConfig(
        host="localhost",  # Замените на ваш хост
        port=22,
        username="your_username",  # Замените на ваше имя пользователя
        auth_method="password",  # или "key"
        password="your_password",  # Замените на ваш пароль
        timeout=30,
        os_type="ubuntu"
    )
    
    # Создаем SSH Connector
    connector = SSHConnector(config, use_credentials_manager=False)
    
    try:
        # Подключаемся к серверу
        print("Подключение к серверу...")
        await connector.connect()
        print("✓ Подключение установлено")
        
        # Выполняем простую команду
        print("\nВыполнение команды 'whoami'...")
        result = await connector.execute_command("whoami")
        
        if result.success:
            print(f"✓ Команда выполнена успешно")
            print(f"Вывод: {result.stdout.strip()}")
        else:
            print(f"✗ Команда завершилась с ошибкой (код: {result.exit_code})")
            print(f"Ошибка: {result.stderr}")
        
        # Выполняем команду для получения информации о системе
        print("\nПолучение информации о системе...")
        result = await connector.execute_command("uname -a")
        
        if result.success:
            print(f"✓ Информация о системе получена")
            print(f"Система: {result.stdout.strip()}")
        
        # Выполняем несколько команд подряд
        print("\nВыполнение нескольких команд...")
        commands = ["pwd", "ls -la", "df -h"]
        
        for cmd in commands:
            print(f"\nВыполнение: {cmd}")
            result = await connector.execute_command(cmd)
            
            if result.success:
                print(f"✓ Успешно")
                print(f"Вывод (первые 3 строки):")
                lines = result.stdout.strip().split('\n')[:3]
                for line in lines:
                    print(f"  {line}")
            else:
                print(f"✗ Ошибка: {result.stderr}")
        
        # Получаем статистику
        print("\n=== Статистика подключения ===")
        stats = connector.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    finally:
        # Отключаемся
        await connector.disconnect()
        print("\n✓ Соединение закрыто")


async def ssh_with_credentials_manager():
    """Пример использования SSH Connector с менеджером учетных данных"""
    print("\n=== SSH Connector с менеджером учетных данных ===")
    
    # Создаем конфигурацию сервера
    config = ServerConfig(
        host="localhost",
        port=22,
        username="your_username",
        auth_method="password",
        timeout=30,
        os_type="ubuntu"
    )
    
    # Создаем SSH Connector с менеджером учетных данных
    connector = SSHConnector(config, use_credentials_manager=True)
    
    try:
        # Сохраняем учетные данные (только для демонстрации)
        print("Сохранение учетных данных...")
        success = connector.store_credentials(password="your_password")
        if success:
            print("✓ Учетные данные сохранены")
        else:
            print("✗ Не удалось сохранить учетные данные")
        
        # Подключаемся (пароль будет загружен из менеджера)
        print("Подключение к серверу...")
        await connector.connect()
        print("✓ Подключение установлено")
        
        # Выполняем команду
        result = await connector.execute_command("echo 'Hello from SSH Agent!'")
        
        if result.success:
            print(f"✓ Команда выполнена: {result.stdout.strip()}")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    finally:
        await connector.disconnect()
        print("✓ Соединение закрыто")


async def ssh_file_operations():
    """Пример работы с файлами через SSH"""
    print("\n=== Работа с файлами через SSH ===")
    
    config = ServerConfig(
        host="localhost",
        port=22,
        username="your_username",
        auth_method="password",
        password="your_password",
        timeout=30,
        os_type="ubuntu"
    )
    
    connector = SSHConnector(config, use_credentials_manager=False)
    
    try:
        await connector.connect()
        print("✓ Подключение установлено")
        
        # Создаем тестовый файл локально
        test_file = Path("test_file.txt")
        test_file.write_text("Hello from SSH Agent!\nThis is a test file.")
        print(f"✓ Создан тестовый файл: {test_file}")
        
        # Загружаем файл на сервер
        print("Загрузка файла на сервер...")
        success = await connector.upload_file(str(test_file), "/tmp/test_file.txt")
        
        if success:
            print("✓ Файл загружен на сервер")
            
            # Проверяем, что файл загружен
            result = await connector.execute_command("ls -la /tmp/test_file.txt")
            if result.success:
                print("✓ Файл найден на сервере")
                print(f"Информация о файле: {result.stdout.strip()}")
            
            # Читаем содержимое файла на сервере
            result = await connector.execute_command("cat /tmp/test_file.txt")
            if result.success:
                print("✓ Содержимое файла на сервере:")
                print(result.stdout)
            
            # Скачиваем файл обратно
            print("Скачивание файла с сервера...")
            downloaded_file = Path("downloaded_file.txt")
            success = await connector.download_file("/tmp/test_file.txt", str(downloaded_file))
            
            if success:
                print("✓ Файл скачан с сервера")
                print(f"Содержимое скачанного файла: {downloaded_file.read_text()}")
                
                # Удаляем скачанный файл
                downloaded_file.unlink()
        
        # Удаляем тестовый файл
        test_file.unlink()
        print("✓ Локальный тестовый файл удален")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    finally:
        await connector.disconnect()
        print("✓ Соединение закрыто")


async def ssh_server_info():
    """Пример получения информации о сервере"""
    print("\n=== Получение информации о сервере ===")
    
    config = ServerConfig(
        host="localhost",
        port=22,
        username="your_username",
        auth_method="password",
        password="your_password",
        timeout=30,
        os_type="ubuntu"
    )
    
    connector = SSHConnector(config, use_credentials_manager=False)
    
    try:
        await connector.connect()
        print("✓ Подключение установлено")
        
        # Получаем информацию о сервере
        print("Получение информации о сервере...")
        server_info = await connector.get_server_info()
        
        print("✓ Информация о сервере получена:")
        for key, value in server_info.items():
            print(f"\n{key.upper()}:")
            if isinstance(value, str):
                # Показываем первые несколько строк для длинных выводов
                lines = value.split('\n')[:5]
                for line in lines:
                    print(f"  {line}")
                if len(value.split('\n')) > 5:
                    print("  ...")
            else:
                print(f"  {value}")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    finally:
        await connector.disconnect()
        print("✓ Соединение закрыто")


async def ssh_context_manager_example():
    """Пример использования контекстного менеджера"""
    print("\n=== Использование контекстного менеджера ===")
    
    config = ServerConfig(
        host="localhost",
        port=22,
        username="your_username",
        auth_method="password",
        password="your_password",
        timeout=30,
        os_type="ubuntu"
    )
    
    connector = SSHConnector(config, use_credentials_manager=False)
    
    try:
        # Используем контекстный менеджер
        async with connector.connection_context() as conn:
            print("✓ Подключение установлено через контекстный менеджер")
            
            # Выполняем команды
            result = await conn.execute_command("date")
            if result.success:
                print(f"✓ Текущее время на сервере: {result.stdout.strip()}")
            
            result = await conn.execute_command("uptime")
            if result.success:
                print(f"✓ Время работы сервера: {result.stdout.strip()}")
        
        print("✓ Соединение автоматически закрыто")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")


async def main():
    """Главная функция с примерами"""
    print("SSH Agent - Примеры использования")
    print("=" * 50)
    
    # Запускаем примеры
    await basic_ssh_example()
    await ssh_with_credentials_manager()
    await ssh_file_operations()
    await ssh_server_info()
    await ssh_context_manager_example()
    
    print("\n" + "=" * 50)
    print("Все примеры завершены!")


if __name__ == "__main__":
    # Запускаем примеры
    asyncio.run(main())
