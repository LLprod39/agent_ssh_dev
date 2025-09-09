"""
Тесты для Subtask Agent
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.agents.subtask_agent import SubtaskAgent, Subtask, SubtaskPlanningContext, SubtaskPlanningResult
from src.config.agent_config import AgentConfig, SubtaskAgentConfig, LLMConfig
from src.models.planning_model import TaskStep, Priority
from src.models.llm_interface import LLMResponse, LLMRequest
from src.agents.task_master_integration import TaskMasterResult


class TestSubtaskAgent:
    """Тесты для SubtaskAgent"""
    
    @pytest.fixture
    def mock_config(self):
        """Мок конфигурации"""
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.test.com/v1"
        )
        subtask_config = SubtaskAgentConfig(
            model="gpt-4",
            temperature=0.1,
            max_subtasks=20,
            max_tokens=3000
        )
        
        config = Mock(spec=AgentConfig)
        config.subtask_agent = subtask_config
        config.llm = llm_config
        
        return config
    
    @pytest.fixture
    def mock_task_master(self):
        """Мок Task Master"""
        task_master = Mock()
        task_master.improve_prompt.return_value = TaskMasterResult(
            success=True,
            data={"improved_prompt": "improved prompt"}
        )
        return task_master
    
    @pytest.fixture
    def mock_llm_interface(self):
        """Мок LLM интерфейса"""
        llm_interface = Mock()
        llm_interface.is_available.return_value = True
        llm_interface.generate_response.return_value = LLMResponse(
            success=True,
            content=self._get_mock_llm_response(),
            usage={"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50}
        )
        return llm_interface
    
    @pytest.fixture
    def sample_step(self):
        """Пример основного шага"""
        return TaskStep(
            step_id="test_step_1",
            title="Установка Nginx",
            description="Установить и настроить веб-сервер Nginx",
            priority=Priority.HIGH,
            estimated_duration=15
        )
    
    @pytest.fixture
    def sample_context(self, sample_step):
        """Пример контекста планирования"""
        return SubtaskPlanningContext(
            step=sample_step,
            server_info={"os": "linux", "arch": "x86_64"},
            os_type="ubuntu",
            installed_services=["ssh"],
            available_tools=["apt", "systemctl", "curl"],
            constraints=["Безопасные команды"],
            previous_subtasks=[],
            environment={}
        )
    
    def _get_mock_llm_response(self):
        """Мок ответа LLM"""
        return """
        {
            "subtasks": [
                {
                    "title": "Обновление системы",
                    "description": "Обновить список пакетов",
                    "commands": ["sudo apt update"],
                    "health_checks": ["apt list --upgradable | wc -l"],
                    "expected_output": "Обновление завершено",
                    "rollback_commands": [],
                    "dependencies": [],
                    "timeout": 30
                },
                {
                    "title": "Установка Nginx",
                    "description": "Установить пакет nginx",
                    "commands": ["sudo apt install -y nginx"],
                    "health_checks": ["dpkg -l | grep nginx"],
                    "expected_output": "Nginx установлен",
                    "rollback_commands": ["sudo apt remove -y nginx"],
                    "dependencies": [],
                    "timeout": 30
                },
                {
                    "title": "Запуск Nginx",
                    "description": "Запустить и включить Nginx",
                    "commands": ["sudo systemctl start nginx", "sudo systemctl enable nginx"],
                    "health_checks": ["systemctl is-active nginx", "curl -I http://localhost"],
                    "expected_output": "Nginx запущен",
                    "rollback_commands": ["sudo systemctl stop nginx"],
                    "dependencies": [],
                    "timeout": 30
                }
            ]
        }
        """
    
    @patch('src.agents.subtask_agent.LLMInterfaceFactory')
    def test_init(self, mock_factory, mock_config, mock_task_master):
        """Тест инициализации SubtaskAgent"""
        mock_interface = Mock()
        mock_interface.is_available.return_value = True
        mock_factory.create_interface.return_value = mock_interface
        
        agent = SubtaskAgent(mock_config, mock_task_master)
        
        assert agent.config == mock_config
        assert agent.subtask_agent_config == mock_config.subtask_agent
        assert agent.task_master == mock_task_master
        assert agent.llm_interface == mock_interface
    
    @patch('src.agents.subtask_agent.LLMInterfaceFactory')
    def test_plan_subtasks_success(self, mock_factory, mock_config, mock_task_master, 
                                 mock_llm_interface, sample_step, sample_context):
        """Тест успешного планирования подзадач"""
        mock_factory.create_interface.return_value = mock_llm_interface
        
        agent = SubtaskAgent(mock_config, mock_task_master)
        result = agent.plan_subtasks(sample_step, sample_context)
        
        assert result.success is True
        assert len(result.subtasks) == 3
        assert result.planning_duration is not None
        assert result.llm_usage is not None
        
        # Проверяем первую подзадачу
        first_subtask = result.subtasks[0]
        assert first_subtask.title == "Обновление системы"
        assert "sudo apt update" in first_subtask.commands
        assert len(first_subtask.health_checks) > 0
    
    @patch('src.agents.subtask_agent.LLMInterfaceFactory')
    def test_plan_subtasks_llm_error(self, mock_factory, mock_config, mock_task_master, 
                                   sample_step, sample_context):
        """Тест ошибки LLM при планировании"""
        mock_interface = Mock()
        mock_interface.is_available.return_value = True
        mock_interface.generate_response.return_value = LLMResponse(
            success=False,
            error="LLM недоступен"
        )
        mock_factory.create_interface.return_value = mock_interface
        
        agent = SubtaskAgent(mock_config, mock_task_master)
        result = agent.plan_subtasks(sample_step, sample_context)
        
        assert result.success is False
        assert "LLM недоступен" in result.error_message
    
    @patch('src.agents.subtask_agent.LLMInterfaceFactory')
    def test_plan_subtasks_invalid_json(self, mock_factory, mock_config, mock_task_master, 
                                      sample_step, sample_context):
        """Тест невалидного JSON ответа"""
        mock_interface = Mock()
        mock_interface.is_available.return_value = True
        mock_interface.generate_response.return_value = LLMResponse(
            success=True,
            content="Невалидный JSON ответ"
        )
        mock_factory.create_interface.return_value = mock_interface
        
        agent = SubtaskAgent(mock_config, mock_task_master)
        result = agent.plan_subtasks(sample_step, sample_context)
        
        assert result.success is False
        assert "Не удалось извлечь подзадачи" in result.error_message
    
    def test_create_default_context(self, mock_config, sample_step):
        """Тест создания контекста по умолчанию"""
        agent = SubtaskAgent(mock_config)
        context = agent._create_default_context(sample_step)
        
        assert context.step == sample_step
        assert context.os_type == "ubuntu"
        assert "apt" in context.available_tools
    
    def test_build_subtask_planning_prompt(self, mock_config, sample_step, sample_context):
        """Тест построения промта для планирования"""
        agent = SubtaskAgent(mock_config)
        prompt = agent._build_subtask_planning_prompt(sample_step, sample_context)
        
        assert "Установка Nginx" in prompt
        assert "ubuntu" in prompt
        assert "apt" in prompt
        assert "JSON" in prompt
    
    def test_parse_llm_response(self, mock_config):
        """Тест парсинга ответа LLM"""
        agent = SubtaskAgent(mock_config)
        response_content = self._get_mock_llm_response()
        
        subtasks = agent._parse_llm_response(response_content, "test_step")
        
        assert len(subtasks) == 3
        assert all(isinstance(subtask, Subtask) for subtask in subtasks)
        assert subtasks[0].title == "Обновление системы"
        assert subtasks[1].title == "Установка Nginx"
        assert subtasks[2].title == "Запуск Nginx"
    
    def test_validate_subtasks(self, mock_config, sample_context):
        """Тест валидации подзадач"""
        agent = SubtaskAgent(mock_config)
        
        # Создаем валидные подзадачи
        valid_subtasks = [
            Subtask(
                subtask_id="test_1",
                title="Test 1",
                description="Test description",
                commands=["sudo apt update"],
                health_checks=["apt list --upgradable | wc -l"]
            ),
            Subtask(
                subtask_id="test_2",
                title="Test 2",
                description="Test description",
                commands=["sudo apt install nginx"],
                health_checks=["dpkg -l | grep nginx"]
            )
        ]
        
        result = agent._validate_subtasks(valid_subtasks, sample_context)
        assert result["valid"] is True
        assert result["subtasks_count"] == 2
        
        # Создаем невалидные подзадачи
        invalid_subtasks = [
            Subtask(
                subtask_id="test_1",
                title="Test 1",
                description="Test description",
                commands=[],  # Нет команд
                health_checks=["apt list --upgradable | wc -l"]
            )
        ]
        
        result = agent._validate_subtasks(invalid_subtasks, sample_context)
        assert result["valid"] is False
        assert len(result["issues"]) > 0
    
    def test_is_dangerous_command(self, mock_config):
        """Тест проверки опасных команд"""
        agent = SubtaskAgent(mock_config)
        
        # Безопасные команды
        safe_commands = [
            "sudo apt update",
            "systemctl start nginx",
            "curl -I http://localhost",
            "mkdir -p /var/www"
        ]
        
        for cmd in safe_commands:
            assert agent._is_dangerous_command(cmd) is False
        
        # Опасные команды
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            "chmod 777 /",
            "halt"
        ]
        
        for cmd in dangerous_commands:
            assert agent._is_dangerous_command(cmd) is True
    
    def test_sort_subtasks_by_dependencies(self, mock_config):
        """Тест сортировки подзадач по зависимостям"""
        agent = SubtaskAgent(mock_config)
        
        subtasks = [
            Subtask(
                subtask_id="task_3",
                title="Task 3",
                description="Depends on task_1 and task_2",
                commands=["echo task3"],
                health_checks=["test task3"],
                dependencies=["task_1", "task_2"]
            ),
            Subtask(
                subtask_id="task_1",
                title="Task 1",
                description="No dependencies",
                commands=["echo task1"],
                health_checks=["test task1"],
                dependencies=[]
            ),
            Subtask(
                subtask_id="task_2",
                title="Task 2",
                description="Depends on task_1",
                commands=["echo task2"],
                health_checks=["test task2"],
                dependencies=["task_1"]
            )
        ]
        
        agent._sort_subtasks_by_dependencies(subtasks)
        
        # Проверяем порядок выполнения
        assert subtasks[0].subtask_id == "task_1"  # Нет зависимостей
        assert subtasks[1].subtask_id == "task_2"  # Зависит от task_1
        assert subtasks[2].subtask_id == "task_3"  # Зависит от task_1 и task_2
    
    def test_get_subtask_status(self, mock_config):
        """Тест получения статуса подзадач"""
        agent = SubtaskAgent(mock_config)
        
        subtasks = [
            Subtask(
                subtask_id="test_1",
                title="Test 1",
                description="Test",
                commands=["cmd1", "cmd2"],
                health_checks=["check1"]
            ),
            Subtask(
                subtask_id="test_2",
                title="Test 2",
                description="Test",
                commands=["cmd3"],
                health_checks=["check2", "check3"]
            )
        ]
        
        status = agent.get_subtask_status(subtasks)
        
        assert status["subtasks_count"] == 2
        assert status["total_commands"] == 3
        assert status["total_health_checks"] == 3
        assert len(status["subtasks"]) == 2
    
    def test_generate_health_check_commands(self, mock_config, sample_context):
        """Тест генерации health-check команд"""
        agent = SubtaskAgent(mock_config)
        
        # Подзадача с командами установки
        install_subtask = Subtask(
            subtask_id="test_1",
            title="Install",
            description="Install package",
            commands=["sudo apt install nginx"],
            health_checks=[]
        )
        
        health_checks = agent.generate_health_check_commands(install_subtask, sample_context)
        assert len(health_checks) > 0
        assert any("dpkg" in check for check in health_checks)
        
        # Подзадача с systemctl командами
        systemctl_subtask = Subtask(
            subtask_id="test_2",
            title="Service",
            description="Manage service",
            commands=["sudo systemctl start nginx"],
            health_checks=[]
        )
        
        health_checks = agent.generate_health_check_commands(systemctl_subtask, sample_context)
        assert any("systemctl" in check for check in health_checks)


class TestSubtask:
    """Тесты для класса Subtask"""
    
    def test_subtask_creation(self):
        """Тест создания подзадачи"""
        subtask = Subtask(
            subtask_id="test_1",
            title="Test Task",
            description="Test description",
            commands=["sudo apt update"],
            health_checks=["apt list --upgradable | wc -l"]
        )
        
        assert subtask.subtask_id == "test_1"
        assert subtask.title == "Test Task"
        assert subtask.description == "Test description"
        assert len(subtask.commands) == 1
        assert len(subtask.health_checks) == 1
        assert subtask.rollback_commands == []
        assert subtask.dependencies == []
        assert subtask.metadata == {}


class TestSubtaskPlanningContext:
    """Тесты для класса SubtaskPlanningContext"""
    
    def test_context_creation(self):
        """Тест создания контекста планирования"""
        step = TaskStep(title="Test Step")
        
        context = SubtaskPlanningContext(
            step=step,
            server_info={"os": "linux"},
            os_type="ubuntu",
            installed_services=["ssh"],
            available_tools=["apt"],
            constraints=["safe commands"],
            previous_subtasks=[],
            environment={}
        )
        
        assert context.step == step
        assert context.os_type == "ubuntu"
        assert "ssh" in context.installed_services
        assert "apt" in context.available_tools


if __name__ == "__main__":
    pytest.main([__file__])

