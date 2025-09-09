"""
Тесты для интеграции идемпотентности в ExecutionModel
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.models.execution_model import ExecutionModel
from src.models.command_result import CommandResult, ExecutionStatus
from src.config.agent_config import AgentConfig
from src.utils.idempotency_system import IdempotencyCheck, IdempotencyCheckType


class MockSSHConnector:
    """Мок SSH коннектора для тестов"""
    
    def __init__(self):
        self.commands_executed = []
        self.mock_results = {}
    
    def execute_command(self, command: str, timeout: int = 30, context: dict = None):
        """Мок выполнения команды"""
        self.commands_executed.append(command)
        
        # Возвращаем предустановленный результат или дефолтный
        if command in self.mock_results:
            return self.mock_results[command]
        
        # Дефолтный успешный результат
        return CommandResult(
            command=command,
            success=True,
            exit_code=0,
            stdout="mock output",
            stderr="",
            duration=0.1,
            status=ExecutionStatus.COMPLETED
        )
    
    def set_mock_result(self, command: str, result: CommandResult):
        """Установка мок результата для команды"""
        self.mock_results[command] = result
    
    def is_command_safe(self, command: str) -> bool:
        """Проверка безопасности команды"""
        dangerous_commands = ['rm -rf /', 'dd if=/dev/zero', 'mkfs']
        return not any(dangerous in command for dangerous in dangerous_commands)


@pytest.fixture
def mock_ssh_connector():
    """Фикстура для мок SSH коннектора"""
    return MockSSHConnector()


@pytest.fixture
def agent_config():
    """Фикстура для конфигурации агента"""
    return AgentConfig(
        llm={
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4"
        },
        idempotency={
            "enabled": True,
            "cache_ttl": 300,
            "max_snapshots": 10,
            "auto_rollback": True,
            "check_timeout": 30
        }
    )


@pytest.fixture
def execution_model(mock_ssh_connector, agent_config):
    """Фикстура для ExecutionModel"""
    return ExecutionModel(agent_config, mock_ssh_connector)


class TestExecutionModelIdempotency:
    """Тесты для интеграции идемпотентности в ExecutionModel"""
    
    def test_idempotency_system_initialization(self, execution_model):
        """Тест инициализации системы идемпотентности"""
        assert execution_model.idempotency_system is not None
        assert execution_model.idempotency_system.config["enabled"] is True
    
    def test_create_idempotency_snapshot(self, execution_model):
        """Тест создания снимка состояния"""
        snapshot = execution_model.create_idempotency_snapshot("test_task_001")
        
        assert snapshot is not None
        assert snapshot.snapshot_id.startswith("test_task_001_")
        assert snapshot.timestamp is not None
    
    def test_generate_idempotent_command(self, execution_model):
        """Тест генерации идемпотентной команды"""
        cmd, checks = execution_model.generate_idempotent_command(
            "apt-get install nginx", "install_package", "nginx"
        )
        
        assert cmd is not None
        assert len(checks) > 0
        assert "dpkg -l | grep -q" in cmd
        assert "apt-get install" in cmd
    
    def test_check_command_idempotency_true(self, execution_model, mock_ssh_connector):
        """Тест проверки идемпотентности - команда должна быть пропущена"""
        # Настраиваем мок для успешной проверки
        mock_ssh_connector.set_mock_result(
            "dpkg -l | grep -q '^ii  nginx'",
            CommandResult(
                command="dpkg -l | grep -q '^ii  nginx'",
                success=True,
                exit_code=0,
                status=ExecutionStatus.COMPLETED
            )
        )
        
        checks = [
            IdempotencyCheck(
                check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
                target="nginx",
                expected_state=True,
                check_command="dpkg -l | grep -q '^ii  nginx'",
                success_pattern=".*",
                description="Проверка установки nginx"
            )
        ]
        
        should_skip = execution_model.check_command_idempotency("apt-get install nginx", checks)
        
        assert should_skip is True
    
    def test_check_command_idempotency_false(self, execution_model, mock_ssh_connector):
        """Тест проверки идемпотентности - команда должна быть выполнена"""
        # Настраиваем мок для неудачной проверки
        mock_ssh_connector.set_mock_result(
            "dpkg -l | grep -q '^ii  nginx'",
            CommandResult(
                command="dpkg -l | grep -q '^ii  nginx'",
                success=False,
                exit_code=1,
                status=ExecutionStatus.FAILED
            )
        )
        
        checks = [
            IdempotencyCheck(
                check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
                target="nginx",
                expected_state=True,
                check_command="dpkg -l | grep -q '^ii  nginx'",
                success_pattern=".*",
                description="Проверка установки nginx"
            )
        ]
        
        should_skip = execution_model.check_command_idempotency("apt-get install nginx", checks)
        
        assert should_skip is False
    
    def test_execute_idempotency_rollback(self, execution_model, mock_ssh_connector):
        """Тест выполнения отката"""
        # Создаем снимок с изменениями
        snapshot = execution_model.create_idempotency_snapshot("test_rollback_task")
        snapshot.packages_installed = ["nginx"]
        snapshot.services_started = ["nginx"]
        
        # Выполняем откат
        results = execution_model.execute_idempotency_rollback(snapshot.snapshot_id)
        
        assert len(results) > 0
        assert any("apt-get remove -y nginx" in result.command for result in results)
        assert any("systemctl stop nginx" in result.command for result in results)
    
    def test_get_idempotency_status(self, execution_model):
        """Тест получения статуса системы идемпотентности"""
        status = execution_model.get_idempotency_status()
        
        assert "snapshots_count" in status
        assert "current_snapshot" in status
        assert "cache_size" in status
        assert "cache_ttl" in status
    
    def test_extract_idempotency_checks_package(self, execution_model):
        """Тест извлечения проверок идемпотентности для пакетов"""
        checks = execution_model._extract_idempotency_checks("apt-get install nginx")
        
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.PACKAGE_INSTALLED
        assert checks[0].target == "nginx"
    
    def test_extract_idempotency_checks_file(self, execution_model):
        """Тест извлечения проверок идемпотентности для файлов"""
        checks = execution_model._extract_idempotency_checks("touch /tmp/test.txt")
        
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.FILE_EXISTS
        assert checks[0].target == "/tmp/test.txt"
    
    def test_extract_idempotency_checks_directory(self, execution_model):
        """Тест извлечения проверок идемпотентности для директорий"""
        checks = execution_model._extract_idempotency_checks("mkdir -p /tmp/test_dir")
        
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.DIRECTORY_EXISTS
        assert checks[0].target == "/tmp/test_dir"
    
    def test_extract_idempotency_checks_service(self, execution_model):
        """Тест извлечения проверок идемпотентности для сервисов"""
        checks = execution_model._extract_idempotency_checks("systemctl start nginx")
        
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.SERVICE_RUNNING
        assert checks[0].target == "nginx"
    
    def test_extract_idempotency_checks_user(self, execution_model):
        """Тест извлечения проверок идемпотентности для пользователей"""
        checks = execution_model._extract_idempotency_checks("useradd testuser")
        
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.USER_EXISTS
        assert checks[0].target == "testuser"
    
    def test_extract_idempotency_checks_group(self, execution_model):
        """Тест извлечения проверок идемпотентности для групп"""
        checks = execution_model._extract_idempotency_checks("groupadd testgroup")
        
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.GROUP_EXISTS
        assert checks[0].target == "testgroup"
    
    def test_extract_package_name(self, execution_model):
        """Тест извлечения имени пакета"""
        # Тест различных форматов команд установки
        test_cases = [
            ("apt-get install nginx", "nginx"),
            ("apt install apache2", "apache2"),
            ("yum install docker", "docker"),
            ("dnf install git", "git")
        ]
        
        for command, expected_package in test_cases:
            package_name = execution_model._extract_package_name(command)
            assert package_name == expected_package
    
    def test_extract_file_path(self, execution_model):
        """Тест извлечения пути к файлу"""
        test_cases = [
            ("touch /tmp/test.txt", "/tmp/test.txt"),
            ("echo 'hello' > /tmp/output.txt", "/tmp/output.txt"),
            ("echo 'world' >> /tmp/append.txt", "/tmp/append.txt")
        ]
        
        for command, expected_path in test_cases:
            file_path = execution_model._extract_file_path(command)
            assert file_path == expected_path
    
    def test_extract_directory_path(self, execution_model):
        """Тест извлечения пути к директории"""
        test_cases = [
            ("mkdir /tmp/test_dir", "/tmp/test_dir"),
            ("mkdir -p /tmp/nested/dir", "/tmp/nested/dir")
        ]
        
        for command, expected_path in test_cases:
            dir_path = execution_model._extract_directory_path(command)
            assert dir_path == expected_path
    
    def test_extract_service_name(self, execution_model):
        """Тест извлечения имени сервиса"""
        test_cases = [
            ("systemctl start nginx", "nginx"),
            ("systemctl enable apache2", "apache2"),
            ("service docker start", "docker")
        ]
        
        for command, expected_service in test_cases:
            service_name = execution_model._extract_service_name(command)
            assert service_name == expected_service
    
    def test_extract_username(self, execution_model):
        """Тест извлечения имени пользователя"""
        username = execution_model._extract_username("useradd testuser")
        assert username == "testuser"
    
    def test_extract_groupname(self, execution_model):
        """Тест извлечения имени группы"""
        groupname = execution_model._extract_groupname("groupadd testgroup")
        assert groupname == "testgroup"


if __name__ == "__main__":
    pytest.main([__file__])
