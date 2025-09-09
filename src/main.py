"""
Main entry point for SSH Agent with LLM integration.

This module provides the main SSHAgent class and CLI interface.
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from rich.console import Console

from .config.server_config import ServerConfig
from .config.agent_config import AgentConfig
from .connectors.ssh_connector import SSHConnector
from .agents.task_master_integration import TaskMasterIntegration
from .agents.task_agent import TaskAgent, TaskPlanningContext
from .agents.subtask_agent import SubtaskAgent, SubtaskPlanningContext
from .models.execution_model import ExecutionModel, ExecutionContext
from .agents.error_handler import ErrorHandler
from .utils.logger import LoggerSetup, StructuredLogger
from .models.planning_model import Task, TaskStep, PlanningResult, TaskStatus

console = Console()


@dataclass
class TaskExecutionState:
    """Состояние выполнения задачи"""
    
    task_id: str
    task: Task
    current_step_index: int = 0
    execution_start_time: Optional[datetime] = None
    execution_end_time: Optional[datetime] = None
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    error_count: int = 0
    is_dry_run: bool = False
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_progress_percentage(self) -> float:
        """Получение процента выполнения"""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100
    
    def get_duration(self) -> Optional[float]:
        """Получение длительности выполнения"""
        if self.execution_start_time and self.execution_end_time:
            return (self.execution_end_time - self.execution_start_time).total_seconds()
        elif self.execution_start_time:
            return (datetime.now() - self.execution_start_time).total_seconds()
        return None
    
    def is_completed(self) -> bool:
        """Проверка завершения задачи"""
        return self.completed_steps >= self.total_steps
    
    def is_failed(self) -> bool:
        """Проверка провала задачи"""
        return self.failed_steps > 0 and self.completed_steps < self.total_steps
    
    def add_log_entry(self, entry: Dict[str, Any]):
        """Добавление записи в лог выполнения"""
        entry["timestamp"] = datetime.now().isoformat()
        self.execution_log.append(entry)


class SSHAgent:
    """
    Главный класс SSH Agent, координирующий все компоненты системы.
    
    Основные возможности:
    - Координация между агентами планирования и выполнения
    - Управление состоянием выполнения задач
    - Интеграция всех компонентов системы
    - Обработка ошибок и эскалация
    - Логирование и мониторинг
    """
    
    def __init__(
        self,
        server_config_path: Optional[str] = None,
        agent_config_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация SSH Agent.
        
        Args:
            server_config_path: Путь к файлу конфигурации сервера
            agent_config_path: Путь к файлу конфигурации агентов
            config: Опциональный словарь конфигурации
        """
        # Конфигурации
        self.server_config = None
        self.agent_config = None
        
        # Компоненты системы
        self.ssh_connector = None
        self.task_master = None
        self.task_agent = None
        self.subtask_agent = None
        self.execution_model = None
        self.error_handler = None
        
        # Система управления состоянием
        self.current_execution_state: Optional[TaskExecutionState] = None
        self.execution_history: List[TaskExecutionState] = []
        self.logger = None
        
        # Статистика
        self.agent_stats = {
            "tasks_executed": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0,
            "total_errors": 0,
            "escalations": 0
        }
        
        # Загружаем конфигурации
        self._load_configurations(server_config_path, agent_config_path, config)
        
        # Инициализируем компоненты
        self._initialize_components()
    
    def _load_configurations(
        self,
        server_config_path: Optional[str],
        agent_config_path: Optional[str],
        config: Optional[Dict[str, Any]]
    ):
        """Загрузка конфигурации из файлов или словаря."""
        try:
            if config:
                # Загружаем из словаря
                self.server_config = ServerConfig(**config.get('server', {}))
                self.agent_config = AgentConfig(**config.get('agents', {}))
            else:
                # Загружаем из файлов
                if server_config_path:
                    self.server_config = ServerConfig.from_yaml(server_config_path)
                else:
                    # Создаем конфигурацию по умолчанию
                    self.server_config = ServerConfig(
                        host="localhost",
                        username="user",
                        auth_method="key"
                    )
                
                if agent_config_path:
                    self.agent_config = AgentConfig.from_yaml(agent_config_path)
                else:
                    # Создаем конфигурацию по умолчанию
                    self.agent_config = AgentConfig(
                        llm={"api_key": "your-api-key"}
                    )
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки конфигурации: {e}")
    
    def _initialize_components(self):
        """Инициализация всех компонентов агента."""
        try:
            # Настройка логирования
            LoggerSetup.setup_logging(
                log_level=self.agent_config.logging.level,
                log_file=self.agent_config.logging.file
            )
            self.logger = StructuredLogger("SSHAgent")
            
            # Инициализация SSH коннектора
            self.ssh_connector = SSHConnector(self.server_config)
            
            # Инициализация Task Master интеграции
            if self.agent_config.taskmaster.enabled:
                self.task_master = TaskMasterIntegration(
                    project_path=".",
                    config=self.agent_config.taskmaster
                )
            
            # Инициализация агентов
            self.task_agent = TaskAgent(
                config=self.agent_config,
                task_master=self.task_master
            )
            
            self.subtask_agent = SubtaskAgent(
                config=self.agent_config,
                task_master=self.task_master,
                ssh_connector=self.ssh_connector
            )
            
            # Инициализация модели выполнения
            self.execution_model = ExecutionModel(
                config=self.agent_config,
                ssh_connector=self.ssh_connector,
                task_master=self.task_master
            )
            
            # Инициализация обработчика ошибок
            self.error_handler = ErrorHandler(
                config=self.agent_config,
                ssh_connector=self.ssh_connector
            )
            
            # Настройка колбэков для обработчика ошибок
            self._setup_error_handler_callbacks()
            
            self.logger.info(
                "SSH Agent инициализирован",
                task_master_enabled=self.task_master is not None,
                ssh_connector_available=self.ssh_connector is not None,
                error_handler_available=self.error_handler is not None
            )
            
        except Exception as e:
            error_msg = f"Ошибка инициализации компонентов: {e}"
            if self.logger:
                self.logger.error("Ошибка инициализации", error=error_msg)
            raise RuntimeError(error_msg)
    
    def _setup_error_handler_callbacks(self):
        """Настройка колбэков для обработчика ошибок."""
        # Колбэк для уведомления планировщика
        def planner_callback(error_report):
            self.logger.warning(
                "Эскалация к планировщику",
                report_id=error_report.report_id,
                step_id=error_report.details.get("step_id"),
                error_count=error_report.details.get("error_count")
            )
            self.agent_stats["escalations"] += 1
        
        # Колбэк для эскалации к человеку
        def human_escalation_callback(error_report):
            self.logger.error(
                "КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ",
                report_id=error_report.report_id,
                step_id=error_report.details.get("step_id"),
                error_count=error_report.details.get("error_count")
            )
            self.agent_stats["escalations"] += 1
        
        # Регистрируем колбэки
        self.error_handler.register_planner_callback(planner_callback)
        self.error_handler.register_human_escalation_callback(human_escalation_callback)
    
    async def execute_task(self, task_description: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Выполнение задачи на удаленном сервере с полной координацией компонентов.
        
        Args:
            task_description: Описание задачи для выполнения
            dry_run: Если True, только показать что будет выполнено
            
        Returns:
            Словарь с результатами выполнения
        """
        execution_start_time = time.time()
        
        try:
            self.logger.info("Начало выполнения задачи", task_description=task_description, dry_run=dry_run)
            console.print(f"[bold blue]Выполнение задачи:[/bold blue] {task_description}")
            
            # Подключение к серверу
            if not await self.ssh_connector.connect():
                error_msg = "Не удалось подключиться к серверу"
                self.logger.error("Ошибка подключения", error=error_msg)
                return {"success": False, "error": error_msg}
            
            # Создание контекста планирования
            planning_context = TaskPlanningContext(
                server_info=self.server_config.get_server_info(),
                user_requirements=task_description,
                constraints=self.server_config.forbidden_commands,
                available_tools=["apt", "systemctl", "docker", "nginx", "curl", "wget"],
                previous_tasks=[],
                environment={"os_type": self.server_config.os_type}
            )
            
            # Планирование задачи
            planning_result = self.task_agent.plan_task(task_description, planning_context)
            if not planning_result.success:
                error_msg = f"Ошибка планирования: {planning_result.error_message}"
                self.logger.error("Ошибка планирования", error=error_msg)
                return {"success": False, "error": error_msg}
            
            task = planning_result.task
            console.print(f"[green]Запланировано {len(task.steps)} шагов[/green]")
            
            # Создание состояния выполнения
            self.current_execution_state = TaskExecutionState(
                task_id=task.task_id,
                task=task,
                total_steps=len(task.steps),
                is_dry_run=dry_run,
                execution_start_time=datetime.now()
            )
            
            # Выполнение каждого шага
            step_results = []
            for step_index, step in enumerate(task.steps):
                self.current_execution_state.current_step_index = step_index
                
                console.print(f"[yellow]Выполнение шага {step_index + 1}/{len(task.steps)}:[/yellow] {step.title}")
                
                # Планирование подзадач для шага
                subtask_context = SubtaskPlanningContext(
                    step=step,
                    server_info=self.server_config.get_server_info(),
                    os_type=self.server_config.os_type,
                    installed_services=self.server_config.installed_services,
                    available_tools=["apt", "systemctl", "docker", "nginx", "curl", "wget"],
                    constraints=self.server_config.forbidden_commands,
                    previous_subtasks=[],
                    environment={"os_type": self.server_config.os_type}
                )
                
                subtask_planning_result = self.subtask_agent.plan_subtasks(step, subtask_context)
                if not subtask_planning_result.success:
                    self.logger.error("Ошибка планирования подзадач", step_id=step.step_id, error=subtask_planning_result.error_message)
                    step.error_count += 1
                    self.current_execution_state.failed_steps += 1
                    continue
                
                # Выполнение подзадач
                step_result = await self._execute_step(step, subtask_planning_result.subtasks, dry_run)
                step_results.append(step_result)
                
                # Обновление состояния
                if step_result["success"]:
                    self.current_execution_state.completed_steps += 1
                    step.status = "completed"
                else:
                    self.current_execution_state.failed_steps += 1
                    step.status = "failed"
                    step.error_count += step_result.get("error_count", 0)
                
                # Обработка ошибок
                if step_result.get("error_count", 0) > 0:
                    error_report = self.error_handler.handle_step_error(
                        step.step_id, task, step_result
                    )
                    if error_report:
                        self.logger.warning("Создан отчет об ошибке", report_id=error_report.report_id)
            
            # Завершение выполнения
            self.current_execution_state.execution_end_time = datetime.now()
            execution_duration = time.time() - execution_start_time
            
            # Обработка завершения задачи
            final_report = self.error_handler.handle_task_completion(task, {
                "step_results": step_results,
                "execution_duration": execution_duration,
                "dry_run": dry_run
            })
            
            # Обновление статистики
            self._update_agent_stats(task, execution_duration)
            
            # Сохранение в историю
            self.execution_history.append(self.current_execution_state)
            
            result = {
                "success": self.current_execution_state.is_completed(),
                "task_id": task.task_id,
                "steps_completed": self.current_execution_state.completed_steps,
                "steps_failed": self.current_execution_state.failed_steps,
                "total_steps": self.current_execution_state.total_steps,
                "execution_duration": execution_duration,
                "progress_percentage": self.current_execution_state.get_progress_percentage(),
                "step_results": step_results,
                "final_report": final_report.to_dict() if final_report else None,
                "dry_run": dry_run
            }
            
            if result["success"]:
                console.print(f"[green]Задача выполнена успешно![/green] Время: {execution_duration:.2f}с")
            else:
                console.print(f"[red]Задача завершена с ошибками[/red] Время: {execution_duration:.2f}с")
            
            self.logger.info(
                "Выполнение задачи завершено",
                task_id=task.task_id,
                success=result["success"],
                duration=execution_duration,
                steps_completed=self.current_execution_state.completed_steps,
                steps_failed=self.current_execution_state.failed_steps
            )
            
            return result
            
        except Exception as e:
            execution_duration = time.time() - execution_start_time
            error_msg = f"Критическая ошибка выполнения задачи: {str(e)}"
            self.logger.error("Критическая ошибка", error=error_msg, duration=execution_duration)
            console.print(f"[red]Критическая ошибка:[/red] {e}")
            
            return {
                "success": False,
                "error": error_msg,
                "execution_duration": execution_duration,
                "task_id": getattr(self.current_execution_state, 'task_id', None) if self.current_execution_state else None
            }
        
        finally:
            # Отключение от сервера
            if self.ssh_connector:
                await self.ssh_connector.disconnect()
            
            # Очистка текущего состояния
            self.current_execution_state = None
    
    async def _execute_step(self, step: TaskStep, subtasks: List, dry_run: bool) -> Dict[str, Any]:
        """Выполнение одного шага с подзадачами."""
        step_start_time = time.time()
        
        try:
            self.logger.info("Начало выполнения шага", step_id=step.step_id, title=step.title)
            
            # Создание контекста выполнения
            execution_context = ExecutionContext(
                subtask=subtasks[0] if subtasks else None,  # Берем первую подзадачу как основную
                ssh_connection=self.ssh_connector,
                server_info=self.server_config.get_server_info(),
                step_id=step.step_id,
                task_id=step.metadata.get("task_id"),
                dry_run=dry_run
            )
            
            # Выполнение всех подзадач
            subtask_results = []
            total_errors = 0
            
            for subtask in subtasks:
                execution_context.subtask = subtask
                subtask_result = self.execution_model.execute_subtask(execution_context)
                subtask_results.append(subtask_result.to_dict())
                
                if not subtask_result.success:
                    total_errors += subtask_result.error_count
                
                # Логируем результат подзадачи
                self.current_execution_state.add_log_entry({
                    "type": "subtask_result",
                    "subtask_id": subtask.subtask_id,
                    "success": subtask_result.success,
                    "error_count": subtask_result.error_count,
                    "duration": subtask_result.total_duration
                })
            
            step_duration = time.time() - step_start_time
            step_success = total_errors == 0
            
            result = {
                "success": step_success,
                "step_id": step.step_id,
                "subtask_results": subtask_results,
                "error_count": total_errors,
                "duration": step_duration,
                "subtasks_count": len(subtasks)
            }
            
            self.logger.info(
                "Выполнение шага завершено",
                step_id=step.step_id,
                success=step_success,
                duration=step_duration,
                error_count=total_errors
            )
            
            return result
            
        except Exception as e:
            step_duration = time.time() - step_start_time
            error_msg = f"Ошибка выполнения шага: {str(e)}"
            self.logger.error("Ошибка выполнения шага", step_id=step.step_id, error=error_msg, duration=step_duration)
            
            return {
                "success": False,
                "step_id": step.step_id,
                "error": error_msg,
                "error_count": 1,
                "duration": step_duration,
                "subtasks_count": len(subtasks) if subtasks else 0
            }
    
    def _update_agent_stats(self, task: Task, execution_duration: float):
        """Обновление статистики агента."""
        self.agent_stats["tasks_executed"] += 1
        self.agent_stats["total_execution_time"] += execution_duration
        
        if self.current_execution_state.is_completed():
            self.agent_stats["tasks_completed"] += 1
        else:
            self.agent_stats["tasks_failed"] += 1
        
        self.agent_stats["total_errors"] += self.current_execution_state.error_count
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Получение статуса агента."""
        return {
            "agent_stats": self.agent_stats,
            "current_execution": {
                "task_id": self.current_execution_state.task_id if self.current_execution_state else None,
                "progress": self.current_execution_state.get_progress_percentage() if self.current_execution_state else 0,
                "is_running": self.current_execution_state is not None
            },
            "execution_history_count": len(self.execution_history),
            "components_status": {
                "ssh_connector": self.ssh_connector is not None,
                "task_master": self.task_master is not None,
                "task_agent": self.task_agent is not None,
                "subtask_agent": self.subtask_agent is not None,
                "execution_model": self.execution_model is not None,
                "error_handler": self.error_handler is not None
            }
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение истории выполнения задач."""
        recent_executions = self.execution_history[-limit:] if limit > 0 else self.execution_history
        
        return [
            {
                "task_id": state.task_id,
                "task_title": state.task.title,
                "completed_steps": state.completed_steps,
                "total_steps": state.total_steps,
                "failed_steps": state.failed_steps,
                "error_count": state.error_count,
                "duration": state.get_duration(),
                "is_dry_run": state.is_dry_run,
                "execution_start_time": state.execution_start_time.isoformat() if state.execution_start_time else None,
                "execution_end_time": state.execution_end_time.isoformat() if state.execution_end_time else None,
                "success": state.is_completed()
            }
            for state in recent_executions
        ]
    
    def cleanup_old_data(self, days: int = 7):
        """Очистка старых данных."""
        if self.error_handler:
            self.error_handler.cleanup_old_data(days)
        
        # Очистка истории выполнения
        cutoff_time = datetime.now() - timedelta(days=days)
        self.execution_history = [
            state for state in self.execution_history
            if state.execution_start_time and state.execution_start_time >= cutoff_time
        ]
        
        self.logger.info("Очистка старых данных завершена", retention_days=days)


def main():
    """Main entry point."""
    from .cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
