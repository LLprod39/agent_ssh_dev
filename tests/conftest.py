"""
Конфигурация pytest для проекта SSH Agent

Содержит общие фикстуры и настройки для всех тестов.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock
from typing import Dict, Any, List

# Добавляем путь к модулям проекта
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.config.agent_config import AgentConfig, TaskAgentConfig, SubtaskAgentConfig, ExecutorConfig, ErrorHandlerConfig, LLMConfig
from src.config.server_config import ServerConfig
from src.models.planning_model import Task, TaskStep, StepStatus, Priority, TaskStatus
from src.models.execution_model import ExecutionContext, CommandResult, ExecutionStatus
from src.agents.subtask_agent import Subtask
from src.connectors.ssh_connector import SSHConnector


@pytest.fixture(scope="session")
def event_loop():
    """Создает event loop для всех тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm_config():
    """Фикстура конфигурации LLM для тестов."""
    return LLMConfig(
        api_key="test-api-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4",
        max_tokens=2000,
        temperature=0.3,
        timeout=60
    )


@pytest.fixture
def mock_task_agent_config():
    """Фикстура конфигурации Task Agent."""
    return TaskAgentConfig(
        model="gpt-4",
        temperature=0.3,
        max_steps=10,
        max_tokens=2000
    )


@pytest.fixture
def mock_subtask_agent_config():
    """Фикстура конфигурации Subtask Agent."""
    return SubtaskAgentConfig(
        model="gpt-4",
        temperature=0.1,
        max_subtasks=20,
        max_tokens=1500
    )


@pytest.fixture
def mock_executor_config():
    """Фикстура конфигурации Executor."""
    return ExecutorConfig(
        max_retries_per_command=2,
        auto_correction_enabled=True,
        dry_run_mode=False,
        command_timeout=30
    )


@pytest.fixture
def mock_error_handler_config():
    """Фикстура конфигурации Error Handler."""
    return ErrorHandlerConfig(
        error_threshold_per_step=4,
        send_to_planner_after_threshold=True,
        human_escalation_threshold=3
    )


@pytest.fixture
def mock_agent_config(
    mock_llm_config,
    mock_task_agent_config,
    mock_subtask_agent_config,
    mock_executor_config,
    mock_error_handler_config
):
    """Фикстура полной конфигурации агента."""
    return AgentConfig(
        task_agent=mock_task_agent_config,
        subtask_agent=mock_subtask_agent_config,
        executor=mock_executor_config,
        error_handler=mock_error_handler_config,
        llm=mock_llm_config
    )


@pytest.fixture
def mock_server_config():
    """Фикстура конфигурации сервера."""
    return ServerConfig(
        host="test.example.com",
        port=22,
        username="testuser",
        auth_method="key",
        key_path="/path/to/test/key",
        timeout=30,
        os_type="ubuntu",
        forbidden_commands=[
            "rm -rf /",
            "dd if=/dev/zero",
            "mkfs"
        ],
        installed_services=[
            "docker",
            "nginx",
            "postgresql"
        ]
    )


@pytest.fixture
def mock_ssh_connector():
    """Фикстура мока SSH Connector."""
    connector = Mock(spec=SSHConnector)
    connector.connected = True
    connector.client = Mock()
    connector.sftp = Mock()
    connector.stats = {
        'connection_attempts': 0,
        'successful_connections': 1,
        'failed_connections': 0,
        'commands_executed': 0,
        'commands_failed': 0
    }
    
    # Мокаем методы
    connector.connect = AsyncMock(return_value=True)
    connector.disconnect = AsyncMock()
    connector.execute_command = AsyncMock(return_value=CommandResult(
        command="test",
        success=True,
        exit_code=0,
        stdout="test output",
        stderr=""
    ))
    connector.check_connection = AsyncMock(return_value=True)
    connector.get_stats = Mock(return_value=connector.stats)
    
    return connector


@pytest.fixture
def mock_llm_interface():
    """Фикстура мока LLM интерфейса."""
    interface = Mock()
    interface.is_available = Mock(return_value=True)
    interface.generate_response = Mock(return_value=Mock(
        success=True,
        content='{"steps": [{"title": "Test Step", "description": "Test Description", "priority": "high", "estimated_duration": 10, "dependencies": []}]}',
        usage={"total_tokens": 100},
        model="gpt-4",
        duration=1.0
    ))
    return interface


@pytest.fixture
def mock_task_master():
    """Фикстура мока Task Master."""
    task_master = Mock()
    task_master.improve_prompt = Mock(return_value=Mock(
        success=True,
        data={"improved_prompt": "improved prompt"}
    ))
    task_master.generate_tasks_from_prd = Mock(return_value=Mock(
        success=True,
        data={"tasks": ["Task 1", "Task 2"]}
    ))
    return task_master


@pytest.fixture
def sample_task():
    """Фикстура примера задачи."""
    task = Task(
        title="Установить и настроить nginx",
        description="Установить веб-сервер nginx на Ubuntu сервере"
    )
    
    # Добавляем шаги
    step1 = TaskStep(
        title="Обновить систему",
        description="Выполнить apt update",
        step_id="step_1",
        priority=Priority.HIGH,
        estimated_duration=5,
        dependencies=[]
    )
    
    step2 = TaskStep(
        title="Установить nginx",
        description="Установить nginx через apt",
        step_id="step_2",
        priority=Priority.HIGH,
        estimated_duration=10,
        dependencies=["step_1"]
    )
    
    task.add_step(step1)
    task.add_step(step2)
    
    return task


@pytest.fixture
def sample_subtask():
    """Фикстура примера подзадачи."""
    return Subtask(
        subtask_id="subtask_001",
        title="Установить nginx",
        description="Установить веб-сервер nginx",
        commands=[
            "sudo apt update",
            "sudo apt install -y nginx"
        ],
        health_checks=[
            "systemctl is-active nginx",
            "curl -I http://localhost"
        ],
        expected_output="nginx успешно установлен и запущен",
        rollback_commands=[
            "sudo apt remove -y nginx",
            "sudo apt autoremove -y"
        ],
        timeout=300
    )


@pytest.fixture
def sample_execution_context(sample_subtask, mock_ssh_connector):
    """Фикстура контекста выполнения."""
    return ExecutionContext(
        subtask=sample_subtask,
        ssh_connection=mock_ssh_connector,
        server_info={"os": "ubuntu", "version": "20.04"},
        environment={"production": False}
    )


@pytest.fixture
def temp_config_file():
    """Фикстура временного конфигурационного файла."""
    config_content = """
agents:
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
  api_key: "test-key"
  base_url: "https://api.openai.com/v1"
  max_tokens: 4000
  timeout: 60
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_file = f.name
    
    yield temp_file
    
    # Очистка
    try:
        os.unlink(temp_file)
    except OSError:
        pass


@pytest.fixture
def temp_server_config_file():
    """Фикстура временного конфигурационного файла сервера."""
    config_content = """
server:
  host: "test.example.com"
  port: 22
  username: "testuser"
  auth_method: "key"
  key_path: "/path/to/test/key"
  timeout: 30
  os_type: "ubuntu"
  forbidden_commands:
    - "rm -rf /"
    - "dd if=/dev/zero"
    - "mkfs"
  installed_services:
    - "docker"
    - "nginx"
    - "postgresql"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_file = f.name
    
    yield temp_file
    
    # Очистка
    try:
        os.unlink(temp_file)
    except OSError:
        pass


@pytest.fixture
def mock_command_results():
    """Фикстура примеров результатов команд."""
    return {
        "success": CommandResult(
            command="apt update",
            success=True,
            exit_code=0,
            stdout="Обновление завершено",
            stderr="",
            duration=2.5
        ),
        "failure": CommandResult(
            command="apt install nonexistent",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Package not found",
            duration=1.0
        ),
        "permission_denied": CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Permission denied",
            duration=0.5
        )
    }


@pytest.fixture
def mock_error_scenarios():
    """Фикстура сценариев ошибок для тестирования."""
    return {
        "network_error": {
            "command": "curl https://example.com",
            "error": "Connection refused",
            "exit_code": 7
        },
        "service_not_found": {
            "command": "systemctl start nonexistent",
            "error": "Unit nonexistent.service not found",
            "exit_code": 1
        },
        "file_not_found": {
            "command": "cat /nonexistent/file",
            "error": "No such file or directory",
            "exit_code": 1
        },
        "syntax_error": {
            "command": "ls  -la   /tmp",
            "error": "syntax error",
            "exit_code": 2
        }
    }


# Маркеры для категоризации тестов
def pytest_configure(config):
    """Настройка маркеров pytest."""
    config.addinivalue_line(
        "markers", "unit: Unit тесты"
    )
    config.addinivalue_line(
        "markers", "integration: Интеграционные тесты"
    )
    config.addinivalue_line(
        "markers", "slow: Медленные тесты"
    )
    config.addinivalue_line(
        "markers", "ssh: Тесты, требующие SSH соединения"
    )
    config.addinivalue_line(
        "markers", "llm: Тесты, требующие LLM API"
    )
    config.addinivalue_line(
        "markers", "mock: Тесты с моками"
    )
    config.addinivalue_line(
        "markers", "error_scenarios: Тесты сценариев ошибок"
    )
    config.addinivalue_line(
        "markers", "security: Тесты безопасности"
    )
    config.addinivalue_line(
        "markers", "performance: Тесты производительности"
    )


# Настройка логирования для тестов
def pytest_configure_node(node):
    """Настройка узла теста."""
    if hasattr(node, 'get_closest_marker'):
        marker = node.get_closest_marker('slow')
        if marker:
            node.add_marker(pytest.mark.timeout(300))  # 5 минут для медленных тестов


# Обработка предупреждений
def pytest_collection_modifyitems(config, items):
    """Модификация элементов коллекции тестов."""
    for item in items:
        # Добавляем маркер unit для тестов без маркеров
        if not any(marker.name in ['unit', 'integration', 'slow', 'ssh', 'llm'] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
        
        # Добавляем таймаут для медленных тестов
        if item.get_closest_marker('slow'):
            item.add_marker(pytest.mark.timeout(300))
