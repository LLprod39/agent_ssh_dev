"""
Тесты для Planning Model
"""
import pytest
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.models.planning_model import (
    Task, TaskStep, TaskStatus, StepStatus, Priority,
    PlanningResult, StepExecutionResult, TaskExecutionResult
)


class TestTaskStep:
    """Тесты для TaskStep"""
    
    def test_task_step_creation(self):
        """Тест создания шага задачи"""
        step = TaskStep(
            title="Test Step",
            description="Test Description",
            priority=Priority.HIGH,
            estimated_duration=30
        )
        
        assert step.title == "Test Step"
        assert step.description == "Test Description"
        assert step.status == StepStatus.PENDING
        assert step.priority == Priority.HIGH
        assert step.estimated_duration == 30
        assert step.error_count == 0
        assert step.max_errors == 4
        assert step.step_id is not None
        assert step.created_at is not None
    
    def test_task_step_default_values(self):
        """Тест значений по умолчанию"""
        step = TaskStep()
        
        assert step.title == ""
        assert step.description == ""
        assert step.status == StepStatus.PENDING
        assert step.priority == Priority.MEDIUM
        assert step.estimated_duration is None
        assert step.dependencies == []
        assert step.subtasks == []
        assert step.error_count == 0
        assert step.max_errors == 4
        assert step.started_at is None
        assert step.completed_at is None
        assert step.metadata == {}
    
    def test_is_ready_to_execute_no_dependencies(self):
        """Тест готовности к выполнению без зависимостей"""
        step = TaskStep(title="Test Step")
        
        assert step.is_ready_to_execute([]) is True
        assert step.is_ready_to_execute(["other_step"]) is True
    
    def test_is_ready_to_execute_with_dependencies(self):
        """Тест готовности к выполнению с зависимостями"""
        step = TaskStep(
            title="Test Step",
            dependencies=["step_1", "step_2"]
        )
        
        # Не все зависимости выполнены
        assert step.is_ready_to_execute(["step_1"]) is False
        assert step.is_ready_to_execute([]) is False
        
        # Все зависимости выполнены
        assert step.is_ready_to_execute(["step_1", "step_2"]) is True
        assert step.is_ready_to_execute(["step_1", "step_2", "step_3"]) is True
    
    def test_can_retry(self):
        """Тест возможности повторной попытки"""
        step = TaskStep(title="Test Step")
        
        # Нет ошибок
        assert step.can_retry() is True
        
        # Несколько ошибок
        step.error_count = 2
        assert step.can_retry() is True
        
        # Максимальное количество ошибок
        step.error_count = 4
        assert step.can_retry() is False
        
        # Превышение максимального количества ошибок
        step.error_count = 5
        assert step.can_retry() is False
    
    def test_mark_started(self):
        """Тест отметки начала выполнения"""
        step = TaskStep(title="Test Step")
        start_time = datetime.now()
        
        step.mark_started()
        
        assert step.status == StepStatus.EXECUTING
        assert step.started_at is not None
        assert step.started_at >= start_time
    
    def test_mark_completed(self):
        """Тест отметки завершения"""
        step = TaskStep(title="Test Step")
        step.mark_started()
        completion_time = datetime.now()
        
        step.mark_completed()
        
        assert step.status == StepStatus.COMPLETED
        assert step.completed_at is not None
        assert step.completed_at >= completion_time
    
    def test_mark_failed(self):
        """Тест отметки неудачи"""
        step = TaskStep(title="Test Step")
        initial_error_count = step.error_count
        
        step.mark_failed()
        
        assert step.status == StepStatus.FAILED
        assert step.error_count == initial_error_count + 1
    
    def test_add_subtask(self):
        """Тест добавления подзадачи"""
        step = TaskStep(title="Test Step")
        subtask = {
            "subtask_id": "subtask_1",
            "title": "Subtask Title",
            "description": "Subtask Description"
        }
        
        step.add_subtask(subtask)
        
        assert len(step.subtasks) == 1
        assert step.subtasks[0] == subtask
    
    def test_get_duration_not_started(self):
        """Тест получения длительности для не начатого шага"""
        step = TaskStep(title="Test Step")
        
        duration = step.get_duration()
        assert duration is None
    
    def test_get_duration_not_completed(self):
        """Тест получения длительности для не завершенного шага"""
        step = TaskStep(title="Test Step")
        step.mark_started()
        
        duration = step.get_duration()
        assert duration is None
    
    def test_get_duration_completed(self):
        """Тест получения длительности для завершенного шага"""
        step = TaskStep(title="Test Step")
        step.mark_started()
        
        # Имитируем выполнение в течение 2 минут
        step.started_at = datetime.now() - timedelta(minutes=2)
        step.mark_completed()
        
        duration = step.get_duration()
        assert duration is not None
        assert 1.9 <= duration <= 2.1  # Учитываем погрешность


class TestTask:
    """Тесты для Task"""
    
    def test_task_creation(self):
        """Тест создания задачи"""
        task = Task(
            title="Test Task",
            description="Test Description",
            priority=Priority.HIGH
        )
        
        assert task.title == "Test Task"
        assert task.description == "Test Description"
        assert task.status == TaskStatus.PENDING
        assert task.priority == Priority.HIGH
        assert task.steps == []
        assert task.task_id is not None
        assert task.created_at is not None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.total_estimated_duration is None
        assert task.metadata == {}
        assert task.context == {}
    
    def test_task_default_values(self):
        """Тест значений по умолчанию"""
        task = Task()
        
        assert task.title == ""
        assert task.description == ""
        assert task.status == TaskStatus.PENDING
        assert task.priority == Priority.MEDIUM
        assert task.steps == []
        assert task.started_at is None
        assert task.completed_at is None
        assert task.total_estimated_duration is None
        assert task.metadata == {}
        assert task.context == {}
    
    def test_add_step(self):
        """Тест добавления шага"""
        task = Task(title="Test Task")
        step = TaskStep(title="Test Step")
        
        step_id = task.add_step(step)
        
        assert step_id == step.step_id
        assert len(task.steps) == 1
        assert task.steps[0] == step
    
    def test_get_step_existing(self):
        """Тест получения существующего шага"""
        task = Task(title="Test Task")
        step = TaskStep(title="Test Step")
        task.add_step(step)
        
        retrieved_step = task.get_step(step.step_id)
        
        assert retrieved_step == step
    
    def test_get_step_nonexistent(self):
        """Тест получения несуществующего шага"""
        task = Task(title="Test Task")
        
        retrieved_step = task.get_step("nonexistent_id")
        
        assert retrieved_step is None
    
    def test_get_pending_steps(self):
        """Тест получения ожидающих шагов"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.PENDING)
        step2 = TaskStep(title="Step 2", status=StepStatus.EXECUTING)
        step3 = TaskStep(title="Step 3", status=StepStatus.PENDING)
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        
        pending_steps = task.get_pending_steps()
        
        assert len(pending_steps) == 2
        assert step1 in pending_steps
        assert step3 in pending_steps
        assert step2 not in pending_steps
    
    def test_get_ready_steps_no_dependencies(self):
        """Тест получения готовых шагов без зависимостей"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.PENDING)
        step2 = TaskStep(title="Step 2", status=StepStatus.PENDING)
        
        task.add_step(step1)
        task.add_step(step2)
        
        ready_steps = task.get_ready_steps()
        
        assert len(ready_steps) == 2
        assert step1 in ready_steps
        assert step2 in ready_steps
    
    def test_get_ready_steps_with_dependencies(self):
        """Тест получения готовых шагов с зависимостями"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", step_id="step_1", status=StepStatus.COMPLETED)
        step2 = TaskStep(title="Step 2", step_id="step_2", status=StepStatus.PENDING, dependencies=["step_1"])
        step3 = TaskStep(title="Step 3", step_id="step_3", status=StepStatus.PENDING, dependencies=["step_2"])
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        
        ready_steps = task.get_ready_steps()
        
        assert len(ready_steps) == 1
        assert step2 in ready_steps
        assert step3 not in ready_steps
    
    def test_get_failed_steps(self):
        """Тест получения неудачных шагов"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.FAILED)
        step2 = TaskStep(title="Step 2", status=StepStatus.COMPLETED)
        step3 = TaskStep(title="Step 3", status=StepStatus.FAILED)
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        
        failed_steps = task.get_failed_steps()
        
        assert len(failed_steps) == 2
        assert step1 in failed_steps
        assert step3 in failed_steps
        assert step2 not in failed_steps
    
    def test_get_completed_steps(self):
        """Тест получения завершенных шагов"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.COMPLETED)
        step2 = TaskStep(title="Step 2", status=StepStatus.PENDING)
        step3 = TaskStep(title="Step 3", status=StepStatus.COMPLETED)
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        
        completed_steps = task.get_completed_steps()
        
        assert len(completed_steps) == 2
        assert step1 in completed_steps
        assert step3 in completed_steps
        assert step2 not in completed_steps
    
    def test_is_completed_all_completed(self):
        """Тест проверки завершения - все шаги завершены"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.COMPLETED)
        step2 = TaskStep(title="Step 2", status=StepStatus.COMPLETED)
        step3 = TaskStep(title="Step 3", status=StepStatus.SKIPPED)
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        
        assert task.is_completed() is True
    
    def test_is_completed_some_pending(self):
        """Тест проверки завершения - некоторые шаги ожидают"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.COMPLETED)
        step2 = TaskStep(title="Step 2", status=StepStatus.PENDING)
        step3 = TaskStep(title="Step 3", status=StepStatus.COMPLETED)
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        
        assert task.is_completed() is False
    
    def test_is_failed_no_retries(self):
        """Тест проверки неудачи - нет возможности повтора"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.FAILED, error_count=5, max_errors=4)
        step2 = TaskStep(title="Step 2", status=StepStatus.COMPLETED)
        
        task.add_step(step1)
        task.add_step(step2)
        
        assert task.is_failed() is True
    
    def test_is_failed_can_retry(self):
        """Тест проверки неудачи - есть возможность повтора"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.FAILED, error_count=2, max_errors=4)
        step2 = TaskStep(title="Step 2", status=StepStatus.COMPLETED)
        
        task.add_step(step1)
        task.add_step(step2)
        
        assert task.is_failed() is False
    
    def test_get_progress(self):
        """Тест получения прогресса"""
        task = Task(title="Test Task")
        
        step1 = TaskStep(title="Step 1", status=StepStatus.COMPLETED)
        step2 = TaskStep(title="Step 2", status=StepStatus.PENDING)
        step3 = TaskStep(title="Step 3", status=StepStatus.FAILED)
        step4 = TaskStep(title="Step 4", status=StepStatus.COMPLETED)
        
        task.add_step(step1)
        task.add_step(step2)
        task.add_step(step3)
        task.add_step(step4)
        
        progress = task.get_progress()
        
        assert progress["total_steps"] == 4
        assert progress["completed_steps"] == 2
        assert progress["failed_steps"] == 1
        assert progress["pending_steps"] == 1
        assert progress["progress_percentage"] == 50.0
        assert progress["is_completed"] is False
        assert progress["is_failed"] is False
    
    def test_get_progress_empty_task(self):
        """Тест получения прогресса для пустой задачи"""
        task = Task(title="Test Task")
        
        progress = task.get_progress()
        
        assert progress["total_steps"] == 0
        assert progress["completed_steps"] == 0
        assert progress["failed_steps"] == 0
        assert progress["pending_steps"] == 0
        assert progress["progress_percentage"] == 0
        assert progress["is_completed"] is True
        assert progress["is_failed"] is False
    
    def test_mark_started(self):
        """Тест отметки начала выполнения"""
        task = Task(title="Test Task")
        start_time = datetime.now()
        
        task.mark_started()
        
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None
        assert task.started_at >= start_time
    
    def test_mark_completed(self):
        """Тест отметки завершения"""
        task = Task(title="Test Task")
        task.mark_started()
        completion_time = datetime.now()
        
        task.mark_completed()
        
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.completed_at >= completion_time
    
    def test_mark_failed(self):
        """Тест отметки неудачи"""
        task = Task(title="Test Task")
        task.mark_started()
        failure_time = datetime.now()
        
        task.mark_failed()
        
        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.completed_at >= failure_time
    
    def test_get_duration_not_started(self):
        """Тест получения длительности для не начатой задачи"""
        task = Task(title="Test Task")
        
        duration = task.get_duration()
        assert duration is None
    
    def test_get_duration_not_completed(self):
        """Тест получения длительности для не завершенной задачи"""
        task = Task(title="Test Task")
        task.mark_started()
        
        duration = task.get_duration()
        assert duration is None
    
    def test_get_duration_completed(self):
        """Тест получения длительности для завершенной задачи"""
        task = Task(title="Test Task")
        task.mark_started()
        
        # Имитируем выполнение в течение 5 минут
        task.started_at = datetime.now() - timedelta(minutes=5)
        task.mark_completed()
        
        duration = task.get_duration()
        assert duration is not None
        assert 4.9 <= duration <= 5.1  # Учитываем погрешность


class TestPlanningResult:
    """Тесты для PlanningResult"""
    
    def test_planning_result_success(self):
        """Тест успешного результата планирования"""
        task = Task(title="Test Task")
        result = PlanningResult(
            success=True,
            task=task,
            planning_duration=1.5,
            llm_usage={"total_tokens": 100}
        )
        
        assert result.success is True
        assert result.task == task
        assert result.error_message is None
        assert result.planning_duration == 1.5
        assert result.llm_usage == {"total_tokens": 100}
        assert result.metadata == {}
    
    def test_planning_result_failure(self):
        """Тест неудачного результата планирования"""
        result = PlanningResult(
            success=False,
            error_message="Planning failed",
            planning_duration=0.5
        )
        
        assert result.success is False
        assert result.task is None
        assert result.error_message == "Planning failed"
        assert result.planning_duration == 0.5
        assert result.llm_usage is None
    
    def test_planning_result_to_dict_success(self):
        """Тест преобразования успешного результата в словарь"""
        task = Task(title="Test Task")
        step = TaskStep(title="Test Step", priority=Priority.HIGH)
        task.add_step(step)
        
        result = PlanningResult(
            success=True,
            task=task,
            planning_duration=2.0,
            llm_usage={"total_tokens": 200}
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["error_message"] is None
        assert result_dict["planning_duration"] == 2.0
        assert result_dict["llm_usage"] == {"total_tokens": 200}
        assert "task" in result_dict
        assert result_dict["task"]["title"] == "Test Task"
        assert len(result_dict["task"]["steps"]) == 1
        assert result_dict["task"]["steps"][0]["title"] == "Test Step"
        assert "progress" in result_dict["task"]
    
    def test_planning_result_to_dict_failure(self):
        """Тест преобразования неудачного результата в словарь"""
        result = PlanningResult(
            success=False,
            error_message="Test error",
            planning_duration=1.0
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is False
        assert result_dict["error_message"] == "Test error"
        assert result_dict["planning_duration"] == 1.0
        assert result_dict["llm_usage"] is None
        assert "task" not in result_dict


class TestStepExecutionResult:
    """Тесты для StepExecutionResult"""
    
    def test_step_execution_result_success(self):
        """Тест успешного результата выполнения шага"""
        result = StepExecutionResult(
            step_id="step_1",
            success=True,
            output="Command completed successfully",
            duration=2.5,
            retry_count=0
        )
        
        assert result.step_id == "step_1"
        assert result.success is True
        assert result.output == "Command completed successfully"
        assert result.error is None
        assert result.exit_code is None
        assert result.duration == 2.5
        assert result.retry_count == 0
        assert result.autocorrection_applied is False
        assert result.metadata == {}
    
    def test_step_execution_result_failure(self):
        """Тест неудачного результата выполнения шага"""
        result = StepExecutionResult(
            step_id="step_1",
            success=False,
            error="Command failed",
            exit_code=1,
            duration=1.0,
            retry_count=2,
            autocorrection_applied=True
        )
        
        assert result.step_id == "step_1"
        assert result.success is False
        assert result.output is None
        assert result.error == "Command failed"
        assert result.exit_code == 1
        assert result.duration == 1.0
        assert result.retry_count == 2
        assert result.autocorrection_applied is True
    
    def test_step_execution_result_to_dict(self):
        """Тест преобразования результата в словарь"""
        result = StepExecutionResult(
            step_id="step_1",
            success=True,
            output="Success",
            duration=3.0,
            metadata={"key": "value"}
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["step_id"] == "step_1"
        assert result_dict["success"] is True
        assert result_dict["output"] == "Success"
        assert result_dict["error"] is None
        assert result_dict["exit_code"] is None
        assert result_dict["duration"] == 3.0
        assert result_dict["retry_count"] == 0
        assert result_dict["autocorrection_applied"] is False
        assert result_dict["metadata"] == {"key": "value"}


class TestTaskExecutionResult:
    """Тесты для TaskExecutionResult"""
    
    def test_task_execution_result_success(self):
        """Тест успешного результата выполнения задачи"""
        completed_step = StepExecutionResult("step_1", True, "Success")
        result = TaskExecutionResult(
            task_id="task_1",
            success=True,
            completed_steps=[completed_step],
            total_duration=10.5
        )
        
        assert result.task_id == "task_1"
        assert result.success is True
        assert len(result.completed_steps) == 1
        assert result.completed_steps[0] == completed_step
        assert result.failed_steps == []
        assert result.total_duration == 10.5
        assert result.error_summary is None
        assert result.metadata == {}
    
    def test_task_execution_result_failure(self):
        """Тест неудачного результата выполнения задачи"""
        failed_step = StepExecutionResult("step_1", False, error="Failed")
        result = TaskExecutionResult(
            task_id="task_1",
            success=False,
            failed_steps=[failed_step],
            total_duration=5.0,
            error_summary="Task execution failed"
        )
        
        assert result.task_id == "task_1"
        assert result.success is False
        assert result.completed_steps == []
        assert len(result.failed_steps) == 1
        assert result.failed_steps[0] == failed_step
        assert result.total_duration == 5.0
        assert result.error_summary == "Task execution failed"
    
    def test_task_execution_result_to_dict(self):
        """Тест преобразования результата в словарь"""
        completed_step = StepExecutionResult("step_1", True, "Success")
        failed_step = StepExecutionResult("step_2", False, error="Failed")
        
        result = TaskExecutionResult(
            task_id="task_1",
            success=True,
            completed_steps=[completed_step],
            failed_steps=[failed_step],
            total_duration=15.0,
            metadata={"key": "value"}
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["task_id"] == "task_1"
        assert result_dict["success"] is True
        assert len(result_dict["completed_steps"]) == 1
        assert result_dict["completed_steps"][0]["step_id"] == "step_1"
        assert len(result_dict["failed_steps"]) == 1
        assert result_dict["failed_steps"][0]["step_id"] == "step_2"
        assert result_dict["total_duration"] == 15.0
        assert result_dict["error_summary"] is None
        assert result_dict["metadata"] == {"key": "value"}


if __name__ == "__main__":
    pytest.main([__file__])
