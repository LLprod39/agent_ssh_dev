"""
Тесты для системы идемпотентности
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.utils.idempotency_system import (
    IdempotencySystem,
    IdempotencyCheck,
    IdempotencyCheckType,
    IdempotencyResult,
    StateSnapshot
)
from src.models.command_result import CommandResult, ExecutionStatus


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


@pytest.fixture
def mock_ssh_connector():
    """Фикстура для мок SSH коннектора"""
    return MockSSHConnector()


@pytest.fixture
def idempotency_config():
    """Фикстура для конфигурации идемпотентности"""
    return {
        "enabled": True,
        "cache_ttl": 300,
        "max_snapshots": 10,
        "auto_rollback": True,
        "check_timeout": 30
    }


@pytest.fixture
def idempotency_system(mock_ssh_connector, idempotency_config):
    """Фикстура для системы идемпотентности"""
    return IdempotencySystem(mock_ssh_connector, idempotency_config)


class TestIdempotencySystem:
    """Тесты для IdempotencySystem"""
    
    def test_initialization(self, idempotency_system):
        """Тест инициализации системы"""
        assert idempotency_system is not None
        assert idempotency_system.config["enabled"] is True
        assert idempotency_system.cache_ttl == 300
        assert len(idempotency_system.state_snapshots) == 0
        assert idempotency_system.current_snapshot is None
    
    def test_create_state_snapshot(self, idempotency_system):
        """Тест создания снимка состояния"""
        snapshot = idempotency_system.create_state_snapshot("test_task_001")
        
        assert isinstance(snapshot, StateSnapshot)
        assert snapshot.snapshot_id.startswith("test_task_001_")
        assert snapshot.timestamp is not None
        assert len(snapshot.checks) == 0
        assert len(snapshot.system_info) > 0
        
        # Проверяем, что снимок сохранен
        assert snapshot.snapshot_id in idempotency_system.state_snapshots
        assert idempotency_system.current_snapshot == snapshot
    
    def test_generate_idempotent_command_package(self, idempotency_system):
        """Тест генерации идемпотентной команды для пакета"""
        cmd, checks = idempotency_system.generate_idempotent_command(
            "apt-get install nginx", "install_package", "nginx"
        )
        
        assert "dpkg -l | grep -q" in cmd
        assert "apt-get install" in cmd
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.PACKAGE_INSTALLED
        assert checks[0].target == "nginx"
    
    def test_generate_idempotent_command_file(self, idempotency_system):
        """Тест генерации идемпотентной команды для файла"""
        cmd, checks = idempotency_system.generate_idempotent_command(
            "touch /tmp/test.txt", "create_file", "/tmp/test.txt"
        )
        
        assert "test -f" in cmd
        assert "touch" in cmd
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.FILE_EXISTS
        assert checks[0].target == "/tmp/test.txt"
    
    def test_generate_idempotent_command_directory(self, idempotency_system):
        """Тест генерации идемпотентной команды для директории"""
        cmd, checks = idempotency_system.generate_idempotent_command(
            "mkdir -p /tmp/test_dir", "create_directory", "/tmp/test_dir"
        )
        
        assert "test -d" in cmd
        assert "mkdir -p" in cmd
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.DIRECTORY_EXISTS
        assert checks[0].target == "/tmp/test_dir"
    
    def test_generate_idempotent_command_service(self, idempotency_system):
        """Тест генерации идемпотентной команды для сервиса"""
        cmd, checks = idempotency_system.generate_idempotent_command(
            "systemctl start nginx", "start_service", "nginx"
        )
        
        assert "systemctl is-active" in cmd
        assert "systemctl start" in cmd
        assert len(checks) == 1
        assert checks[0].check_type == IdempotencyCheckType.SERVICE_RUNNING
        assert checks[0].target == "nginx"
    
    def test_check_idempotency_success(self, idempotency_system, mock_ssh_connector):
        """Тест успешной проверки идемпотентности"""
        # Настраиваем мок для успешной проверки
        mock_ssh_connector.set_mock_result(
            "dpkg -l | grep -q '^ii  nginx'",
            CommandResult(
                command="dpkg -l | grep -q '^ii  nginx'",
                success=True,
                exit_code=0,
                stdout="ii  nginx  1.18.0-0ubuntu1.4  amd64  high performance web server",
                status=ExecutionStatus.COMPLETED
            )
        )
        
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        )
        
        results = idempotency_system.check_idempotency([check])
        
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].check == check
        assert results[0].current_state is not None
    
    def test_check_idempotency_failure(self, idempotency_system, mock_ssh_connector):
        """Тест неудачной проверки идемпотентности"""
        # Настраиваем мок для неудачной проверки
        mock_ssh_connector.set_mock_result(
            "test -f /nonexistent/file",
            CommandResult(
                command="test -f /nonexistent/file",
                success=False,
                exit_code=1,
                stderr="No such file or directory",
                status=ExecutionStatus.FAILED
            )
        )
        
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.FILE_EXISTS,
            target="/nonexistent/file",
            expected_state=True,
            check_command="test -f /nonexistent/file",
            success_pattern=".*",
            description="Проверка существования файла"
        )
        
        results = idempotency_system.check_idempotency([check])
        
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].check == check
        assert "No such file or directory" in results[0].error_message
    
    def test_should_skip_command_true(self, idempotency_system, mock_ssh_connector):
        """Тест пропуска команды когда состояние уже достигнуто"""
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
        
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        )
        
        should_skip = idempotency_system.should_skip_command("apt-get install nginx", [check])
        
        assert should_skip is True
    
    def test_should_skip_command_false(self, idempotency_system, mock_ssh_connector):
        """Тест выполнения команды когда состояние не достигнуто"""
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
        
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        )
        
        should_skip = idempotency_system.should_skip_command("apt-get install nginx", [check])
        
        assert should_skip is False
    
    def test_create_rollback_commands(self, idempotency_system):
        """Тест создания команд отката"""
        snapshot = StateSnapshot(
            snapshot_id="test_snapshot",
            timestamp=datetime.now(),
            checks=[],
            system_info={},
            packages_installed=["nginx", "apache2"],
            services_started=["nginx"],
            files_created=["/etc/nginx/nginx.conf"],
            users_created=["testuser"],
            groups_created=["testgroup"]
        )
        
        rollback_commands = idempotency_system.create_rollback_commands(snapshot)
        
        assert len(rollback_commands) > 0
        assert any("apt-get remove -y nginx" in cmd for cmd in rollback_commands)
        assert any("apt-get remove -y apache2" in cmd for cmd in rollback_commands)
        assert any("systemctl stop nginx" in cmd for cmd in rollback_commands)
        assert any("rm -f /etc/nginx/nginx.conf" in cmd for cmd in rollback_commands)
        assert any("userdel -r testuser" in cmd for cmd in rollback_commands)
        assert any("groupdel testgroup" in cmd for cmd in rollback_commands)
    
    def test_execute_rollback(self, idempotency_system, mock_ssh_connector):
        """Тест выполнения отката"""
        # Создаем снимок с изменениями
        snapshot = StateSnapshot(
            snapshot_id="test_rollback_snapshot",
            timestamp=datetime.now(),
            checks=[],
            system_info={},
            packages_installed=["nginx"],
            services_started=["nginx"]
        )
        
        idempotency_system.state_snapshots["test_rollback_snapshot"] = snapshot
        
        # Выполняем откат
        results = idempotency_system.execute_rollback("test_rollback_snapshot")
        
        assert len(results) > 0
        assert any("apt-get remove -y nginx" in result.command for result in results)
        assert any("systemctl stop nginx" in result.command for result in results)
    
    def test_execute_rollback_nonexistent_snapshot(self, idempotency_system):
        """Тест выполнения отката несуществующего снимка"""
        with pytest.raises(ValueError, match="Снимок nonexistent_snapshot не найден"):
            idempotency_system.execute_rollback("nonexistent_snapshot")
    
    def test_cache_functionality(self, idempotency_system, mock_ssh_connector):
        """Тест функциональности кэша"""
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx"
        )
        
        # Первый вызов - команда должна выполниться
        results1 = idempotency_system.check_idempotency([check])
        assert len(results1) == 1
        assert len(mock_ssh_connector.commands_executed) == 1
        
        # Второй вызов - команда должна быть взята из кэша
        results2 = idempotency_system.check_idempotency([check])
        assert len(results2) == 1
        assert len(mock_ssh_connector.commands_executed) == 1  # Не увеличилось
    
    def test_get_system_status(self, idempotency_system):
        """Тест получения статуса системы"""
        # Создаем снимок
        snapshot = idempotency_system.create_state_snapshot("test_task")
        
        status = idempotency_system.get_system_status()
        
        assert status["snapshots_count"] == 1
        assert status["current_snapshot"] == snapshot.snapshot_id
        assert status["cache_size"] == 0
        assert status["cache_ttl"] == 300


class TestIdempotencyCheck:
    """Тесты для IdempotencyCheck"""
    
    def test_idempotency_check_creation(self):
        """Тест создания проверки идемпотентности"""
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*",
            description="Проверка установки nginx",
            timeout=30,
            retry_count=3
        )
        
        assert check.check_type == IdempotencyCheckType.PACKAGE_INSTALLED
        assert check.target == "nginx"
        assert check.expected_state is True
        assert check.check_command == "dpkg -l | grep -q '^ii  nginx'"
        assert check.success_pattern == ".*"
        assert check.description == "Проверка установки nginx"
        assert check.timeout == 30
        assert check.retry_count == 3


class TestIdempotencyResult:
    """Тесты для IdempotencyResult"""
    
    def test_idempotency_result_creation(self):
        """Тест создания результата проверки"""
        check = IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target="nginx",
            expected_state=True,
            check_command="dpkg -l | grep -q '^ii  nginx'",
            success_pattern=".*"
        )
        
        result = IdempotencyResult(
            check=check,
            success=True,
            current_state="nginx installed",
            error_message=""
        )
        
        assert result.check == check
        assert result.success is True
        assert result.current_state == "nginx installed"
        assert result.error_message == ""
        assert result.timestamp is not None


class TestStateSnapshot:
    """Тесты для StateSnapshot"""
    
    def test_state_snapshot_creation(self):
        """Тест создания снимка состояния"""
        snapshot = StateSnapshot(
            snapshot_id="test_snapshot",
            timestamp=datetime.now(),
            checks=[],
            system_info={"os": "linux", "arch": "x86_64"},
            files_created=["/tmp/test.txt"],
            packages_installed=["nginx"]
        )
        
        assert snapshot.snapshot_id == "test_snapshot"
        assert snapshot.timestamp is not None
        assert len(snapshot.checks) == 0
        assert snapshot.system_info["os"] == "linux"
        assert len(snapshot.files_created) == 1
        assert len(snapshot.packages_installed) == 1


if __name__ == "__main__":
    pytest.main([__file__])
