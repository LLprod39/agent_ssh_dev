"""
Тесты для Execution Model
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from src.models.execution_model import (
    ExecutionModel, ExecutionStatus, CommandResult, 
    SubtaskExecutionResult, ExecutionContext
)
from src.agents.subtask_agent import Subtask
from src.config.agent_config import AgentConfig, ExecutorConfig, LLMConfig


class MockSSHConnection:
    """Мок SSH соединения для тестов"""
    
    def __init__(self, command_responses: Dict[str, tuple] = None):
        self.connected = True
        self.command_responses = command_responses or {}
        self.executed_commands = []
    
    def execute_command(self, command: str, timeout: int = 30):
        """Мок выполнение команды"""
        self.executed_commands.append(command)
        
        # Возвращаем предопределенный ответ или стандартный
        if command in self.command_responses:
            return self.command_responses[command]
        
        # Стандартные ответы для тестов
        if "apt update" in command:
            return "Обновление завершено", "", 0
        elif "apt install" in command:
            return "Установка завершена", "", 0
        elif "systemctl start" in command:
            return "", "", 0
        elif "systemctl is-active" in command:
            return "active", "", 0
        elif "curl -I" in command:
            return "HTTP/1.1 200 OK", "", 0
        else:
            return f"Команда '{command}' выполнена", "", 0
    
    def close(self):
        self.connected = False


def create_test_config() -> AgentConfig:
    """Создание тестовой конфигурации"""
    return AgentConfig(
        executor=ExecutorConfig(
            max_retries_per_command=2,
            auto_correction_enabled=True,
            dry_run_mode=False,
            command_timeout=10
        ),
        llm=LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
    )


def create_test_subtask() -> Subtask:
    """Создание тестовой подзадачи"""
    return Subtask(
        subtask_id="test_subtask_1",
        title="Тестовая подзадача",
        description="Тестовая подзадача для проверки",
        commands=[
            "sudo apt update",
            "sudo apt install -y test-package"
        ],
        health_checks=[
            "systemctl is-active test-service",
            "curl -I http://localhost"
        ],
        expected_output="Тестовая подзадача выполнена",
        rollback_commands=[
            "sudo apt remove -y test-package"
        ],
        timeout=30
    )


class TestExecutionModel:
    """Тесты для ExecutionModel"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.config = create_test_config()
        self.ssh_connector = Mock()
        self.execution_model = ExecutionModel(self.config, self.ssh_connector)
        self.subtask = create_test_subtask()
    
    def test_initialization(self):
        """Тест инициализации ExecutionModel"""
        assert self.execution_model.config == self.config
        assert self.execution_model.executor_config == self.config.executor
        assert self.execution_model.ssh_connector == self.ssh_connector
        assert self.execution_model.execution_stats["total_commands"] == 0
    
    def test_execute_single_command_success(self):
        """Тест успешного выполнения одной команды"""
        mock_ssh = MockSSHConnection()
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        result = self.execution_model._execute_single_command("sudo apt update", context)
        
        assert result.success is True
        assert result.exit_code == 0
        assert result.command == "sudo apt update"
        assert result.status == ExecutionStatus.COMPLETED
        assert "Обновление завершено" in result.stdout
    
    def test_execute_single_command_failure(self):
        """Тест неудачного выполнения команды"""
        mock_ssh = MockSSHConnection({
            "sudo apt install -y bad-package": ("", "Package not found", 1)
        })
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        result = self.execution_model._execute_single_command("sudo apt install -y bad-package", context)
        
        assert result.success is False
        assert result.exit_code == 1
        assert result.status == ExecutionStatus.FAILED
        assert "Package not found" in result.stderr
    
    def test_simulate_command_execution_dry_run(self):
        """Тест симуляции выполнения команды в dry-run режиме"""
        self.execution_model.executor_config.dry_run_mode = True
        
        result = self.execution_model._simulate_command_execution("sudo apt update")
        
        assert result.success is True
        assert result.exit_code == 0
        assert "[DRY-RUN]" in result.stdout
        assert result.metadata["dry_run"] is True
    
    def test_simulate_command_execution_dangerous_command(self):
        """Тест симуляции опасной команды в dry-run режиме"""
        self.execution_model.executor_config.dry_run_mode = True
        
        result = self.execution_model._simulate_command_execution("rm -rf /")
        
        assert result.success is False
        assert result.exit_code == 1
        assert "[DRY-RUN]" in result.stderr
    
    def test_execute_commands_sequence(self):
        """Тест выполнения последовательности команд"""
        mock_ssh = MockSSHConnection()
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        commands = ["sudo apt update", "sudo apt install -y test-package"]
        results = self.execution_model._execute_commands(commands, context)
        
        assert len(results) == 2
        assert all(result.success for result in results)
        assert len(mock_ssh.executed_commands) == 2
        assert mock_ssh.executed_commands == commands
    
    def test_execute_health_checks(self):
        """Тест выполнения health-check команд"""
        mock_ssh = MockSSHConnection()
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        health_checks = ["systemctl is-active test-service", "curl -I http://localhost"]
        results = self.execution_model._execute_health_checks(health_checks, context)
        
        assert len(results) == 2
        assert all(result.success for result in results)
        assert len(mock_ssh.executed_commands) == 2
    
    def test_autocorrection_permission_denied(self):
        """Тест автокоррекции для ошибки 'permission denied'"""
        mock_ssh = MockSSHConnection({
            "apt update": ("", "Permission denied", 1),
            "sudo apt update": ("Обновление завершено", "", 0)
        })
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        # Создаем неудачный результат
        failed_result = CommandResult(
            command="apt update",
            success=False,
            exit_code=1,
            stderr="Permission denied",
            status=ExecutionStatus.FAILED
        )
        
        # Применяем автокоррекцию
        corrected_results = self.execution_model._apply_autocorrection([failed_result], context)
        
        assert corrected_results is not None
        assert len(corrected_results) == 1
        assert corrected_results[0].success is True
        assert corrected_results[0].command == "sudo apt update"
        assert corrected_results[0].metadata["autocorrected"] is True
    
    def test_autocorrection_package_not_found(self):
        """Тест автокоррекции для ошибки 'package not found'"""
        mock_ssh = MockSSHConnection({
            "sudo apt install -y missing-package": ("", "Package not found", 1),
            "sudo apt update && sudo apt install -y missing-package": ("Установка завершена", "", 0)
        })
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        failed_result = CommandResult(
            command="sudo apt install -y missing-package",
            success=False,
            exit_code=1,
            stderr="Package not found",
            status=ExecutionStatus.FAILED
        )
        
        corrected_results = self.execution_model._apply_autocorrection([failed_result], context)
        
        assert corrected_results is not None
        assert corrected_results[0].success is True
        assert "apt update &&" in corrected_results[0].command
    
    def test_execute_subtask_success(self):
        """Тест успешного выполнения подзадачи"""
        mock_ssh = MockSSHConnection()
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        result = self.execution_model.execute_subtask(context)
        
        assert result.success is True
        assert result.subtask_id == self.subtask.subtask_id
        assert len(result.commands_results) == 2
        assert len(result.health_check_results) == 2
        assert result.error_count == 0
        assert result.autocorrection_applied is False
        assert result.rollback_executed is False
    
    def test_execute_subtask_with_failures(self):
        """Тест выполнения подзадачи с ошибками"""
        mock_ssh = MockSSHConnection({
            "sudo apt install -y test-package": ("", "Package not found", 1)
        })
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        result = self.execution_model.execute_subtask(context)
        
        assert result.success is False
        assert result.error_count > 0
        assert any(not cmd.success for cmd in result.commands_results)
    
    def test_execute_subtask_dry_run_mode(self):
        """Тест выполнения подзадачи в dry-run режиме"""
        self.execution_model.executor_config.dry_run_mode = True
        mock_ssh = MockSSHConnection()
        context = ExecutionContext(
            subtask=self.subtask,
            ssh_connection=mock_ssh,
            server_info={"os": "ubuntu"},
            environment={}
        )
        
        result = self.execution_model.execute_subtask(context)
        
        assert result.success is True
        assert len(mock_ssh.executed_commands) == 0  # Команды не выполнялись реально
        assert all("[DRY-RUN]" in cmd.stdout for cmd in result.commands_results if cmd.stdout)
    
    def test_dangerous_command_detection(self):
        """Тест обнаружения опасных команд"""
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda1",
            "chmod 777 /",
            "halt",
            "reboot"
        ]
        
        for command in dangerous_commands:
            assert self.execution_model._is_dangerous_command(command) is True
        
        safe_commands = [
            "ls -la",
            "cat /etc/passwd",
            "ps aux",
            "df -h",
            "sudo apt update"
        ]
        
        for command in safe_commands:
            assert self.execution_model._is_dangerous_command(command) is False
    
    def test_critical_command_detection(self):
        """Тест обнаружения критических команд"""
        critical_commands = [
            "systemctl start nginx",
            "systemctl enable docker",
            "service apache2 start",
            "docker start container",
            "nginx -t"
        ]
        
        for command in critical_commands:
            assert self.execution_model._is_critical_command(command) is True
        
        non_critical_commands = [
            "ls -la",
            "cat /etc/passwd",
            "ps aux",
            "df -h"
        ]
        
        for command in non_critical_commands:
            assert self.execution_model._is_critical_command(command) is False
    
    def test_execution_stats_update(self):
        """Тест обновления статистики выполнения"""
        initial_stats = self.execution_model.get_execution_stats()
        assert initial_stats["total_commands"] == 0
        
        # Создаем результаты команд
        successful_result = CommandResult(
            command="test command",
            success=True,
            duration=1.0
        )
        failed_result = CommandResult(
            command="failed command",
            success=False,
            duration=0.5
        )
        
        # Обновляем статистику
        self.execution_model._update_execution_stats(
            [successful_result, failed_result], 
            [], 
            1.5
        )
        
        stats = self.execution_model.get_execution_stats()
        assert stats["total_commands"] == 2
        assert stats["successful_commands"] == 1
        assert stats["failed_commands"] == 1
        assert stats["total_duration"] == 1.5
        assert stats["success_rate"] == 50.0
    
    def test_reset_stats(self):
        """Тест сброса статистики"""
        # Добавляем некоторую статистику
        self.execution_model.execution_stats["total_commands"] = 10
        self.execution_model.execution_stats["successful_commands"] = 8
        
        # Сбрасываем статистику
        self.execution_model.reset_stats()
        
        stats = self.execution_model.get_execution_stats()
        assert stats["total_commands"] == 0
        assert stats["successful_commands"] == 0
        assert stats["failed_commands"] == 0


class TestCommandResult:
    """Тесты для CommandResult"""
    
    def test_command_result_creation(self):
        """Тест создания CommandResult"""
        result = CommandResult(
            command="test command",
            success=True,
            exit_code=0,
            stdout="test output",
            stderr="",
            duration=1.5
        )
        
        assert result.command == "test command"
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "test output"
        assert result.stderr == ""
        assert result.duration == 1.5
        assert result.status == ExecutionStatus.PENDING
    
    def test_command_result_to_dict(self):
        """Тест преобразования CommandResult в словарь"""
        result = CommandResult(
            command="test command",
            success=True,
            exit_code=0,
            stdout="test output"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["command"] == "test command"
        assert result_dict["success"] is True
        assert result_dict["exit_code"] == 0
        assert result_dict["stdout"] == "test output"
        assert result_dict["status"] == ExecutionStatus.PENDING.value


class TestSubtaskExecutionResult:
    """Тесты для SubtaskExecutionResult"""
    
    def test_subtask_execution_result_creation(self):
        """Тест создания SubtaskExecutionResult"""
        command_result = CommandResult(
            command="test command",
            success=True
        )
        
        result = SubtaskExecutionResult(
            subtask_id="test_subtask",
            success=True,
            commands_results=[command_result],
            total_duration=2.5,
            error_count=0
        )
        
        assert result.subtask_id == "test_subtask"
        assert result.success is True
        assert len(result.commands_results) == 1
        assert result.total_duration == 2.5
        assert result.error_count == 0
    
    def test_subtask_execution_result_to_dict(self):
        """Тест преобразования SubtaskExecutionResult в словарь"""
        command_result = CommandResult(
            command="test command",
            success=True
        )
        
        result = SubtaskExecutionResult(
            subtask_id="test_subtask",
            success=True,
            commands_results=[command_result]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["subtask_id"] == "test_subtask"
        assert result_dict["success"] is True
        assert len(result_dict["commands_results"]) == 1
        assert result_dict["commands_results"][0]["command"] == "test command"


if __name__ == "__main__":
    pytest.main([__file__])
