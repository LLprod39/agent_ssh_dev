"""
Тесты для TaskMasterIntegration
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from src.agents.task_master_integration import (
    TaskMasterIntegration,
    TaskMasterResult,
    ParsedPRD,
    GeneratedTask
)
from src.config.agent_config import TaskmasterConfig


class TestTaskMasterIntegration:
    """Тесты для TaskMasterIntegration"""
    
    @pytest.fixture
    def config(self):
        """Конфигурация для тестов"""
        return TaskmasterConfig(
            enabled=True,
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
    
    @pytest.fixture
    def disabled_config(self):
        """Отключенная конфигурация для тестов"""
        return TaskmasterConfig(
            enabled=False,
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
    
    @pytest.fixture
    def temp_project_root(self):
        """Временная директория проекта"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def integration(self, config, temp_project_root):
        """Экземпляр TaskMasterIntegration для тестов"""
        return TaskMasterIntegration(config, temp_project_root)
    
    def test_init_with_enabled_config(self, config, temp_project_root):
        """Тест инициализации с включенной конфигурацией"""
        with patch.object(TaskMasterIntegration, '_check_taskmaster_installation', return_value=True):
            integration = TaskMasterIntegration(config, temp_project_root)
            assert integration.config == config
            assert integration.project_root == temp_project_root
            assert integration.taskmaster_dir == temp_project_root / ".taskmaster"
    
    def test_init_with_disabled_config(self, disabled_config, temp_project_root):
        """Тест инициализации с отключенной конфигурацией"""
        integration = TaskMasterIntegration(disabled_config, temp_project_root)
        assert integration.config == disabled_config
        assert not integration.config.enabled
    
    @patch('subprocess.run')
    def test_check_taskmaster_installation_success(self, mock_run, integration):
        """Тест успешной проверки установки Task Master"""
        mock_run.return_value = Mock(returncode=0, stdout="1.0.0")
        
        result = integration._check_taskmaster_installation()
        assert result is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_check_taskmaster_installation_failure(self, mock_run, integration):
        """Тест неудачной проверки установки Task Master"""
        mock_run.return_value = Mock(returncode=1, stderr="Command not found")
        
        with patch.object(integration, '_install_taskmaster', return_value=False):
            result = integration._check_taskmaster_installation()
            assert result is False
    
    @patch('subprocess.run')
    def test_install_taskmaster_success(self, mock_run, integration):
        """Тест успешной установки Task Master"""
        mock_run.return_value = Mock(returncode=0, stdout="Installed successfully")
        
        result = integration._install_taskmaster()
        assert result is True
        mock_run.assert_called_once_with(
            ["npm", "install", "-g", "task-master-ai"],
            capture_output=True,
            text=True,
            timeout=300
        )
    
    @patch('subprocess.run')
    def test_install_taskmaster_failure(self, mock_run, integration):
        """Тест неудачной установки Task Master"""
        mock_run.return_value = Mock(returncode=1, stderr="Installation failed")
        
        result = integration._install_taskmaster()
        assert result is False
    
    @patch('subprocess.run')
    def test_initialize_taskmaster_success(self, mock_run, integration):
        """Тест успешной инициализации Task Master"""
        mock_run.return_value = Mock(returncode=0, stdout="Initialized successfully")
        
        result = integration._initialize_taskmaster()
        assert result is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_improve_prompt_success(self, mock_run, integration):
        """Тест успешного улучшения промта"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"improved_prompt": "Улучшенный промт"})
        )
        
        result = integration.improve_prompt("Исходный промт")
        
        assert result.success is True
        assert result.data["improved_prompt"] == "Улучшенный промт"
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_improve_prompt_with_context(self, mock_run, integration):
        """Тест улучшения промта с контекстом"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"improved_prompt": "Улучшенный промт с контекстом"})
        )
        
        context = {"task_type": "planning", "complexity": "high"}
        result = integration.improve_prompt("Исходный промт", context)
        
        assert result.success is True
        assert result.data["improved_prompt"] == "Улучшенный промт с контекстом"
        mock_run.assert_called_once()
    
    def test_improve_prompt_disabled(self, disabled_config, temp_project_root):
        """Тест улучшения промта при отключенном Task Master"""
        integration = TaskMasterIntegration(disabled_config, temp_project_root)
        
        result = integration.improve_prompt("Исходный промт")
        
        assert result.success is True
        assert result.data["improved_prompt"] == "Исходный промт"
        assert result.data["original_prompt"] == "Исходный промт"
    
    @patch('subprocess.run')
    def test_improve_prompt_failure(self, mock_run, integration):
        """Тест неудачного улучшения промта"""
        mock_run.return_value = Mock(returncode=1, stderr="Error occurred")
        
        result = integration.improve_prompt("Исходный промт")
        
        assert result.success is False
        assert result.error == "Error occurred"
    
    @patch('subprocess.run')
    def test_parse_prd_success(self, mock_run, integration):
        """Тест успешного парсинга PRD"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"parsed_prd": {"overview": "Test overview"}})
        )
        
        # Создаем временный PRD файл
        prd_file = integration.taskmaster_dir / "docs" / "prd.txt"
        prd_file.parent.mkdir(parents=True, exist_ok=True)
        prd_file.write_text("# Test PRD\nThis is a test PRD document.")
        
        result = integration.parse_prd()
        
        assert result.success is True
        assert "parsed_prd" in result.data
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_parse_prd_file_not_found(self, integration):
        """Тест парсинга PRD когда файл не найден"""
        result = integration.parse_prd("/nonexistent/path.txt")
        
        assert result.success is False
        assert "не найден" in result.error
    
    @patch('subprocess.run')
    def test_generate_tasks_from_prd_success(self, mock_run, integration):
        """Тест успешной генерации задач из PRD"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"tasks": [{"id": "task1", "title": "Test Task"}]})
        )
        
        # Создаем временный PRD файл
        prd_file = integration.taskmaster_dir / "docs" / "prd.txt"
        prd_file.parent.mkdir(parents=True, exist_ok=True)
        prd_file.write_text("# Test PRD\nThis is a test PRD document.")
        
        result = integration.generate_tasks_from_prd(num_tasks=5)
        
        assert result.success is True
        assert "tasks" in result.data
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_validate_prompt_success(self, mock_run, integration):
        """Тест успешной валидации промта"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"valid": True, "score": 0.9})
        )
        
        result = integration.validate_prompt("Test prompt", "planning")
        
        assert result.success is True
        assert result.data["valid"] is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_format_prompt_success(self, mock_run, integration):
        """Тест успешного форматирования промта"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"formatted_prompt": "Formatted prompt"})
        )
        
        result = integration.format_prompt("Test prompt", "structured")
        
        assert result.success is True
        assert result.data["formatted_prompt"] == "Formatted prompt"
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_get_taskmaster_status_installed(self, mock_run, integration):
        """Тест получения статуса Task Master (установлен)"""
        mock_run.return_value = Mock(returncode=0, stdout="1.0.0")
        
        # Создаем необходимые файлы
        integration.taskmaster_dir.mkdir(parents=True, exist_ok=True)
        (integration.taskmaster_dir / "config.json").write_text("{}")
        (integration.taskmaster_dir / "docs").mkdir(exist_ok=True)
        (integration.taskmaster_dir / "docs" / "prd.txt").write_text("# Test PRD")
        
        status = integration.get_taskmaster_status()
        
        assert status["enabled"] is True
        assert status["installation_status"] == "installed"
        assert status["version"] == "1.0.0"
        assert status["taskmaster_dir_exists"] is True
        assert status["config_file_exists"] is True
        assert status["prd_file_exists"] is True
    
    @patch('subprocess.run')
    def test_get_taskmaster_status_not_installed(self, mock_run, integration):
        """Тест получения статуса Task Master (не установлен)"""
        mock_run.return_value = Mock(returncode=1, stderr="Command not found")
        
        status = integration.get_taskmaster_status()
        
        assert status["enabled"] is True
        assert status["installation_status"] == "not_installed"
        assert status["taskmaster_dir_exists"] is False
    
    def test_create_custom_prd_success(self, integration):
        """Тест успешного создания кастомного PRD"""
        content = "# Custom PRD\nThis is a custom PRD document."
        
        result = integration.create_custom_prd(content, "custom.txt")
        
        assert result is True
        
        # Проверяем, что файл создан
        prd_file = integration.taskmaster_dir / "docs" / "custom.txt"
        assert prd_file.exists()
        assert prd_file.read_text() == content
    
    def test_create_custom_prd_failure(self, integration):
        """Тест неудачного создания кастомного PRD"""
        # Создаем файл как директорию, чтобы вызвать ошибку
        integration.taskmaster_dir.mkdir(parents=True, exist_ok=True)
        (integration.taskmaster_dir / "docs").mkdir(exist_ok=True)
        (integration.taskmaster_dir / "docs" / "custom.txt").mkdir(exist_ok=True)
        
        result = integration.create_custom_prd("content", "custom.txt")
        
        assert result is False


class TestTaskMasterResult:
    """Тесты для TaskMasterResult"""
    
    def test_success_result(self):
        """Тест успешного результата"""
        result = TaskMasterResult(
            success=True,
            data={"key": "value"},
            raw_output="raw output"
        )
        
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.raw_output == "raw output"
    
    def test_error_result(self):
        """Тест результата с ошибкой"""
        result = TaskMasterResult(
            success=False,
            error="Test error"
        )
        
        assert result.success is False
        assert result.error == "Test error"
        assert result.data is None
        assert result.raw_output is None


class TestParsedPRD:
    """Тесты для ParsedPRD"""
    
    def test_parsed_prd_creation(self):
        """Тест создания ParsedPRD"""
        prd = ParsedPRD(
            overview="Test overview",
            core_features=[{"name": "Feature 1", "description": "Description 1"}],
            user_experience={"personas": ["User 1"]},
            technical_architecture={"components": ["Component 1"]},
            development_roadmap=[{"phase": "Phase 1", "tasks": ["Task 1"]}],
            risks_and_mitigations=[{"risk": "Risk 1", "mitigation": "Mitigation 1"}],
            raw_content="Raw PRD content"
        )
        
        assert prd.overview == "Test overview"
        assert len(prd.core_features) == 1
        assert prd.core_features[0]["name"] == "Feature 1"
        assert prd.user_experience["personas"] == ["User 1"]
        assert prd.technical_architecture["components"] == ["Component 1"]
        assert len(prd.development_roadmap) == 1
        assert prd.development_roadmap[0]["phase"] == "Phase 1"
        assert len(prd.risks_and_mitigations) == 1
        assert prd.risks_and_mitigations[0]["risk"] == "Risk 1"
        assert prd.raw_content == "Raw PRD content"


class TestGeneratedTask:
    """Тесты для GeneratedTask"""
    
    def test_generated_task_creation(self):
        """Тест создания GeneratedTask"""
        task = GeneratedTask(
            task_id="task_1",
            title="Test Task",
            description="Test task description",
            priority="high",
            estimated_effort="2 days",
            dependencies=["task_0"],
            acceptance_criteria=["Criterion 1", "Criterion 2"],
            subtasks=[{"id": "subtask_1", "title": "Subtask 1"}]
        )
        
        assert task.task_id == "task_1"
        assert task.title == "Test Task"
        assert task.description == "Test task description"
        assert task.priority == "high"
        assert task.estimated_effort == "2 days"
        assert task.dependencies == ["task_0"]
        assert len(task.acceptance_criteria) == 2
        assert task.acceptance_criteria[0] == "Criterion 1"
        assert len(task.subtasks) == 1
        assert task.subtasks[0]["id"] == "subtask_1"
