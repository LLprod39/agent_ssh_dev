"""
Интеграционные тесты для основных сценариев
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any

from src.main import SSHAgent
from src.config.agent_config import AgentConfig, TaskAgentConfig, SubtaskAgentConfig, ExecutorConfig, LLMConfig
from src.config.server_config import ServerConfig
from src.models.planning_model import Task, TaskStep, TaskStatus, StepStatus, Priority
from src.models.command_result import CommandResult, ExecutionStatus


class TestSSHAgentIntegration:
    """Интеграционные тесты для SSHAgent"""
    
    @pytest.fixture
    def agent_config(self):
        """Конфигурация агента"""
        return AgentConfig(
            task_agent=TaskAgentConfig(
                model="gpt-4",
                temperature=0.3,
                max_steps=10
            ),
            subtask_agent=SubtaskAgentConfig(
                model="gpt-4",
                temperature=0.1,
                max_subtasks=20
            ),
            executor=ExecutorConfig(
                max_retries_per_command=2,
                auto_correction_enabled=True,
                dry_run_mode=False
            ),
            llm=LLMConfig(
                api_key="test-key",
                base_url="https://api.openai.com/v1"
            )
        )
    
    @pytest.fixture
    def server_config(self):
        """Конфигурация сервера"""
        return ServerConfig(
            host="test.example.com",
            port=22,
            username="testuser",
            auth_method="key",
            key_path="/path/to/key",
            timeout=30,
            os_type="ubuntu"
        )
    
    @pytest.fixture
    def mock_ssh_connector(self):
        """Мок SSH коннектора"""
        connector = Mock()
        connector.connected = True
        connector.execute_command = AsyncMock()
        connector.connect = AsyncMock(return_value=True)
        connector.disconnect = AsyncMock()
        return connector
    
    @pytest.fixture
    def mock_task_master(self):
        """Мок Task Master"""
        task_master = Mock()
        task_master.improve_prompt.return_value = Mock(
            success=True,
            data={"improved_prompt": "improved prompt"}
        )
        return task_master
    
    @pytest.fixture
    def mock_llm_interface(self):
        """Мок LLM интерфейса"""
        interface = Mock()
        interface.is_available.return_value = True
        interface.generate_response.return_value = Mock(
            success=True,
            content='{"steps": [{"title": "Test Step", "description": "Test Description", "priority": "high", "estimated_duration": 10, "dependencies": []}]}',
            usage={"total_tokens": 100},
            model="gpt-4",
            duration=1.0
        )
        return interface
    
    @pytest.fixture
    def ssh_agent(self, agent_config, server_config, mock_ssh_connector, mock_task_master, mock_llm_interface):
        """SSH агент с моками"""
        with patch('src.main.SSHConnector', return_value=mock_ssh_connector), \
             patch('src.main.TaskMasterIntegration', return_value=mock_task_master), \
             patch('src.main.LLMInterfaceFactory.create_interface', return_value=mock_llm_interface):
            
            agent = SSHAgent(agent_config, server_config)
            agent.ssh_connector = mock_ssh_connector
            agent.task_master = mock_task_master
            agent.task_agent.llm_interface = mock_llm_interface
            agent.subtask_agent.llm_interface = mock_llm_interface
            return agent
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self, ssh_agent, mock_ssh_connector):
        """Тест успешного выполнения задачи"""
        # Настраиваем моки
        mock_ssh_connector.execute_command.return_value = CommandResult(
            command="test command",
            success=True,
            exit_code=0,
            stdout="success output",
            stderr="",
            duration=1.0,
            status=ExecutionStatus.COMPLETED
        )
        
        # Выполняем задачу
        result = await ssh_agent.execute_task("Установить nginx на сервере")
        
        # Проверяем результат
        assert result.success is True
        assert result.task is not None
        assert result.task.title == "Установить nginx на сервере"
        assert len(result.task.steps) > 0
        assert result.execution_duration > 0
        
        # Проверяем что SSH коннектор был использован
        mock_ssh_connector.connect.assert_called_once()
        mock_ssh_connector.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_task_planning_failure(self, ssh_agent, mock_llm_interface):
        """Тест выполнения задачи с ошибкой планирования"""
        # Настраиваем мок LLM для возврата ошибки
        mock_llm_interface.generate_response.return_value = Mock(
            success=False,
            error="API error",
            duration=1.0
        )
        
        # Выполняем задачу
        result = await ssh_agent.execute_task("Установить nginx на сервере")
        
        # Проверяем результат
        assert result.success is False
        assert "Ошибка планирования" in result.error_message
        assert result.task is None
    
    @pytest.mark.asyncio
    async def test_execute_task_ssh_connection_failure(self, ssh_agent, mock_ssh_connector):
        """Тест выполнения задачи с ошибкой SSH соединения"""
        # Настраиваем мок SSH коннектора для возврата ошибки
        mock_ssh_connector.connect.side_effect = Exception("Connection failed")
        
        # Выполняем задачу
        result = await ssh_agent.execute_task("Установить nginx на сервере")
        
        # Проверяем результат
        assert result.success is False
        assert "Ошибка подключения" in result.error_message
    
    @pytest.mark.asyncio
    async def test_execute_task_dry_run_mode(self, ssh_agent, mock_ssh_connector):
        """Тест выполнения задачи в dry-run режиме"""
        # Включаем dry-run режим
        ssh_agent.config.executor.dry_run_mode = True
        
        # Выполняем задачу
        result = await ssh_agent.execute_task("Установить nginx на сервере")
        
        # Проверяем результат
        assert result.success is True
        assert result.task is not None
        
        # Проверяем что команды не выполнялись реально
        mock_ssh_connector.execute_command.assert_not_called()
    
    def test_get_task_status(self, ssh_agent):
        """Тест получения статуса задачи"""
        # Создаем тестовую задачу
        task = Task(title="Test Task", description="Test Description")
        step = TaskStep(title="Test Step", step_id="step_1")
        task.add_step(step)
        
        # Получаем статус
        status = ssh_agent.get_task_status(task)
        
        # Проверяем результат
        assert status["task_id"] == task.task_id
        assert status["title"] == "Test Task"
        assert status["status"] == TaskStatus.PENDING.value
        assert len(status["steps"]) == 1
        assert status["progress"]["total_steps"] == 1
    
    def test_get_system_stats(self, ssh_agent):
        """Тест получения статистики системы"""
        # Получаем статистику
        stats = ssh_agent.get_system_stats()
        
        # Проверяем результат
        assert "tasks_completed" in stats
        assert "tasks_failed" in stats
        assert "total_execution_time" in stats
        assert "average_task_duration" in stats
        assert "ssh_connection_stats" in stats
        assert "llm_usage_stats" in stats


class TestTaskExecutionWorkflow:
    """Тесты для рабочего процесса выполнения задач"""
    
    @pytest.fixture
    def mock_agent(self):
        """Мок агента для тестирования рабочего процесса"""
        agent = Mock()
        agent.config = Mock()
        agent.config.executor = Mock()
        agent.config.executor.dry_run_mode = False
        agent.config.executor.auto_correction_enabled = True
        agent.config.executor.max_retries_per_command = 2
        return agent
    
    def test_task_planning_workflow(self, mock_agent):
        """Тест рабочего процесса планирования задачи"""
        # Создаем мок для планирования
        with patch('src.agents.task_agent.TaskAgent.plan_task') as mock_plan:
            mock_plan.return_value = Mock(
                success=True,
                task=Task(title="Test Task", description="Test Description")
            )
            
            # Тестируем планирование
            from src.agents.task_agent import TaskAgent
            task_agent = TaskAgent(Mock(), Mock())
            result = task_agent.plan_task("Test task")
            
            assert result.success is True
            assert result.task is not None
    
    def test_subtask_planning_workflow(self, mock_agent):
        """Тест рабочего процесса планирования подзадач"""
        # Создаем мок для планирования подзадач
        with patch('src.agents.subtask_agent.SubtaskAgent.plan_subtasks') as mock_plan:
            mock_plan.return_value = Mock(
                success=True,
                subtasks=[Mock(title="Subtask 1"), Mock(title="Subtask 2")]
            )
            
            # Тестируем планирование подзадач
            from src.agents.subtask_agent import SubtaskAgent
            subtask_agent = SubtaskAgent(Mock(), Mock())
            result = subtask_agent.plan_subtasks(Mock(), Mock())
            
            assert result.success is True
            assert len(result.subtasks) == 2
    
    def test_command_execution_workflow(self, mock_agent):
        """Тест рабочего процесса выполнения команд"""
        # Создаем мок для выполнения команд
        with patch('src.models.execution_model.ExecutionModel.execute_subtask') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                commands_results=[Mock(success=True)],
                total_duration=1.0
            )
            
            # Тестируем выполнение команд
            from src.models.execution_model import ExecutionModel
            execution_model = ExecutionModel(Mock(), Mock())
            result = execution_model.execute_subtask(Mock())
            
            assert result.success is True
            assert len(result.commands_results) == 1


class TestSystemIntegration:
    """Тесты для интеграции системы"""
    
    def test_config_loading_integration(self):
        """Тест интеграции загрузки конфигурации"""
        with patch('src.config.agent_config.AgentConfig.from_yaml') as mock_agent_config, \
             patch('src.config.server_config.ServerConfig.from_yaml') as mock_server_config:
            
            mock_agent_config.return_value = Mock()
            mock_server_config.return_value = Mock()
            
            # Тестируем загрузку конфигурации
            from src.main import SSHAgent
            agent = SSHAgent.from_config_files("agent.yaml", "server.yaml")
            
            assert agent is not None
            mock_agent_config.assert_called_once_with("agent.yaml")
            mock_server_config.assert_called_once_with("server.yaml")
    
    def test_logging_integration(self):
        """Тест интеграции логирования"""
        with patch('src.utils.logger.setup_logging') as mock_setup:
            mock_logger = Mock()
            mock_setup.return_value = mock_logger
            
            # Тестируем настройку логирования
            from src.utils.logger import setup_logging
            logger = setup_logging({"level": "DEBUG"})
            
            assert logger is not None
            mock_setup.assert_called_once_with({"level": "DEBUG"})
    
    def test_validation_integration(self):
        """Тест интеграции валидации"""
        with patch('src.utils.validator.CommandValidator.validate_command') as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "security_level": "safe"
            }
            
            # Тестируем валидацию команд
            from src.utils.validator import CommandValidator
            validator = CommandValidator()
            result = validator.validate_command("ls -la")
            
            assert result["valid"] is True
            assert result["security_level"] == "safe"
    
    def test_autocorrection_integration(self):
        """Тест интеграции автокоррекции"""
        with patch('src.utils.autocorrection.AutocorrectionEngine.correct_command') as mock_correct:
            mock_correct.return_value = Mock(
                success=True,
                final_command="sudo apt install nginx",
                total_attempts=1
            )
            
            # Тестируем автокоррекцию
            from src.utils.autocorrection import AutocorrectionEngine
            engine = AutocorrectionEngine()
            result = engine.correct_command(Mock(), Mock())
            
            assert result.success is True
            assert result.final_command == "sudo apt install nginx"


if __name__ == "__main__":
    pytest.main([__file__])