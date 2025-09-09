"""
Тесты для Task Agent
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.agents.task_agent import TaskAgent, TaskPlanningContext
from src.config.agent_config import AgentConfig, TaskAgentConfig, LLMConfig
from src.models.planning_model import Task, TaskStep, StepStatus, Priority, TaskStatus
from src.models.llm_interface import LLMResponse, LLMRequest
from src.agents.task_master_integration import TaskMasterIntegration, TaskMasterResult


class TestTaskAgent:
    """Тесты для Task Agent"""
    
    @pytest.fixture
    def mock_config(self):
        """Мок конфигурации"""
        llm_config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            max_tokens=2000,
            temperature=0.3,
            timeout=60
        )
        
        task_agent_config = TaskAgentConfig(
            model="gpt-4",
            temperature=0.3,
            max_steps=10,
            max_tokens=2000
        )
        
        return AgentConfig(
            task_agent=task_agent_config,
            llm=llm_config
        )
    
    @pytest.fixture
    def mock_task_master(self):
        """Мок Task Master"""
        task_master = Mock(spec=TaskMasterIntegration)
        task_master.improve_prompt.return_value = TaskMasterResult(
            success=True,
            data={"improved_prompt": "improved prompt"}
        )
        return task_master
    
    @pytest.fixture
    def mock_llm_interface(self):
        """Мок LLM интерфейса"""
        mock_interface = Mock()
        mock_interface.is_available.return_value = True
        mock_interface.generate_response.return_value = LLMResponse(
            success=True,
            content='{"steps": [{"title": "Test Step", "description": "Test Description", "priority": "high", "estimated_duration": 10, "dependencies": []}]}',
            usage={"total_tokens": 100},
            model="gpt-4",
            duration=1.0
        )
        return mock_interface
    
    @pytest.fixture
    def task_agent(self, mock_config, mock_task_master, mock_llm_interface):
        """Создание Task Agent с моками"""
        with patch('src.agents.task_agent.LLMInterfaceFactory.create_interface') as mock_factory:
            mock_factory.return_value = mock_llm_interface
            agent = TaskAgent(mock_config, mock_task_master)
            agent.llm_interface = mock_llm_interface
            return agent
    
    @pytest.fixture
    def sample_context(self):
        """Пример контекста планирования"""
        return TaskPlanningContext(
            server_info={"os": "ubuntu", "version": "20.04"},
            user_requirements="Установить и настроить nginx",
            constraints=["Не перезагружать сервер", "Использовать только apt"],
            available_tools=["apt", "systemctl", "curl"],
            previous_tasks=[],
            environment={"production": True}
        )
    
    def test_task_agent_initialization(self, mock_config, mock_task_master):
        """Тест инициализации Task Agent"""
        with patch('src.agents.task_agent.LLMInterfaceFactory.create_interface') as mock_factory:
            mock_interface = Mock()
            mock_interface.is_available.return_value = True
            mock_factory.return_value = mock_interface
            
            agent = TaskAgent(mock_config, mock_task_master)
            
            assert agent.config == mock_config
            assert agent.task_agent_config == mock_config.task_agent
            assert agent.task_master == mock_task_master
            assert agent.llm_interface == mock_interface
    
    def test_plan_task_success(self, task_agent, sample_context):
        """Тест успешного планирования задачи"""
        task_description = "Установить и настроить nginx на сервере"
        
        result = task_agent.plan_task(task_description, sample_context)
        
        assert result.success is True
        assert result.task is not None
        assert result.task.title == "Установить и настроить nginx на сервере"
        assert len(result.task.steps) > 0
        assert result.planning_duration is not None
        assert result.llm_usage is not None
    
    def test_plan_task_without_context(self, task_agent):
        """Тест планирования задачи без контекста"""
        task_description = "Установить Docker"
        
        result = task_agent.plan_task(task_description)
        
        assert result.success is True
        assert result.task is not None
        assert result.task.description == task_description
    
    def test_plan_task_llm_error(self, task_agent, sample_context):
        """Тест планирования при ошибке LLM"""
        task_agent.llm_interface.generate_response.return_value = LLMResponse(
            success=False,
            error="API error",
            duration=1.0
        )
        
        result = task_agent.plan_task("Test task", sample_context)
        
        assert result.success is False
        assert "Ошибка LLM" in result.error_message
        assert result.task is None
    
    def test_plan_task_invalid_json(self, task_agent, sample_context):
        """Тест планирования при невалидном JSON ответе"""
        task_agent.llm_interface.generate_response.return_value = LLMResponse(
            success=True,
            content="Invalid JSON response",
            usage={"total_tokens": 100},
            model="gpt-4",
            duration=1.0
        )
        
        result = task_agent.plan_task("Test task", sample_context)
        
        assert result.success is False
        assert "Не удалось извлечь шаги" in result.error_message
    
    def test_extract_task_title(self, task_agent):
        """Тест извлечения заголовка задачи"""
        # Обычный случай
        title = task_agent._extract_task_title("Установить nginx\nДополнительная информация")
        assert title == "Установить nginx"
        
        # Длинный заголовок
        long_description = "Очень длинное описание задачи которое должно быть обрезано до ста символов и заканчиваться многоточием"
        title = task_agent._extract_task_title(long_description)
        assert len(title) <= 100
        assert title.endswith("...")
        
        # Пустое описание
        title = task_agent._extract_task_title("")
        assert title == ""
    
    def test_build_planning_prompt(self, task_agent, sample_context):
        """Тест построения промта для планирования"""
        prompt = task_agent._build_planning_prompt("Test task", sample_context)
        
        assert "Test task" in prompt
        assert "JSON" in prompt
        assert "steps" in prompt
        assert "ubuntu" in prompt  # из контекста
        assert "apt" in prompt  # из available_tools контекста
    
    def test_parse_llm_response_valid(self, task_agent):
        """Тест парсинга валидного ответа LLM"""
        valid_response = '''
        {
            "steps": [
                {
                    "title": "Обновить систему",
                    "description": "Выполнить apt update",
                    "priority": "high",
                    "estimated_duration": 5,
                    "dependencies": []
                },
                {
                    "title": "Установить nginx",
                    "description": "Установить nginx через apt",
                    "priority": "high",
                    "estimated_duration": 10,
                    "dependencies": ["step_1"]
                }
            ]
        }
        '''
        
        steps = task_agent._parse_llm_response(valid_response, "test_task_id")
        
        assert len(steps) == 2
        assert steps[0].title == "Обновить систему"
        assert steps[0].priority == Priority.HIGH
        assert steps[0].estimated_duration == 5
        assert steps[1].dependencies == ["step_1"]
    
    def test_parse_llm_response_invalid_json(self, task_agent):
        """Тест парсинга невалидного JSON"""
        invalid_response = "Not a JSON response"
        
        steps = task_agent._parse_llm_response(invalid_response, "test_task_id")
        
        assert len(steps) == 0
    
    def test_parse_llm_response_missing_steps(self, task_agent):
        """Тест парсинга ответа без шагов"""
        response_without_steps = '{"other_data": "value"}'
        
        steps = task_agent._parse_llm_response(response_without_steps, "test_task_id")
        
        assert len(steps) == 0
    
    def test_validate_plan_valid(self, task_agent):
        """Тест валидации валидного плана"""
        task = Task(title="Test Task", description="Test Description")
        
        # Добавляем валидные шаги
        step1 = TaskStep(title="Step 1", step_id="step_1")
        step2 = TaskStep(title="Step 2", step_id="step_2", dependencies=["step_1"])
        
        task.add_step(step1)
        task.add_step(step2)
        
        result = task_agent._validate_plan(task)
        
        assert result["valid"] is True
        assert len(result["issues"]) == 0
        assert result["steps_count"] == 2
    
    def test_validate_plan_no_steps(self, task_agent):
        """Тест валидации плана без шагов"""
        task = Task(title="Test Task", description="Test Description")
        
        result = task_agent._validate_plan(task)
        
        assert result["valid"] is False
        assert "не содержит шагов" in result["issues"][0]
    
    def test_validate_plan_too_many_steps(self, task_agent):
        """Тест валидации плана со слишком большим количеством шагов"""
        task = Task(title="Test Task", description="Test Description")
        
        # Добавляем больше шагов чем разрешено
        for i in range(15):  # больше чем max_steps=10
            step = TaskStep(title=f"Step {i}", step_id=f"step_{i}")
            task.add_step(step)
        
        result = task_agent._validate_plan(task)
        
        assert result["valid"] is False
        assert "Слишком много шагов" in result["issues"][0]
    
    def test_validate_plan_cyclic_dependencies(self, task_agent):
        """Тест валидации плана с циклическими зависимостями"""
        task = Task(title="Test Task", description="Test Description")
        
        step1 = TaskStep(title="Step 1", step_id="step_1", dependencies=["step_2"])
        step2 = TaskStep(title="Step 2", step_id="step_2", dependencies=["step_1"])
        
        task.add_step(step1)
        task.add_step(step2)
        
        result = task_agent._validate_plan(task)
        
        assert result["valid"] is False
        assert "циклические зависимости" in result["issues"][0]
    
    def test_has_cyclic_dependencies(self, task_agent):
        """Тест проверки циклических зависимостей"""
        # Без циклов
        step1 = TaskStep(title="Step 1", step_id="step_1")
        step2 = TaskStep(title="Step 2", step_id="step_2", dependencies=["step_1"])
        step3 = TaskStep(title="Step 3", step_id="step_3", dependencies=["step_2"])
        
        assert task_agent._has_cyclic_dependencies([step1, step2, step3]) is False
        
        # С циклом
        step1_cyclic = TaskStep(title="Step 1", step_id="step_1", dependencies=["step_2"])
        step2_cyclic = TaskStep(title="Step 2", step_id="step_2", dependencies=["step_1"])
        
        assert task_agent._has_cyclic_dependencies([step1_cyclic, step2_cyclic]) is True
    
    def test_optimize_plan(self, task_agent):
        """Тест оптимизации плана"""
        task = Task(title="Test Task", description="Test Description")
        
        step1 = TaskStep(title="Step 1", step_id="step_1", estimated_duration=10)
        step2 = TaskStep(title="Step 2", step_id="step_2", estimated_duration=15, dependencies=["step_1"])
        
        task.add_step(step2)  # Добавляем в неправильном порядке
        task.add_step(step1)
        
        task_agent._optimize_plan(task)
        
        # Проверяем что шаги отсортированы правильно
        assert task.steps[0].step_id == "step_1"
        assert task.steps[1].step_id == "step_2"
        assert task.total_estimated_duration == 25
    
    def test_get_task_status(self, task_agent):
        """Тест получения статуса задачи"""
        task = Task(title="Test Task", description="Test Description")
        
        step1 = TaskStep(title="Step 1", step_id="step_1")
        step2 = TaskStep(title="Step 2", step_id="step_2")
        
        task.add_step(step1)
        task.add_step(step2)
        
        status = task_agent.get_task_status(task)
        
        assert status["task_id"] == task.task_id
        assert status["title"] == "Test Task"
        assert status["status"] == TaskStatus.PENDING.value
        assert len(status["steps"]) == 2
        assert status["progress"]["total_steps"] == 2
    
    def test_update_step_status(self, task_agent):
        """Тест обновления статуса шага"""
        task = Task(title="Test Task", description="Test Description")
        
        step = TaskStep(title="Test Step", step_id="test_step")
        task.add_step(step)
        
        # Обновляем статус
        result = task_agent.update_step_status(task, "test_step", StepStatus.EXECUTING)
        
        assert result is True
        assert step.status == StepStatus.EXECUTING
        assert step.started_at is not None
        
        # Обновляем с ошибкой
        result = task_agent.update_step_status(task, "test_step", StepStatus.FAILED, error_count=1)
        
        assert result is True
        assert step.status == StepStatus.FAILED
        assert step.error_count == 1
    
    def test_update_step_status_invalid_step(self, task_agent):
        """Тест обновления статуса несуществующего шага"""
        task = Task(title="Test Task", description="Test Description")
        
        result = task_agent.update_step_status(task, "invalid_step", StepStatus.EXECUTING)
        
        assert result is False
    
    def test_improve_prompt_with_taskmaster_success(self, task_agent, sample_context):
        """Тест улучшения промта через Task Master"""
        prompt = "Test prompt"
        
        result = task_agent._improve_prompt_with_taskmaster(prompt, sample_context)
        
        assert result.success is True
        assert "improved_prompt" in result.data
    
    def test_improve_prompt_with_taskmaster_failure(self, task_agent, sample_context):
        """Тест неудачного улучшения промта через Task Master"""
        task_agent.task_master.improve_prompt.return_value = TaskMasterResult(
            success=False,
            error="Task Master error"
        )
        
        prompt = "Test prompt"
        result = task_agent._improve_prompt_with_taskmaster(prompt, sample_context)
        
        assert result.success is False
        assert "Task Master error" in result.error
    
    def test_improve_prompt_without_taskmaster(self, task_agent, sample_context):
        """Тест улучшения промта без Task Master"""
        task_agent.task_master = None
        
        prompt = "Test prompt"
        result = task_agent._improve_prompt_with_taskmaster(prompt, sample_context)
        
        assert result.success is False
        assert "не доступен" in result.error


class TestTaskPlanningContext:
    """Тесты для TaskPlanningContext"""
    
    def test_task_planning_context_creation(self):
        """Тест создания контекста планирования"""
        context = TaskPlanningContext(
            server_info={"os": "ubuntu"},
            user_requirements="Install nginx",
            constraints=["No reboot"],
            available_tools=["apt"],
            previous_tasks=[],
            environment={"prod": True}
        )
        
        assert context.server_info["os"] == "ubuntu"
        assert context.user_requirements == "Install nginx"
        assert "No reboot" in context.constraints
        assert "apt" in context.available_tools
        assert context.environment["prod"] is True
