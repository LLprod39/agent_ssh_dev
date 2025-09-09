"""
Пример использования системы идемпотентности

Этот пример демонстрирует:
- Создание снимков состояния системы
- Генерацию идемпотентных команд
- Проверки идемпотентности
- Систему отката изменений
"""

import sys
import os
import time
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.agent_config import AgentConfig
from src.connectors.ssh_connector import SSHConnector, ServerConfig
from src.utils.idempotency_system import IdempotencySystem, IdempotencyCheck, IdempotencyCheckType
from src.agents.subtask_agent import SubtaskAgent, Subtask
from src.models.execution_model import ExecutionModel
from src.utils.logger import StructuredLogger


def create_mock_ssh_connector():
    """Создание мок SSH коннектора для демонстрации"""
    class MockSSHConnector:
        def __init__(self):
            self.connected = True
            self.commands_executed = []
        
        def execute_command(self, command: str, timeout: int = 30, context: dict = None):
            """Мок выполнения команды"""
            self.commands_executed.append(command)
            
            # Имитируем различные результаты в зависимости от команды
            if "dpkg -l" in command and "nginx" in command:
                # Пакет уже установлен
                return type('Result', (), {
                    'success': True,
                    'exit_code': 0,
                    'stdout': 'ii  nginx  1.18.0-0ubuntu1.4  amd64  high performance web server',
                    'stderr': '',
                    'duration': 0.1
                })()
            elif "test -f" in command and "/etc/nginx/nginx.conf" in command:
                # Файл существует
                return type('Result', (), {
                    'success': True,
                    'exit_code': 0,
                    'stdout': '',
                    'stderr': '',
                    'duration': 0.05
                })()
            elif "systemctl is-active" in command and "nginx" in command:
                # Сервис запущен
                return type('Result', (), {
                    'success': True,
                    'exit_code': 0,
                    'stdout': '',
                    'stderr': '',
                    'duration': 0.1
                })()
            elif "apt-get install" in command:
                # Установка пакета
                return type('Result', (), {
                    'success': True,
                    'exit_code': 0,
                    'stdout': 'Setting up nginx (1.18.0-0ubuntu1.4) ...',
                    'stderr': '',
                    'duration': 2.5
                })()
            elif "systemctl start" in command:
                # Запуск сервиса
                return type('Result', (), {
                    'success': True,
                    'exit_code': 0,
                    'stdout': '',
                    'stderr': '',
                    'duration': 0.3
                })()
            else:
                # Обычная команда
                return type('Result', (), {
                    'success': True,
                    'exit_code': 0,
                    'stdout': f'Mock output for: {command}',
                    'stderr': '',
                    'duration': 0.1
                })()
        
        def is_command_safe(self, command: str) -> bool:
            """Проверка безопасности команды"""
            dangerous_commands = ['rm -rf /', 'dd if=/dev/zero', 'mkfs']
            return not any(dangerous in command for dangerous in dangerous_commands)
    
    return MockSSHConnector()


def demonstrate_idempotency_system():
    """Демонстрация системы идемпотентности"""
    print("🚀 Демонстрация системы идемпотентности")
    print("=" * 50)
    
    # Создаем мок SSH коннектор
    ssh_connector = create_mock_ssh_connector()
    
    # Создаем конфигурацию
    config = AgentConfig(
        llm={
            "api_key": "mock-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4"
        }
    )
    
    # Инициализируем систему идемпотентности
    idempotency_system = IdempotencySystem(ssh_connector, config.idempotency.dict())
    
    print("\n1. Создание снимка состояния системы")
    print("-" * 30)
    
    # Создаем снимок состояния
    snapshot = idempotency_system.create_state_snapshot("demo_task_001")
    print(f"✅ Создан снимок: {snapshot.snapshot_id}")
    print(f"   Время: {snapshot.timestamp}")
    print(f"   Информация о системе: {len(snapshot.system_info)} параметров")
    
    print("\n2. Генерация идемпотентных команд")
    print("-" * 30)
    
    # Демонстрируем генерацию идемпотентных команд
    commands_to_test = [
        ("apt-get install nginx", "install_package", "nginx"),
        ("touch /etc/nginx/nginx.conf", "create_file", "/etc/nginx/nginx.conf"),
        ("mkdir -p /var/www/html", "create_directory", "/var/www/html"),
        ("systemctl start nginx", "start_service", "nginx"),
        ("systemctl enable nginx", "enable_service", "nginx"),
    ]
    
    for base_command, command_type, target in commands_to_test:
        print(f"\nКоманда: {base_command}")
        idempotent_cmd, checks = idempotency_system.generate_idempotent_command(
            base_command, command_type, target
        )
        print(f"Идемпотентная: {idempotent_cmd}")
        print(f"Проверки: {len(checks)} шт.")
        for check in checks:
            print(f"  - {check.description}")
    
    print("\n3. Проверка идемпотентности")
    print("-" * 30)
    
    # Создаем проверки
    checks = [
        IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        ),
        IdempotencyCheck(
            check_type=IdempotencyCheckType.FILE_EXISTS,
            target="/etc/nginx/nginx.conf",
            expected_state=True,
            check_command="test -f /etc/nginx/nginx.conf",
            success_pattern=".*",
            description="Проверка существования конфига nginx"
        ),
        IdempotencyCheck(
            check_type=IdempotencyCheckType.SERVICE_RUNNING,
            target="nginx",
            expected_state=True,
            check_command="systemctl is-active --quiet nginx",
            success_pattern=".*",
            description="Проверка запуска nginx"
        )
    ]
    
    # Выполняем проверки
    results = idempotency_system.check_idempotency(checks)
    
    print("Результаты проверок:")
    for result in results:
        status = "✅ УСПЕХ" if result.success else "❌ НЕУДАЧА"
        print(f"  {status} {result.check.description}")
        if result.current_state:
            print(f"    Текущее состояние: {result.current_state}")
        if result.error_message:
            print(f"    Ошибка: {result.error_message}")
    
    print("\n4. Проверка необходимости пропуска команд")
    print("-" * 30)
    
    # Проверяем, нужно ли пропускать команды
    test_commands = [
        "apt-get install nginx",
        "systemctl start nginx",
        "touch /tmp/test_file"
    ]
    
    for command in test_commands:
        should_skip = idempotency_system.should_skip_command(command, checks)
        status = "ПРОПУСТИТЬ" if should_skip else "ВЫПОЛНИТЬ"
        print(f"  {command} -> {status}")
    
    print("\n5. Система отката")
    print("-" * 30)
    
    # Обновляем снимок с изменениями
    snapshot.packages_installed = ["nginx"]
    snapshot.services_started = ["nginx"]
    snapshot.files_created = ["/etc/nginx/nginx.conf"]
    
    # Создаем команды отката
    rollback_commands = idempotency_system.create_rollback_commands(snapshot)
    print(f"Создано команд отката: {len(rollback_commands)}")
    for cmd in rollback_commands:
        print(f"  - {cmd}")
    
    print("\n6. Статус системы идемпотентности")
    print("-" * 30)
    
    status = idempotency_system.get_system_status()
    print(f"Снимков: {status['snapshots_count']}")
    print(f"Текущий снимок: {status['current_snapshot']}")
    print(f"Размер кэша: {status['cache_size']}")
    print(f"TTL кэша: {status['cache_ttl']} сек")
    
    print("\n✅ Демонстрация завершена!")


def demonstrate_subtask_agent_integration():
    """Демонстрация интеграции с SubtaskAgent"""
    print("\n🔧 Демонстрация интеграции с SubtaskAgent")
    print("=" * 50)
    
    # Создаем мок SSH коннектор
    ssh_connector = create_mock_ssh_connector()
    
    # Создаем конфигурацию
    config = AgentConfig(
        llm={
            "api_key": "mock-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4"
        }
    )
    
    # Инициализируем SubtaskAgent с системой идемпотентности
    subtask_agent = SubtaskAgent(config, ssh_connector=ssh_connector)
    
    # Создаем тестовую подзадачу
    subtask = Subtask(
        subtask_id="test_subtask_001",
        title="Установка и настройка nginx",
        description="Установка веб-сервера nginx и его базовая настройка",
        commands=[
            "apt-get update",
            "apt-get install nginx",
            "systemctl start nginx",
            "systemctl enable nginx",
            "touch /etc/nginx/nginx.conf"
        ],
        health_checks=[
            "systemctl is-active nginx",
            "nginx -t"
        ],
        expected_output="Nginx установлен и запущен",
        rollback_commands=[
            "systemctl stop nginx",
            "apt-get remove nginx"
        ]
    )
    
    print("Исходная подзадача:")
    print(f"  Команд: {len(subtask.commands)}")
    for i, cmd in enumerate(subtask.commands, 1):
        print(f"    {i}. {cmd}")
    
    # Улучшаем подзадачу идемпотентностью
    enhanced_subtask = subtask_agent.enhance_subtask_with_idempotency(subtask)
    
    print("\nУлучшенная подзадача:")
    print(f"  Команд: {len(enhanced_subtask.commands)}")
    for i, cmd in enumerate(enhanced_subtask.commands, 1):
        print(f"    {i}. {cmd}")
    
    print(f"\nМетаданные:")
    print(f"  Идемпотентность: {enhanced_subtask.metadata.get('idempotent_enhanced', False)}")
    print(f"  Проверок: {len(enhanced_subtask.metadata.get('idempotency_checks', []))}")
    
    print("\n✅ Интеграция с SubtaskAgent продемонстрирована!")


def demonstrate_execution_model_integration():
    """Демонстрация интеграции с ExecutionModel"""
    print("\n⚙️ Демонстрация интеграции с ExecutionModel")
    print("=" * 50)
    
    # Создаем мок SSH коннектор
    ssh_connector = create_mock_ssh_connector()
    
    # Создаем конфигурацию
    config = AgentConfig(
        llm={
            "api_key": "mock-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4"
        }
    )
    
    # Инициализируем ExecutionModel
    execution_model = ExecutionModel(config, ssh_connector)
    
    print("Статус системы идемпотентности:")
    status = execution_model.get_idempotency_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\nСоздание снимка состояния:")
    snapshot = execution_model.create_idempotency_snapshot("demo_execution_001")
    print(f"  Снимок создан: {snapshot.snapshot_id}")
    
    print("\nГенерация идемпотентной команды:")
    cmd, checks = execution_model.generate_idempotent_command(
        "apt-get install nginx", "install_package", "nginx"
    )
    print(f"  Исходная: apt-get install nginx")
    print(f"  Идемпотентная: {cmd}")
    print(f"  Проверок: {len(checks)}")
    
    print("\n✅ Интеграция с ExecutionModel продемонстрирована!")


if __name__ == "__main__":
    print("🎯 Примеры использования системы идемпотентности")
    print("=" * 60)
    
    try:
        # Основная демонстрация системы идемпотентности
        demonstrate_idempotency_system()
        
        # Демонстрация интеграции с SubtaskAgent
        demonstrate_subtask_agent_integration()
        
        # Демонстрация интеграции с ExecutionModel
        demonstrate_execution_model_integration()
        
        print("\n🎉 Все демонстрации завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка во время демонстрации: {e}")
        import traceback
        traceback.print_exc()
