"""
Пример использования Execution Model

Демонстрирует:
- Создание и настройку Execution Model
- Выполнение подзадач с командами
- Обработку результатов выполнения
- Интеграцию с Task Master
- Автокоррекцию ошибок
"""
import sys
import os
import time
from pathlib import Path

# Добавляем путь к src для импорта модулей
sys.path.append(str(Path(__file__).parent.parent / "src"))

from src.models.execution_model import ExecutionModel, ExecutionContext
from src.agents.subtask_agent import Subtask
from src.config.agent_config import AgentConfig
from src.connectors.ssh_connector import SSHConnector
from src.agents.task_master_integration import TaskMasterIntegration
from src.utils.logger import StructuredLogger


def create_sample_subtask() -> Subtask:
    """Создание примера подзадачи"""
    return Subtask(
        subtask_id="example_subtask_1",
        title="Установка и настройка Nginx",
        description="Установить Nginx, настроить и запустить сервис",
        commands=[
            "sudo apt update",
            "sudo apt install -y nginx",
            "sudo systemctl start nginx",
            "sudo systemctl enable nginx"
        ],
        health_checks=[
            "systemctl is-active nginx",
            "curl -I http://localhost",
            "nginx -t"
        ],
        expected_output="Nginx установлен и запущен",
        rollback_commands=[
            "sudo systemctl stop nginx",
            "sudo systemctl disable nginx",
            "sudo apt remove -y nginx"
        ],
        timeout=60,
        metadata={
            "example": True,
            "created_by": "execution_model_example"
        }
    )


def create_sample_config() -> AgentConfig:
    """Создание примера конфигурации"""
    from src.config.agent_config import (
        AgentConfig, ExecutorConfig, LLMConfig, 
        TaskmasterConfig, TaskAgentConfig, SubtaskAgentConfig,
        ErrorHandlerConfig, LoggingConfig, SecurityConfig
    )
    
    return AgentConfig(
        taskmaster=TaskmasterConfig(
            enabled=True,
            model="gpt-4",
            temperature=0.7
        ),
        task_agent=TaskAgentConfig(
            model="gpt-4",
            temperature=0.3
        ),
        subtask_agent=SubtaskAgentConfig(
            model="gpt-4",
            temperature=0.1
        ),
        executor=ExecutorConfig(
            max_retries_per_command=2,
            auto_correction_enabled=True,
            dry_run_mode=True,  # Включаем dry-run для примера
            command_timeout=30
        ),
        error_handler=ErrorHandlerConfig(
            error_threshold_per_step=4,
            send_to_planner_after_threshold=True
        ),
        llm=LLMConfig(
            api_key="your-api-key-here",
            base_url="https://api.openai.com/v1",
            model="gpt-4"
        ),
        logging=LoggingConfig(
            level="INFO",
            log_file="logs/execution_example.log"
        ),
        security=SecurityConfig(
            validate_commands=True,
            log_forbidden_attempts=True
        )
    )


def create_mock_ssh_connection():
    """Создание мок SSH соединения для примера"""
    class MockSSHConnection:
        def __init__(self):
            self.connected = True
        
        def execute_command(self, command: str, timeout: int = 30):
            """Мок выполнение команды"""
            print(f"[MOCK SSH] Выполнение команды: {command}")
            
            # Имитируем различные результаты в зависимости от команды
            if "apt update" in command:
                return "Обновление списков пакетов...\nГотово.", "", 0
            elif "apt install" in command:
                return "Установка пакета...\nГотово.", "", 0
            elif "systemctl start" in command:
                return "", "", 0
            elif "systemctl enable" in command:
                return "", "", 0
            elif "systemctl is-active" in command:
                return "active", "", 0
            elif "curl -I" in command:
                return "HTTP/1.1 200 OK\nServer: nginx/1.18.0", "", 0
            elif "nginx -t" in command:
                return "nginx: configuration file /etc/nginx/nginx.conf test is successful", "", 0
            else:
                return f"Команда '{command}' выполнена", "", 0
        
        def close(self):
            self.connected = False
    
    return MockSSHConnection()


def main():
    """Основная функция примера"""
    print("=== Пример использования Execution Model ===\n")
    
    # Создаем конфигурацию
    config = create_sample_config()
    print("✓ Конфигурация создана")
    
    # Создаем SSH коннектор (мок)
    ssh_connector = SSHConnector()
    print("✓ SSH коннектор создан")
    
    # Создаем Task Master интеграцию (мок)
    task_master = None  # В реальном примере здесь был бы TaskMasterIntegration
    print("✓ Task Master интеграция настроена")
    
    # Создаем Execution Model
    execution_model = ExecutionModel(config, ssh_connector, task_master)
    print("✓ Execution Model создан")
    
    # Создаем пример подзадачи
    subtask = create_sample_subtask()
    print(f"✓ Подзадача создана: {subtask.title}")
    
    # Создаем мок SSH соединение
    mock_ssh = create_mock_ssh_connection()
    print("✓ Мок SSH соединение создано")
    
    # Создаем контекст выполнения
    context = ExecutionContext(
        subtask=subtask,
        ssh_connection=mock_ssh,
        server_info={
            "os": "ubuntu",
            "version": "20.04",
            "arch": "x86_64"
        },
        environment={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/root"
        }
    )
    print("✓ Контекст выполнения создан")
    
    print("\n--- Выполнение подзадачи ---")
    
    # Выполняем подзадачу
    start_time = time.time()
    result = execution_model.execute_subtask(context)
    execution_time = time.time() - start_time
    
    print(f"\n✓ Выполнение завершено за {execution_time:.2f} секунд")
    
    # Выводим результаты
    print("\n--- Результаты выполнения ---")
    print(f"Подзадача ID: {result.subtask_id}")
    print(f"Успех: {result.success}")
    print(f"Длительность: {result.total_duration:.2f} сек")
    print(f"Количество ошибок: {result.error_count}")
    print(f"Автокоррекция применена: {result.autocorrection_applied}")
    print(f"Откат выполнен: {result.rollback_executed}")
    
    print(f"\nКоманды выполнены: {len(result.commands_results)}")
    for i, cmd_result in enumerate(result.commands_results, 1):
        print(f"  {i}. {cmd_result.command}")
        print(f"     Успех: {cmd_result.success}, Код выхода: {cmd_result.exit_code}")
        if cmd_result.stdout:
            print(f"     Вывод: {cmd_result.stdout[:100]}...")
        if cmd_result.stderr:
            print(f"     Ошибка: {cmd_result.stderr[:100]}...")
    
    print(f"\nHealth-check команды выполнены: {len(result.health_check_results)}")
    for i, health_result in enumerate(result.health_check_results, 1):
        print(f"  {i}. {health_result.command}")
        print(f"     Успех: {health_result.success}, Код выхода: {health_result.exit_code}")
    
    # Выводим статистику
    print("\n--- Статистика выполнения ---")
    stats = execution_model.get_execution_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Закрываем соединение
    mock_ssh.close()
    print("\n✓ SSH соединение закрыто")
    
    print("\n=== Пример завершен ===")


if __name__ == "__main__":
    main()
