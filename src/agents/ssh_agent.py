"""
SSH Agent - Главный класс приложения с координацией между агентами

Этот модуль обеспечивает:
- Координацию между всеми агентами системы
- Управление состоянием выполнения задач
- Интеграцию всех компонентов
- Обработку ошибок и эскалацию
- Мониторинг и отчетность
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ..config.agent_config import AgentConfig
from ..config.server_config import ServerConfig
from ..connectors.ssh_connector import SSHConnector
from ..agents.task_master_integration import TaskMasterIntegration
from ..agents.task_agent import TaskAgent, TaskPlanningContext
from ..agents.subtask_agent import SubtaskAgent, SubtaskPlanningContext
from ..models.execution_model import ExecutionModel
from ..agents.error_handler import ErrorHandler
from ..models.planning_model import Task, TaskStep, StepStatus, TaskStatus
from ..models.execution_context import ExecutionContext
from ..utils.logger import StructuredLogger
from ..utils.error_tracker import ErrorTracker


class AgentState(Enum):
    """Состояние агента"""
    INITIALIZING = "initializing"
    READY = "ready"
    EXECUTING = "executing"
    ERROR = "error"
    STOPPED = "stopped"


class TaskExecutionState(Enum):
    """Состояние выполнения задачи"""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskExecutionResult:
    """Результат выполнения задачи"""
    
    task_id: str
    success: bool
    state: TaskExecutionState
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: Optional[float] = None
    steps_completed: int = 0
    steps_failed: int = 0
    error_count: int = 0
    error_reports: List[Dict[str, Any]] = field(default_factory=list)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "state": self.state.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration": self.total_duration,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "error_count": self.error_count,
            "error_reports": self.error_reports,
            "execution_log": self.execution_log,
            "metadata": self.metadata
        }


@dataclass
class AgentStatus:
    """Статус агента"""
    
    agent_name: str
    state: AgentState
    last_activity: Optional[datetime] = None
    error_count: int = 0
    success_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SSHAgent:
    """
    Главный класс SSH Agent с координацией между агентами
    
    Основные возможности:
    - Координация между всеми агентами системы
    - Управление состоянием выполнения задач
    - Интеграция всех компонентов
    - Обработка ошибок и эскалация
    - Мониторинг и отчетность
    """
    
    def __init__(
        self,
        server_config: ServerConfig,
        agent_config: AgentConfig,
        project_root: Optional[str] = None
    ):
        """
        Инициализация SSH Agent
        
        Args:
            server_config: Конфигурация сервера
            agent_config: Конфигурация агентов
            project_root: Корневая директория проекта
        """
        self.server_config = server_config
        self.agent_config = agent_config
        self.project_root = project_root
        self.logger = StructuredLogger("SSHAgent")
        
        # Состояние агента
        self.state = AgentState.INITIALIZING
        self.current_task: Optional[Task] = None
        self.current_execution: Optional[TaskExecutionResult] = None
        
        # Компоненты системы
        self.ssh_connector: Optional[SSHConnector] = None
        self.task_master: Optional[TaskMasterIntegration] = None
        self.task_agent: Optional[TaskAgent] = None
        self.subtask_agent: Optional[SubtaskAgent] = None
        self.execution_model: Optional[ExecutionModel] = None
        self.error_handler: Optional[ErrorHandler] = None
        
        # Система подсчета ошибок
        self.error_tracker: Optional[ErrorTracker] = None
        
        # Статусы агентов
        self.agent_statuses: Dict[str, AgentStatus] = {}
        
        # История выполнения задач
        self.execution_history: List[TaskExecutionResult] = []
        
        # Колбэки для уведомлений
        self.progress_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.error_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.completion_callbacks: List[Callable[[TaskExecutionResult], None]] = []
        
        # Статистика
        self.stats = {
            "tasks_executed": 0,
            "tasks_successful": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0,
            "total_errors": 0,
            "agent_initializations": 0,
            "agent_errors": 0
        }
        
        self.logger.info("SSH Agent инициализирован", project_root=project_root)
    
    async def initialize(self) -> bool:
        """
        Инициализация всех компонентов системы
        
        Returns:
            True если инициализация прошла успешно
        """
        try:
            self.logger.info("Начало инициализации SSH Agent")
            self.state = AgentState.INITIALIZING
            
            # Инициализация SSH коннектора
            await self._initialize_ssh_connector()
            
            # Инициализация Task Master
            await self._initialize_task_master()
            
            # Инициализация агентов
            await self._initialize_agents()
            
            # Инициализация системы подсчета ошибок
            await self._initialize_error_tracking()
            
            # Инициализация обработчика ошибок
            await self._initialize_error_handler()
            
            # Инициализация модели выполнения
            await self._initialize_execution_model()
            
            # Настройка колбэков
            self._setup_callbacks()
            
            self.state = AgentState.READY
            self.stats["agent_initializations"] += 1
            
            self.logger.info(
                "SSH Agent успешно инициализирован",
                components_initialized=len(self.agent_statuses),
                state=self.state.value
            )
            
            return True
            
        except Exception as e:
            self.state = AgentState.ERROR
            self.stats["agent_errors"] += 1
            error_msg = f"Ошибка инициализации SSH Agent: {str(e)}"
            self.logger.error("Ошибка инициализации", error=error_msg)
            
            # Уведомляем об ошибке
            await self._notify_error({
                "type": "initialization_error",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            
            return False
    
    async def execute_task(
        self,
        task_description: str,
        dry_run: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskExecutionResult:
        """
        Выполнение задачи
        
        Args:
            task_description: Описание задачи
            dry_run: Режим симуляции
            context: Дополнительный контекст
            
        Returns:
            Результат выполнения задачи
        """
        if self.state != AgentState.READY:
            raise RuntimeError(f"SSH Agent не готов к выполнению. Текущее состояние: {self.state.value}")
        
        task_id = f"task_{int(time.time() * 1000)}"
        start_time = datetime.now()
        
        self.logger.info(
            "Начало выполнения задачи",
            task_id=task_id,
            task_description=task_description,
            dry_run=dry_run
        )
        
        # Создаем результат выполнения
        execution_result = TaskExecutionResult(
            task_id=task_id,
            success=False,
            state=TaskExecutionState.PENDING,
            start_time=start_time,
            metadata={
                "task_description": task_description,
                "dry_run": dry_run,
                "context": context or {}
            }
        )
        
        self.current_execution = execution_result
        self.state = AgentState.EXECUTING
        
        try:
            # Подключаемся к серверу
            if not dry_run:
                await self._connect_to_server()
            
            # Планирование задачи
            execution_result.state = TaskExecutionState.PLANNING
            await self._notify_progress({
                "task_id": task_id,
                "phase": "planning",
                "message": "Планирование задачи"
            })
            
            task = await self._plan_task(task_description, context)
            self.current_task = task
            
            # Выполнение задачи
            execution_result.state = TaskExecutionState.EXECUTING
            await self._notify_progress({
                "task_id": task_id,
                "phase": "execution",
                "message": "Выполнение задачи",
                "steps_count": len(task.steps)
            })
            
            await self._execute_task_steps(task, dry_run, execution_result)
            
            # Завершение
            execution_result.state = TaskExecutionState.COMPLETED
            execution_result.success = True
            execution_result.end_time = datetime.now()
            execution_result.total_duration = (execution_result.end_time - start_time).total_seconds()
            
            self.stats["tasks_executed"] += 1
            self.stats["tasks_successful"] += 1
            self.stats["total_execution_time"] += execution_result.total_duration
            
            self.logger.info(
                "Задача выполнена успешно",
                task_id=task_id,
                duration=execution_result.total_duration,
                steps_completed=execution_result.steps_completed
            )
            
            # Уведомляем о завершении
            await self._notify_completion(execution_result)
            
        except Exception as e:
            execution_result.state = TaskExecutionState.FAILED
            execution_result.success = False
            execution_result.end_time = datetime.now()
            execution_result.total_duration = (execution_result.end_time - start_time).total_seconds()
            execution_result.error_count += 1
            
            self.stats["tasks_executed"] += 1
            self.stats["tasks_failed"] += 1
            self.stats["total_execution_time"] += execution_result.total_duration
            self.stats["total_errors"] += 1
            
            error_msg = f"Ошибка выполнения задачи: {str(e)}"
            self.logger.error("Ошибка выполнения задачи", task_id=task_id, error=error_msg)
            
            # Добавляем ошибку в лог
            execution_result.execution_log.append({
                "timestamp": datetime.now().isoformat(),
                "level": "error",
                "message": error_msg,
                "phase": execution_result.state.value
            })
            
            # Уведомляем об ошибке
            await self._notify_error({
                "type": "task_execution_error",
                "task_id": task_id,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            
        finally:
            # Отключаемся от сервера
            if not dry_run:
                await self._disconnect_from_server()
            
            # Сохраняем результат
            self.execution_history.append(execution_result)
            self.current_task = None
            self.current_execution = None
            self.state = AgentState.READY
        
        return execution_result
    
    async def _initialize_ssh_connector(self):
        """Инициализация SSH коннектора"""
        self.logger.info("Инициализация SSH коннектора")
        
        self.ssh_connector = SSHConnector(self.server_config)
        self.agent_statuses["ssh_connector"] = AgentStatus(
            agent_name="ssh_connector",
            state=AgentState.READY,
            last_activity=datetime.now()
        )
        
        self.logger.info("SSH коннектор инициализирован")
    
    async def _initialize_task_master(self):
        """Инициализация Task Master"""
        self.logger.info("Инициализация Task Master")
        
        if self.agent_config.taskmaster.enabled:
            self.task_master = TaskMasterIntegration(
                config=self.agent_config.taskmaster,
                project_root=self.project_root
            )
            self.agent_statuses["task_master"] = AgentStatus(
                agent_name="task_master",
                state=AgentState.READY,
                last_activity=datetime.now()
            )
            self.logger.info("Task Master инициализирован")
        else:
            self.logger.info("Task Master отключен в конфигурации")
    
    async def _initialize_agents(self):
        """Инициализация агентов"""
        self.logger.info("Инициализация агентов")
        
        # Task Agent
        self.task_agent = TaskAgent(
            config=self.agent_config,
            task_master=self.task_master
        )
        self.agent_statuses["task_agent"] = AgentStatus(
            agent_name="task_agent",
            state=AgentState.READY,
            last_activity=datetime.now()
        )
        
        # Subtask Agent
        self.subtask_agent = SubtaskAgent(
            config=self.agent_config,
            task_master=self.task_master,
            ssh_connector=self.ssh_connector
        )
        self.agent_statuses["subtask_agent"] = AgentStatus(
            agent_name="subtask_agent",
            state=AgentState.READY,
            last_activity=datetime.now()
        )
        
        self.logger.info("Агенты инициализированы")
    
    async def _initialize_error_tracking(self):
        """Инициализация системы подсчета ошибок"""
        self.logger.info("Инициализация системы подсчета ошибок")
        
        if self.agent_config.error_handler.enable_error_tracking:
            self.error_tracker = ErrorTracker(
                error_threshold=self.agent_config.error_handler.error_threshold_per_step,
                escalation_threshold=self.agent_config.error_handler.human_escalation_threshold,
                max_retention_days=self.agent_config.error_handler.max_retention_days
            )
            
            # Устанавливаем error_tracker в агенты
            if self.task_agent:
                self.task_agent.set_error_tracker(self.error_tracker)
            
            self.agent_statuses["error_tracker"] = AgentStatus(
                agent_name="error_tracker",
                state=AgentState.READY,
                last_activity=datetime.now()
            )
            self.logger.info("Система подсчета ошибок инициализирована")
        else:
            self.logger.info("Система подсчета ошибок отключена в конфигурации")
    
    async def _initialize_error_handler(self):
        """Инициализация обработчика ошибок"""
        self.logger.info("Инициализация обработчика ошибок")
        
        self.error_handler = ErrorHandler(
            config=self.agent_config,
            ssh_connector=self.ssh_connector
        )
        
        # Устанавливаем error_tracker в error_handler
        if self.error_tracker:
            self.error_handler.error_tracker = self.error_tracker
        
        self.agent_statuses["error_handler"] = AgentStatus(
            agent_name="error_handler",
            state=AgentState.READY,
            last_activity=datetime.now()
        )
        
        self.logger.info("Обработчик ошибок инициализирован")
    
    async def _initialize_execution_model(self):
        """Инициализация модели выполнения"""
        self.logger.info("Инициализация модели выполнения")
        
        self.execution_model = ExecutionModel(
            config=self.agent_config,
            ssh_connector=self.ssh_connector,
            task_master=self.task_master
        )
        
        # Устанавливаем error_tracker в execution_model
        if self.error_tracker:
            self.execution_model.error_tracker = self.error_tracker
        
        self.agent_statuses["execution_model"] = AgentStatus(
            agent_name="execution_model",
            state=AgentState.READY,
            last_activity=datetime.now()
        )
        
        self.logger.info("Модель выполнения инициализирована")
    
    def _setup_callbacks(self):
        """Настройка колбэков"""
        # Регистрируем колбэки в error_handler
        if self.error_handler:
            self.error_handler.register_planner_callback(self._on_planner_escalation)
            self.error_handler.register_human_escalation_callback(self._on_human_escalation)
    
    async def _connect_to_server(self):
        """Подключение к серверу"""
        if not self.ssh_connector:
            raise RuntimeError("SSH коннектор не инициализирован")
        
        self.logger.info("Подключение к серверу")
        success = await self.ssh_connector.connect()
        
        if not success:
            raise RuntimeError("Не удалось подключиться к серверу")
        
        self.logger.info("Подключение к серверу установлено")
    
    async def _disconnect_from_server(self):
        """Отключение от сервера"""
        if self.ssh_connector:
            self.logger.info("Отключение от сервера")
            await self.ssh_connector.disconnect()
            self.logger.info("Отключение от сервера завершено")
    
    async def _plan_task(self, task_description: str, context: Optional[Dict[str, Any]]) -> Task:
        """Планирование задачи"""
        if not self.task_agent:
            raise RuntimeError("Task Agent не инициализирован")
        
        self.logger.info("Планирование задачи", task_description=task_description)
        
        # Создаем контекст планирования
        planning_context = TaskPlanningContext(
            server_info=self.server_config.dict(),
            user_requirements=task_description,
            constraints=[],
            available_tools=["apt", "systemctl", "docker", "nginx"],
            previous_tasks=[],
            environment=context or {}
        )
        
        # Планируем задачу
        planning_result = self.task_agent.plan_task(task_description, planning_context)
        
        if not planning_result.success:
            raise RuntimeError(f"Ошибка планирования задачи: {planning_result.error_message}")
        
        task = planning_result.task
        self.logger.info(
            "Задача спланирована",
            task_id=task.task_id,
            steps_count=len(task.steps)
        )
        
        return task
    
    async def _execute_task_steps(
        self,
        task: Task,
        dry_run: bool,
        execution_result: TaskExecutionResult
    ):
        """Выполнение шагов задачи"""
        if not self.subtask_agent or not self.execution_model:
            raise RuntimeError("Агенты не инициализированы")
        
        self.logger.info(
            "Начало выполнения шагов задачи",
            task_id=task.task_id,
            steps_count=len(task.steps)
        )
        
        for step_index, step in enumerate(task.steps):
            try:
                # Обновляем статус шага
                step.status = StepStatus.EXECUTING
                
                await self._notify_progress({
                    "task_id": task.task_id,
                    "phase": "step_execution",
                    "step_index": step_index + 1,
                    "step_id": step.step_id,
                    "step_title": step.title,
                    "message": f"Выполнение шага: {step.title}"
                })
                
                # Планируем подзадачи для шага
                subtask_context = SubtaskPlanningContext(
                    step=step,
                    server_info=self.server_config.dict(),
                    os_type=self.server_config.os_type,
                    installed_services=self.server_config.installed_services,
                    available_tools=["apt", "systemctl", "docker", "nginx"],
                    constraints=[],
                    previous_subtasks=[],
                    environment={}
                )
                
                subtask_result = self.subtask_agent.plan_subtasks(step, subtask_context)
                
                if not subtask_result.success:
                    raise RuntimeError(f"Ошибка планирования подзадач: {subtask_result.error_message}")
                
                # Выполняем подзадачи
                step_success = await self._execute_step_subtasks(
                    step,
                    subtask_result.subtasks,
                    dry_run,
                    execution_result
                )
                
                # Обновляем статус шага
                if step_success:
                    step.status = StepStatus.COMPLETED
                    execution_result.steps_completed += 1
                else:
                    step.status = StepStatus.FAILED
                    execution_result.steps_failed += 1
                
                # Проверяем эскалацию
                if self.error_tracker:
                    escalation_level = self.error_tracker.get_escalation_level(step.step_id)
                    if escalation_level.value != "none":
                        await self._handle_escalation(step, escalation_level.value, execution_result)
                
            except Exception as e:
                step.status = StepStatus.FAILED
                execution_result.steps_failed += 1
                execution_result.error_count += 1
                
                error_msg = f"Ошибка выполнения шага {step.step_id}: {str(e)}"
                self.logger.error("Ошибка выполнения шага", step_id=step.step_id, error=error_msg)
                
                execution_result.execution_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "error",
                    "message": error_msg,
                    "step_id": step.step_id,
                    "step_title": step.title
                })
        
        # Обновляем статус задачи
        if execution_result.steps_failed == 0:
            task.status = TaskStatus.COMPLETED
        else:
            task.status = TaskStatus.FAILED
        
        self.logger.info(
            "Выполнение шагов задачи завершено",
            task_id=task.task_id,
            steps_completed=execution_result.steps_completed,
            steps_failed=execution_result.steps_failed
        )
    
    async def _execute_step_subtasks(
        self,
        step: TaskStep,
        subtasks: List,
        dry_run: bool,
        execution_result: TaskExecutionResult
    ) -> bool:
        """Выполнение подзадач шага"""
        step_success = True
        
        for subtask in subtasks:
            try:
                # Создаем контекст выполнения
                execution_context = ExecutionContext(
                    subtask=subtask,
                    step_id=step.step_id,
                    task_id=step.task_id,
                    ssh_connection=self.ssh_connector,
                    server_info=self.server_config.dict(),
                    dry_run=dry_run
                )
                
                # Выполняем подзадачу
                subtask_result = await self.execution_model.execute_subtask(execution_context)
                
                if not subtask_result.success:
                    step_success = False
                    execution_result.error_count += subtask_result.error_count
                
                # Добавляем в лог выполнения
                execution_result.execution_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "info",
                    "message": f"Подзадача выполнена: {subtask.title}",
                    "subtask_id": subtask.subtask_id,
                    "success": subtask_result.success,
                    "error_count": subtask_result.error_count
                })
                
            except Exception as e:
                step_success = False
                execution_result.error_count += 1
                
                error_msg = f"Ошибка выполнения подзадачи {subtask.subtask_id}: {str(e)}"
                self.logger.error("Ошибка выполнения подзадачи", subtask_id=subtask.subtask_id, error=error_msg)
                
                execution_result.execution_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "error",
                    "message": error_msg,
                    "subtask_id": subtask.subtask_id
                })
        
        return step_success
    
    async def _handle_escalation(
        self,
        step: TaskStep,
        escalation_level: str,
        execution_result: TaskExecutionResult
    ):
        """Обработка эскалации"""
        self.logger.warning(
            "Обработка эскалации",
            step_id=step.step_id,
            escalation_level=escalation_level
        )
        
        if escalation_level == "planner_notification":
            # Эскалация к планировщику
            if self.error_handler:
                error_report = self.error_handler.handle_step_error(
                    step.step_id,
                    self.current_task,
                    {"escalation_level": escalation_level}
                )
                if error_report:
                    execution_result.error_reports.append(error_report.to_dict())
        
        elif escalation_level == "human_escalation":
            # Эскалация к человеку
            if self.error_handler:
                error_report = self.error_handler.handle_step_error(
                    step.step_id,
                    self.current_task,
                    {"escalation_level": escalation_level}
                )
                if error_report:
                    execution_result.error_reports.append(error_report.to_dict())
            
            # Уведомляем об эскалации к человеку
            await self._notify_error({
                "type": "human_escalation",
                "step_id": step.step_id,
                "step_title": step.title,
                "timestamp": datetime.now().isoformat()
            })
    
    def _on_planner_escalation(self, error_report):
        """Колбэк для эскалации к планировщику"""
        self.logger.info("Эскалация к планировщику", report_id=error_report.report_id)
        
        # Здесь можно добавить логику для уведомления планировщика
        # Например, отправить уведомление или обновить статус
    
    def _on_human_escalation(self, error_report):
        """Колбэк для эскалации к человеку"""
        self.logger.error("Эскалация к человеку", report_id=error_report.report_id)
        
        # Здесь можно добавить логику для уведомления человека-оператора
        # Например, отправить email, Slack уведомление и т.д.
    
    async def _notify_progress(self, data: Dict[str, Any]):
        """Уведомление о прогрессе"""
        for callback in self.progress_callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.warning("Ошибка в колбэке прогресса", error=str(e))
    
    async def _notify_error(self, data: Dict[str, Any]):
        """Уведомление об ошибке"""
        for callback in self.error_callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.warning("Ошибка в колбэке ошибки", error=str(e))
    
    async def _notify_completion(self, result: TaskExecutionResult):
        """Уведомление о завершении"""
        for callback in self.completion_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.warning("Ошибка в колбэке завершения", error=str(e))
    
    def register_progress_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Регистрация колбэка для уведомлений о прогрессе"""
        self.progress_callbacks.append(callback)
    
    def register_error_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Регистрация колбэка для уведомлений об ошибках"""
        self.error_callbacks.append(callback)
    
    def register_completion_callback(self, callback: Callable[[TaskExecutionResult], None]):
        """Регистрация колбэка для уведомлений о завершении"""
        self.completion_callbacks.append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса SSH Agent"""
        return {
            "state": self.state.value,
            "current_task": self.current_task.task_id if self.current_task else None,
            "current_execution": self.current_execution.task_id if self.current_execution else None,
            "agent_statuses": {
                name: {
                    "state": status.state.value,
                    "last_activity": status.last_activity.isoformat() if status.last_activity else None,
                    "error_count": status.error_count,
                    "success_count": status.success_count
                }
                for name, status in self.agent_statuses.items()
            },
            "stats": self.stats,
            "execution_history_count": len(self.execution_history)
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение истории выполнения задач"""
        recent_executions = self.execution_history[-limit:]
        return [execution.to_dict() for execution in recent_executions]
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """Получение статистики агентов"""
        return {
            "ssh_agent": self.stats,
            "ssh_connector": self.ssh_connector.get_stats() if self.ssh_connector else {},
            "execution_model": self.execution_model.get_execution_stats() if self.execution_model else {},
            "error_handler": self.error_handler.get_handler_stats() if self.error_handler else {},
            "error_tracker": self.error_tracker.get_global_stats() if self.error_tracker else {}
        }
    
    async def cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("Очистка ресурсов SSH Agent")
        
        # Отключаемся от сервера
        await self._disconnect_from_server()
        
        # Очищаем старые данные
        if self.error_tracker:
            self.error_tracker.cleanup_old_records()
        
        if self.error_handler:
            self.error_handler.cleanup_old_data()
        
        self.state = AgentState.STOPPED
        self.logger.info("Очистка ресурсов завершена")
    
    def __str__(self) -> str:
        return f"SSHAgent(state={self.state.value}, components={len(self.agent_statuses)})"
    
    def __repr__(self) -> str:
        return f"SSHAgent(state={self.state.value}, stats={self.stats})"
