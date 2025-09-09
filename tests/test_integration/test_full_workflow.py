"""
Интеграционные тесты полного рабочего процесса
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.main import SSHAgent
from src.config.agent_config import AgentConfig
from src.config.server_config import ServerConfig
from src.models.planning_model import Task, TaskStep, Priority
from src.models.execution_model import ExecutionContext, CommandResult


class TestFullWorkflow:
    """Тесты полного рабочего процесса"""
    
    @pytest.fixture
    def mock_agent_config(self):
        """Фикстура конфигурации агента"""
        return AgentConfig(
            task_agent=Mock(
                model="gpt-4",
                temperature=0.3,
                max_steps=10
            ),
            subtask_agent=Mock(
                model="gpt-4",
                temperature=0.1,
                max_subtasks=20
            ),
            executor=Mock(
                max_retries_per_command=2,
                auto_correction_enabled=True,
                dry_run_mode=False
            ),
            error_handler=Mock(
                error_threshold_per_step=4,
                send_to_planner_after_threshold=True,
                human_escalation_threshold=3
            ),
            llm=Mock(
                api_key="test-key",
                base_url="https://api.openai.com/v1"
            )
        )
    
    @pytest.fixture
    def mock_server_config(self):
        """Фикстура конфигурации сервера"""
        return ServerConfig(
            host="test.example.com",
            port=22,
            username="testuser",
            auth_method="key",
            key_path="/path/to/test/key",
            timeout=30,
            os_type="ubuntu"
        )
    
    @pytest.fixture
    def mock_ssh_connector(self):
        """Фикстура SSH коннектора"""
        connector = Mock()
        connector.connected = True
        connector.connect = AsyncMock(return_value=True)
        connector.disconnect = AsyncMock()
        connector.execute_command = AsyncMock(return_value=CommandResult(
            command="test",
            success=True,
            exit_code=0,
            stdout="test output",
            stderr=""
        ))
        return connector
    
    @pytest.fixture
    def mock_task_master(self):
        """Фикстура Task Master"""
        task_master = Mock()
        task_master.improve_prompt = Mock(return_value=Mock(
            success=True,
            data={"improved_prompt": "improved prompt"}
        ))
        return task_master
    
    @pytest.fixture
    def mock_llm_interface(self):
        """Фикстура LLM интерфейса"""
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
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_task_execution_workflow(
        self, 
        mock_agent_config, 
        mock_server_config,
        mock_ssh_connector,
        mock_task_master,
        mock_llm_interface
    ):
        """Тест полного рабочего процесса выполнения задачи"""
        
        with patch('src.main.SSHConnector', return_value=mock_ssh_connector):
            with patch('src.main.TaskMasterIntegration', return_value=mock_task_master):
                with patch('src.main.LLMInterfaceFactory.create_interface', return_value=mock_llm_interface):
                    
                    # Создаем агента
                    agent = SSHAgent(mock_agent_config, mock_server_config)
                    
                    # Выполняем задачу
                    task_description = "Установить и настроить nginx на сервере"
                    result = await agent.execute_task(task_description)
                    
                    # Проверяем результат
                    assert result is not None
                    assert hasattr(result, 'success')
                    assert hasattr(result, 'task')
                    assert hasattr(result, 'execution_summary')
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_task_planning_workflow(
        self,
        mock_agent_config,
        mock_task_master,
        mock_llm_interface
    ):
        """Тест рабочего процесса планирования задачи"""
        
        with patch('src.main.TaskMasterIntegration', return_value=mock_task_master):
            with patch('src.main.LLMInterfaceFactory.create_interface', return_value=mock_llm_interface):
                
                from src.agents.task_agent import TaskAgent
                
                # Создаем Task Agent
                task_agent = TaskAgent(mock_agent_config, mock_task_master)
                task_agent.llm_interface = mock_llm_interface
                
                # Планируем задачу
                task_description = "Установить Docker на сервере"
                context = {
                    "server_info": {"os": "ubuntu", "version": "20.04"},
                    "user_requirements": task_description,
                    "constraints": ["Не перезагружать сервер"],
                    "available_tools": ["apt", "curl", "systemctl"],
                    "previous_tasks": [],
                    "environment": {"production": False}
                }
                
                result = task_agent.plan_task(task_description, context)
                
                # Проверяем результат планирования
                assert result.success is True
                assert result.task is not None
                assert result.task.title is not None
                assert len(result.task.steps) > 0
                assert result.planning_duration is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_subtask_planning_workflow(
        self,
        mock_agent_config,
        mock_llm_interface
    ):
        """Тест рабочего процесса планирования подзадач"""
        
        with patch('src.main.LLMInterfaceFactory.create_interface', return_value=mock_llm_interface):
            
            from src.agents.subtask_agent import SubtaskAgent
            from src.models.planning_model import Task, TaskStep, Priority
            
            # Создаем Subtask Agent
            subtask_agent = SubtaskAgent(mock_agent_config)
            subtask_agent.llm_interface = mock_llm_interface
            
            # Создаем задачу с шагом
            task = Task(title="Установить nginx", description="Установить веб-сервер")
            step = TaskStep(
                title="Установить nginx",
                description="Установить nginx через apt",
                step_id="step_1",
                priority=Priority.HIGH,
                estimated_duration=10
            )
            task.add_step(step)
            
            # Планируем подзадачи
            result = subtask_agent.plan_subtasks(step, {"os": "ubuntu"})
            
            # Проверяем результат
            assert result.success is True
            assert result.subtasks is not None
            assert len(result.subtasks) > 0
            assert result.planning_duration is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_command_execution_workflow(
        self,
        mock_agent_config,
        mock_ssh_connector
    ):
        """Тест рабочего процесса выполнения команд"""
        
        from src.models.execution_model import ExecutionModel, ExecutionContext
        from src.agents.subtask_agent import Subtask
        
        # Создаем Execution Model
        execution_model = ExecutionModel(mock_agent_config, mock_ssh_connector)
        
        # Создаем подзадачу
        subtask = Subtask(
            subtask_id="test_001",
            title="Установить nginx",
            description="Установить веб-сервер nginx",
            commands=[
                "sudo apt update",
                "sudo apt install -y nginx"
            ],
            health_checks=[
                "systemctl is-active nginx"
            ],
            rollback_commands=[
                "sudo apt remove -y nginx"
            ]
        )
        
        # Создаем контекст выполнения
        context = ExecutionContext(
            subtask=subtask,
            ssh_connection=mock_ssh_connector,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        # Выполняем подзадачу
        result = execution_model.execute_subtask(context)
        
        # Проверяем результат
        assert result is not None
        assert hasattr(result, 'success')
        assert hasattr(result, 'subtask_id')
        assert hasattr(result, 'commands_results')
        assert hasattr(result, 'health_check_results')
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_workflow(
        self,
        mock_agent_config,
        mock_ssh_connector
    ):
        """Тест рабочего процесса обработки ошибок"""
        
        from src.agents.error_handler import ErrorHandler
        from src.models.execution_model import CommandResult, ExecutionStatus
        
        # Создаем Error Handler
        error_handler = ErrorHandler(mock_agent_config)
        
        # Создаем результаты команд с ошибками
        failed_result = CommandResult(
            command="apt install nonexistent",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Package not found",
            status=ExecutionStatus.FAILED
        )
        
        successful_result = CommandResult(
            command="apt update",
            success=True,
            exit_code=0,
            stdout="Update completed",
            stderr="",
            status=ExecutionStatus.COMPLETED
        )
        
        # Обрабатываем ошибки
        error_summary = error_handler.aggregate_errors([failed_result, successful_result])
        
        # Проверяем результат
        assert error_summary is not None
        assert hasattr(error_summary, 'total_errors')
        assert hasattr(error_summary, 'error_rate')
        assert hasattr(error_summary, 'critical_errors')
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_autocorrection_workflow(
        self,
        mock_agent_config,
        mock_ssh_connector
    ):
        """Тест рабочего процесса автокоррекции"""
        
        from src.utils.autocorrection import AutocorrectionEngine
        from src.models.execution_model import CommandResult, ExecutionStatus, ExecutionContext
        from src.agents.subtask_agent import Subtask
        
        # Создаем движок автокоррекции
        autocorrection_engine = AutocorrectionEngine()
        
        # Создаем неудачный результат команды
        failed_result = CommandResult(
            command="apt install nginx",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Создаем контекст
        subtask = Subtask(
            subtask_id="test_001",
            title="Test",
            description="Test",
            commands=["apt install nginx"],
            health_checks=[],
            rollback_commands=[]
        )
        
        context = ExecutionContext(
            subtask=subtask,
            ssh_connection=mock_ssh_connector,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        # Применяем автокоррекцию
        correction_result = autocorrection_engine.correct_command(failed_result, context)
        
        # Проверяем результат
        assert correction_result is not None
        assert hasattr(correction_result, 'success')
        assert hasattr(correction_result, 'final_command')
        assert hasattr(correction_result, 'attempts')
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dry_run_workflow(self):
        """Тест рабочего процесса dry-run"""
        
        from src.utils.dry_run_system import DryRunSystem
        from src.utils.logger import StructuredLogger
        
        # Создаем систему dry-run
        logger = Mock(spec=StructuredLogger)
        dry_run_system = DryRunSystem(logger)
        
        # Команды для симуляции
        commands = [
            "apt update",
            "apt install -y nginx",
            "systemctl start nginx",
            "systemctl enable nginx"
        ]
        
        # Выполняем симуляцию
        result = dry_run_system.simulate_execution(commands)
        
        # Проверяем результат
        assert result.success is True
        assert len(result.simulated_commands) == 4
        assert result.execution_summary is not None
        assert result.risk_summary is not None
        assert result.validation_result is not None
        assert len(result.recommendations) > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_idempotency_workflow(self):
        """Тест рабочего процесса идемпотентности"""
        
        from src.utils.idempotency_system import IdempotencySystem, IdempotencyKey
        
        # Создаем систему идемпотентности
        idempotency_system = IdempotencySystem()
        
        # Создаем ключ для операции
        key = idempotency_system.generate_idempotency_key(
            operation="install_package",
            parameters={"package": "nginx", "version": "1.18.0"},
            context={"server": "test.example.com"}
        )
        
        # Проверяем идемпотентность
        result1 = idempotency_system.check_idempotency(key)
        assert result1.status.value == "NOT_EXECUTED"
        
        # Отмечаем операцию как выполненную
        idempotency_system.mark_operation_executed(
            key,
            success=True,
            result_data={"package": "nginx", "version": "1.18.0"}
        )
        
        # Проверяем идемпотентность снова
        result2 = idempotency_system.check_idempotency(key)
        assert result2.status.value == "ALREADY_EXECUTED"
        assert result2.already_executed is True


if __name__ == "__main__":
    pytest.main([__file__])
