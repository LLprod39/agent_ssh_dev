"""
Тесты для интеграции идемпотентности в SubtaskAgent
"""
import pytest
from unittest.mock import Mock, MagicMock

from src.agents.subtask_agent import SubtaskAgent, Subtask
from src.config.agent_config import AgentConfig
from src.utils.idempotency_system import IdempotencyCheckType


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
        from src.models.command_result import CommandResult, ExecutionStatus
        return CommandResult(
            command=command,
            success=True,
            exit_code=0,
            stdout="mock output",
            stderr="",
            duration=0.1,
            status=ExecutionStatus.COMPLETED
        )
    
    def set_mock_result(self, command: str, result):
        """Установка мок результата для команды"""
        self.mock_results[command] = result


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
def subtask_agent(mock_ssh_connector, agent_config):
    """Фикстура для SubtaskAgent"""
    return SubtaskAgent(agent_config, ssh_connector=mock_ssh_connector)


@pytest.fixture
def sample_subtask():
    """Фикстура для тестовой подзадачи"""
    return Subtask(
        subtask_id="test_subtask_001",
        title="Установка nginx",
        description="Установка веб-сервера nginx",
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


class TestSubtaskAgentIdempotency:
    """Тесты для интеграции идемпотентности в SubtaskAgent"""
    
    def test_idempotency_system_initialization(self, subtask_agent):
        """Тест инициализации системы идемпотентности"""
        assert subtask_agent.idempotency_system is not None
        assert subtask_agent.idempotency_system.config["enabled"] is True
    
    def test_generate_idempotent_commands(self, subtask_agent, sample_subtask):
        """Тест генерации идемпотентных команд"""
        idempotent_commands = subtask_agent.generate_idempotent_commands(sample_subtask)
        
        assert len(idempotent_commands) == len(sample_subtask.commands)
        
        # Проверяем, что команды стали идемпотентными
        for i, cmd in enumerate(idempotent_commands):
            original_cmd = sample_subtask.commands[i]
            
            if "apt-get install" in original_cmd:
                assert "dpkg -l | grep -q" in cmd
                assert "apt-get install" in cmd
            elif "systemctl start" in original_cmd:
                assert "systemctl is-active" in cmd
                assert "systemctl start" in cmd
            elif "touch" in original_cmd:
                assert "test -f" in cmd
                assert "touch" in cmd
    
    def test_analyze_command_package(self, subtask_agent):
        """Тест анализа команды установки пакета"""
        command_type, target = subtask_agent._analyze_command("apt-get install nginx")
        
        assert command_type == "install_package"
        assert target == "nginx"
    
    def test_analyze_command_file(self, subtask_agent):
        """Тест анализа команды создания файла"""
        command_type, target = subtask_agent._analyze_command("touch /tmp/test.txt")
        
        assert command_type == "create_file"
        assert target == "/tmp/test.txt"
    
    def test_analyze_command_directory(self, subtask_agent):
        """Тест анализа команды создания директории"""
        command_type, target = subtask_agent._analyze_command("mkdir -p /tmp/test_dir")
        
        assert command_type == "create_directory"
        assert target == "/tmp/test_dir"
    
    def test_analyze_command_service_start(self, subtask_agent):
        """Тест анализа команды запуска сервиса"""
        command_type, target = subtask_agent._analyze_command("systemctl start nginx")
        
        assert command_type == "start_service"
        assert target == "nginx"
    
    def test_analyze_command_service_enable(self, subtask_agent):
        """Тест анализа команды включения сервиса"""
        command_type, target = subtask_agent._analyze_command("systemctl enable nginx")
        
        assert command_type == "enable_service"
        assert target == "nginx"
    
    def test_analyze_command_user(self, subtask_agent):
        """Тест анализа команды создания пользователя"""
        command_type, target = subtask_agent._analyze_command("useradd testuser")
        
        assert command_type == "create_user"
        assert target == "testuser"
    
    def test_analyze_command_group(self, subtask_agent):
        """Тест анализа команды создания группы"""
        command_type, target = subtask_agent._analyze_command("groupadd testgroup")
        
        assert command_type == "create_group"
        assert target == "testgroup"
    
    def test_analyze_command_unknown(self, subtask_agent):
        """Тест анализа неизвестной команды"""
        command_type, target = subtask_agent._analyze_command("echo 'hello world'")
        
        assert command_type is None
        assert target is None
    
    def test_extract_package_name(self, subtask_agent):
        """Тест извлечения имени пакета"""
        test_cases = [
            ("apt-get install nginx", "nginx"),
            ("apt install apache2", "apache2"),
            ("yum install docker", "docker"),
            ("dnf install git", "git")
        ]
        
        for command, expected_package in test_cases:
            package_name = subtask_agent._extract_package_name(command)
            assert package_name == expected_package
    
    def test_extract_file_path(self, subtask_agent):
        """Тест извлечения пути к файлу"""
        test_cases = [
            ("touch /tmp/test.txt", "/tmp/test.txt"),
            ("echo 'hello' > /tmp/output.txt", "/tmp/output.txt"),
            ("echo 'world' >> /tmp/append.txt", "/tmp/append.txt")
        ]
        
        for command, expected_path in test_cases:
            file_path = subtask_agent._extract_file_path(command)
            assert file_path == expected_path
    
    def test_extract_directory_path(self, subtask_agent):
        """Тест извлечения пути к директории"""
        test_cases = [
            ("mkdir /tmp/test_dir", "/tmp/test_dir"),
            ("mkdir -p /tmp/nested/dir", "/tmp/nested/dir")
        ]
        
        for command, expected_path in test_cases:
            dir_path = subtask_agent._extract_directory_path(command)
            assert dir_path == expected_path
    
    def test_extract_service_name(self, subtask_agent):
        """Тест извлечения имени сервиса"""
        test_cases = [
            ("systemctl start nginx", "nginx"),
            ("systemctl enable apache2", "apache2"),
            ("service docker start", "docker")
        ]
        
        for command, expected_service in test_cases:
            service_name = subtask_agent._extract_service_name(command)
            assert service_name == expected_service
    
    def test_extract_username(self, subtask_agent):
        """Тест извлечения имени пользователя"""
        username = subtask_agent._extract_username("useradd testuser")
        assert username == "testuser"
    
    def test_extract_groupname(self, subtask_agent):
        """Тест извлечения имени группы"""
        groupname = subtask_agent._extract_groupname("groupadd testgroup")
        assert groupname == "testgroup"
    
    def test_enhance_subtask_with_idempotency(self, subtask_agent, sample_subtask):
        """Тест улучшения подзадачи идемпотентностью"""
        enhanced_subtask = subtask_agent.enhance_subtask_with_idempotency(sample_subtask)
        
        # Проверяем, что подзадача была улучшена
        assert enhanced_subtask.metadata.get("idempotent_enhanced") is True
        assert "original_commands" in enhanced_subtask.metadata
        assert "idempotency_checks" in enhanced_subtask.metadata
        
        # Проверяем, что команды стали идемпотентными
        assert len(enhanced_subtask.commands) == len(sample_subtask.commands)
        
        # Проверяем, что есть проверки идемпотентности
        idempotency_checks = enhanced_subtask.metadata.get("idempotency_checks", [])
        assert len(idempotency_checks) > 0
        
        # Проверяем типы проверок
        check_types = [check.check_type for check in idempotency_checks]
        assert IdempotencyCheckType.PACKAGE_INSTALLED in check_types
        assert IdempotencyCheckType.SERVICE_RUNNING in check_types
        assert IdempotencyCheckType.FILE_EXISTS in check_types
    
    def test_enhance_subtask_without_idempotency_system(self, agent_config, sample_subtask):
        """Тест улучшения подзадачи без системы идемпотентности"""
        # Создаем агента без SSH коннектора
        subtask_agent_no_ssh = SubtaskAgent(agent_config, ssh_connector=None)
        
        enhanced_subtask = subtask_agent_no_ssh.enhance_subtask_with_idempotency(sample_subtask)
        
        # Подзадача должна остаться неизменной
        assert enhanced_subtask == sample_subtask
        assert enhanced_subtask.metadata.get("idempotent_enhanced") is not True
    
    def test_optimize_subtasks_with_idempotency(self, subtask_agent, sample_subtask):
        """Тест оптимизации подзадач с идемпотентностью"""
        from src.agents.subtask_agent import SubtaskPlanningContext
        from src.models.planning_model import TaskStep, Priority
        
        # Создаем контекст планирования
        step = TaskStep(
            step_id="test_step",
            title="Test Step",
            description="Test Description",
            priority=Priority.MEDIUM
        )
        
        context = SubtaskPlanningContext(
            step=step,
            server_info={"os": "linux"},
            os_type="ubuntu",
            installed_services=[],
            available_tools=["apt", "systemctl"],
            constraints=[],
            previous_subtasks=[],
            environment={}
        )
        
        # Создаем список подзадач
        subtasks = [sample_subtask]
        
        # Вызываем оптимизацию
        subtask_agent._optimize_subtasks(subtasks, context)
        
        # Проверяем, что подзадача была улучшена
        assert subtasks[0].metadata.get("idempotent_enhanced") is True


class TestSubtaskAgentWithoutIdempotency:
    """Тесты для SubtaskAgent без системы идемпотентности"""
    
    def test_initialization_without_ssh_connector(self, agent_config):
        """Тест инициализации без SSH коннектора"""
        subtask_agent = SubtaskAgent(agent_config, ssh_connector=None)
        
        assert subtask_agent.idempotency_system is None
    
    def test_generate_idempotent_commands_without_system(self, agent_config, sample_subtask):
        """Тест генерации идемпотентных команд без системы"""
        subtask_agent = SubtaskAgent(agent_config, ssh_connector=None)
        
        idempotent_commands = subtask_agent.generate_idempotent_commands(sample_subtask)
        
        # Команды должны остаться неизменными
        assert idempotent_commands == sample_subtask.commands
    
    def test_enhance_subtask_without_system(self, agent_config, sample_subtask):
        """Тест улучшения подзадачи без системы"""
        subtask_agent = SubtaskAgent(agent_config, ssh_connector=None)
        
        enhanced_subtask = subtask_agent.enhance_subtask_with_idempotency(sample_subtask)
        
        # Подзадача должна остаться неизменной
        assert enhanced_subtask == sample_subtask


if __name__ == "__main__":
    pytest.main([__file__])
