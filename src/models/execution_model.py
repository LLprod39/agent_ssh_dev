"""
Execution Model - Модель выполнения малых шагов

Этот модуль отвечает за:
- Выполнение команд на удаленном сервере через SSH
- Последовательное выполнение подзадач
- Сбор stdout/stderr и exit codes
- Интеграцию с Task Master для отслеживания прогресса
- Автокоррекцию ошибок
- Систему повторных попыток
"""
import time
import json
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging
from enum import Enum

from ..config.agent_config import ExecutorConfig, AgentConfig
from ..connectors.ssh_connector import SSHConnector
from ..agents.subtask_agent import Subtask
from ..agents.task_master_integration import TaskMasterIntegration, TaskMasterResult
from ..utils.logger import StructuredLogger
from ..utils.autocorrection import AutocorrectionEngine, AutocorrectionResult
# ErrorTracker будет импортирован динамически для избежания циклических импортов
from .command_result import CommandResult, ExecutionStatus
from .execution_context import ExecutionContext




@dataclass
class SubtaskExecutionResult:
    """Результат выполнения подзадачи"""
    
    subtask_id: str
    success: bool
    commands_results: List[CommandResult] = field(default_factory=list)
    health_check_results: List[CommandResult] = field(default_factory=list)
    total_duration: Optional[float] = None
    error_count: int = 0
    autocorrection_applied: bool = False
    rollback_executed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "subtask_id": self.subtask_id,
            "success": self.success,
            "commands_results": [cmd.to_dict() for cmd in self.commands_results],
            "health_check_results": [cmd.to_dict() for cmd in self.health_check_results],
            "total_duration": self.total_duration,
            "error_count": self.error_count,
            "autocorrection_applied": self.autocorrection_applied,
            "rollback_executed": self.rollback_executed,
            "metadata": self.metadata
        }




class ExecutionModel:
    """
    Модель выполнения команд
    
    Основные возможности:
    - Выполнение команд на удаленном сервере
    - Последовательное выполнение подзадач
    - Сбор и анализ результатов
    - Автокоррекция ошибок
    - Интеграция с Task Master
    - Система повторных попыток
    """
    
    def __init__(self, config: AgentConfig, ssh_connector: SSHConnector, 
                 task_master: Optional[TaskMasterIntegration] = None):
        """
        Инициализация Execution Model
        
        Args:
            config: Конфигурация агентов
            ssh_connector: SSH коннектор для подключения к серверу
            task_master: Интеграция с Task Master
        """
        self.config = config
        self.executor_config = config.executor
        self.ssh_connector = ssh_connector
        self.task_master = task_master
        self.logger = StructuredLogger("ExecutionModel")
        
        # Инициализация движка автокоррекции
        self.autocorrection_engine = AutocorrectionEngine(
            max_attempts=self.executor_config.autocorrection_max_attempts,
            timeout=self.executor_config.autocorrection_timeout
        )
        
        # Инициализация системы подсчета ошибок (динамический импорт)
        try:
            from ..utils.error_tracker import ErrorTracker
            self.error_tracker = ErrorTracker(
                error_threshold=config.error_handler.error_threshold_per_step,
                escalation_threshold=config.error_handler.human_escalation_threshold,
                max_retention_days=config.error_handler.max_retention_days
            )
        except ImportError:
            self.error_tracker = None
            self.logger.warning("ErrorTracker недоступен, система подсчета ошибок отключена")
        
        # Статистика выполнения
        self.execution_stats = {
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
            "retry_attempts": 0,
            "autocorrections": 0,
            "autocorrection_successes": 0,
            "total_duration": 0.0
        }
        
        self.logger.info(
            "Execution Model инициализирован",
            max_retries=self.executor_config.max_retries_per_command,
            auto_correction_enabled=self.executor_config.auto_correction_enabled,
            dry_run_mode=self.executor_config.dry_run_mode,
            task_master_enabled=self.task_master is not None
        )
    
    def execute_subtask(self, context: ExecutionContext) -> SubtaskExecutionResult:
        """
        Выполнение подзадачи
        
        Args:
            context: Контекст выполнения
            
        Returns:
            Результат выполнения подзадачи
        """
        start_time = time.time()
        subtask = context.subtask
        
        self.logger.info(
            "Начало выполнения подзадачи",
            subtask_id=subtask.subtask_id,
            title=subtask.title,
            commands_count=len(subtask.commands),
            health_checks_count=len(subtask.health_checks)
        )
        
        # Отправляем прогресс в Task Master
        if self.task_master:
            self._report_progress_to_taskmaster(context, "subtask_started", {
                "subtask_id": subtask.subtask_id,
                "title": subtask.title
            })
        
        try:
            # Выполняем команды подзадачи
            commands_results = self._execute_commands(subtask.commands, context)
            
            # Проверяем успешность выполнения команд
            commands_success = all(cmd.success for cmd in commands_results)
            
            if not commands_success and self.executor_config.auto_correction_enabled:
                # Пытаемся исправить ошибки
                self.logger.info("Применение автокоррекции", subtask_id=subtask.subtask_id)
                corrected_results = self._apply_autocorrection(commands_results, context)
                if corrected_results:
                    commands_results = corrected_results
                    commands_success = all(cmd.success for cmd in commands_results)
            
            # Выполняем health-check команды
            health_check_results = []
            if commands_success:
                health_check_results = self._execute_health_checks(subtask.health_checks, context)
                health_checks_success = all(cmd.success for cmd in health_check_results)
                
                if not health_checks_success:
                    self.logger.warning(
                        "Health-check команды не прошли",
                        subtask_id=subtask.subtask_id,
                        failed_checks=[cmd.command for cmd in health_check_results if not cmd.success]
                    )
            else:
                self.logger.warning(
                    "Команды подзадачи не выполнены успешно",
                    subtask_id=subtask.subtask_id,
                    failed_commands=[cmd.command for cmd in commands_results if not cmd.success]
                )
            
            # Определяем общий успех
            overall_success = commands_success and (not health_check_results or all(cmd.success for cmd in health_check_results))
            
            # Выполняем откат если нужно
            rollback_executed = False
            if not overall_success and subtask.rollback_commands:
                self.logger.info("Выполнение отката", subtask_id=subtask.subtask_id)
                rollback_results = self._execute_rollback(subtask.rollback_commands, context)
                rollback_executed = True
            
            total_duration = time.time() - start_time
            
            # Обновляем статистику
            self._update_execution_stats(commands_results, health_check_results, total_duration)
            
            result = SubtaskExecutionResult(
                subtask_id=subtask.subtask_id,
                success=overall_success,
                commands_results=commands_results,
                health_check_results=health_check_results,
                total_duration=total_duration,
                error_count=len([cmd for cmd in commands_results if not cmd.success]),
                autocorrection_applied=self.executor_config.auto_correction_enabled and not commands_success,
                rollback_executed=rollback_executed,
                metadata={
                    "subtask_title": subtask.title,
                    "subtask_description": subtask.description,
                    "execution_timestamp": datetime.now().isoformat(),
                    "server_info": context.server_info
                }
            )
            
            # Отправляем результат в Task Master
            if self.task_master:
                self._report_progress_to_taskmaster(context, "subtask_completed", {
                    "subtask_id": subtask.subtask_id,
                    "success": overall_success,
                    "duration": total_duration,
                    "error_count": result.error_count
                })
            
            self.logger.info(
                "Выполнение подзадачи завершено",
                subtask_id=subtask.subtask_id,
                success=overall_success,
                duration=total_duration,
                commands_executed=len(commands_results),
                health_checks_executed=len(health_check_results)
            )
            
            return result
            
        except Exception as e:
            total_duration = time.time() - start_time
            error_msg = f"Ошибка выполнения подзадачи: {str(e)}"
            self.logger.error("Ошибка выполнения подзадачи", error=error_msg, subtask_id=subtask.subtask_id)
            
            # Отправляем ошибку в Task Master
            if self.task_master:
                self._report_progress_to_taskmaster(context, "subtask_failed", {
                    "subtask_id": subtask.subtask_id,
                    "error": error_msg,
                    "duration": total_duration
                })
            
            return SubtaskExecutionResult(
                subtask_id=subtask.subtask_id,
                success=False,
                total_duration=total_duration,
                error_count=1,
                metadata={
                    "error": error_msg,
                    "subtask_title": subtask.title,
                    "execution_timestamp": datetime.now().isoformat()
                }
            )
    
    def _execute_commands(self, commands: List[str], context: ExecutionContext) -> List[CommandResult]:
        """Выполнение списка команд с интегрированной проверкой безопасности"""
        results = []
        
        for i, command in enumerate(commands):
            self.logger.debug("Выполнение команды", command=command, order=i+1)
            
            # Контекст для валидации команды
            validation_context = {
                'step_id': getattr(context, 'step_id', None),
                'task_id': getattr(context, 'task_id', None),
                'subtask_id': context.subtask.subtask_id,
                'command_index': i,
                'server_info': context.server_info
            }
            
            # Проверяем режим dry-run
            if self.executor_config.dry_run_mode:
                result = self._simulate_command_execution(command, validation_context)
            else:
                result = self._execute_single_command(command, context, validation_context)
            
            results.append(result)
            
            # Если команда не удалась и это критично, прерываем выполнение
            if not result.success and self._is_critical_command(command):
                self.logger.warning("Критическая команда не выполнена, прерывание", command=command)
                break
            
            # Небольшая пауза между командами
            time.sleep(0.1)
        
        return results
    
    def _execute_single_command(self, command: str, context: ExecutionContext, validation_context: Dict[str, Any] = None) -> CommandResult:
        """Выполнение одной команды"""
        start_time = time.time()
        
        try:
            # Выполняем команду через SSH с передачей контекста валидации
            stdout, stderr, exit_code = context.ssh_connection.execute_command(
                command, 
                timeout=self.executor_config.command_timeout,
                context=validation_context
            )
            
            duration = time.time() - start_time
            success = exit_code == 0
            
            result = CommandResult(
                command=command,
                success=success,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
                error_message=stderr if not success else None,
                metadata={
                    "execution_timestamp": datetime.now().isoformat(),
                    "timeout": self.executor_config.command_timeout
                }
            )
            
            # Записываем попытку выполнения в систему подсчета ошибок
            if self.error_tracker:
                self.error_tracker.record_attempt(
                    step_id=context.subtask.subtask_id,
                    command=command,
                    success=success,
                    duration=duration,
                    exit_code=exit_code,
                    error_message=stderr if not success else None,
                    autocorrection_used=False,  # Будет обновлено при автокоррекции
                    metadata={
                        "subtask_id": context.subtask.subtask_id,
                        "command_type": "main_command"
                    }
                )
            
            self.logger.debug(
                "Команда выполнена",
                command=command,
                success=success,
                exit_code=exit_code,
                duration=duration,
                stdout_length=len(stdout) if stdout else 0,
                stderr_length=len(stderr) if stderr else 0
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Ошибка выполнения команды: {str(e)}"
            
            # Записываем неудачную попытку
            if self.error_tracker:
                self.error_tracker.record_attempt(
                    step_id=context.subtask.subtask_id,
                    command=command,
                    success=False,
                    duration=duration,
                    error_message=error_msg,
                    autocorrection_used=False,
                    metadata={
                        "subtask_id": context.subtask.subtask_id,
                        "command_type": "main_command",
                        "exception": str(e)
                    }
                )
            
            self.logger.error("Ошибка выполнения команды", command=command, error=error_msg, duration=duration)
            
            return CommandResult(
                command=command,
                success=False,
                duration=duration,
                status=ExecutionStatus.FAILED,
                error_message=error_msg,
                metadata={
                    "execution_timestamp": datetime.now().isoformat(),
                    "exception": str(e)
                }
            )
    
    def _simulate_command_execution(self, command: str, validation_context: Dict[str, Any] = None) -> CommandResult:
        """Симуляция выполнения команды (dry-run режим) с проверкой безопасности"""
        # Имитируем выполнение команды
        time.sleep(0.1)  # Небольшая задержка для реалистичности
        
        # Проверяем команду через валидатор SSH коннектора
        is_safe = True
        validation_errors = []
        
        try:
            # Проверяем безопасность команды
            is_safe = self.ssh_connector.is_command_safe(command)
            if not is_safe:
                validation_errors.append("Команда заблокирована системой безопасности")
        except Exception as e:
            validation_errors.append(f"Ошибка валидации: {str(e)}")
            is_safe = False
        
        # Дополнительная проверка на опасность
        success = is_safe and not self._is_dangerous_command(command)
        
        error_message = None
        stdout = None
        
        if not success:
            if validation_errors:
                error_message = f"[DRY-RUN] {'; '.join(validation_errors)}"
            else:
                error_message = f"[DRY-RUN] Команда '{command}' определена как опасная"
        else:
            stdout = f"[DRY-RUN] Команда '{command}' выполнена успешно"
        
        return CommandResult(
            command=command,
            success=success,
            exit_code=0 if success else 1,
            stdout=stdout,
            stderr=error_message,
            duration=0.1,
            status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
            error_message=error_message,
            metadata={
                "dry_run": True,
                "execution_timestamp": datetime.now().isoformat(),
                "security_check": "passed" if is_safe else "failed",
                "validation_context": validation_context
            }
        )
    
    def _execute_health_checks(self, health_checks: List[str], context: ExecutionContext) -> List[CommandResult]:
        """Выполнение health-check команд"""
        results = []
        
        for health_check in health_checks:
            self.logger.debug("Выполнение health-check", command=health_check)
            
            if self.executor_config.dry_run_mode:
                result = self._simulate_health_check(health_check)
            else:
                result = self._execute_single_command(health_check, context)
            
            results.append(result)
            
            # Небольшая пауза между проверками
            time.sleep(0.1)
        
        return results
    
    def _simulate_health_check(self, health_check: str) -> CommandResult:
        """Симуляция health-check команды"""
        time.sleep(0.05)
        
        # Большинство health-check команд считаем успешными в dry-run режиме
        return CommandResult(
            command=health_check,
            success=True,
            exit_code=0,
            stdout=f"[DRY-RUN] Health-check '{health_check}' прошел успешно",
            duration=0.05,
            status=ExecutionStatus.COMPLETED,
            metadata={
                "dry_run": True,
                "health_check": True,
                "execution_timestamp": datetime.now().isoformat()
            }
        )
    
    def _execute_rollback(self, rollback_commands: List[str], context: ExecutionContext) -> List[CommandResult]:
        """Выполнение команд отката"""
        self.logger.info("Выполнение отката", commands_count=len(rollback_commands))
        
        results = []
        for rollback_command in rollback_commands:
            self.logger.debug("Выполнение команды отката", command=rollback_command)
            
            if self.executor_config.dry_run_mode:
                result = self._simulate_command_execution(rollback_command)
            else:
                result = self._execute_single_command(rollback_command, context)
            
            results.append(result)
            
            # Небольшая пауза между командами отката
            time.sleep(0.1)
        
        return results
    
    def _apply_autocorrection(self, failed_results: List[CommandResult], context: ExecutionContext) -> Optional[List[CommandResult]]:
        """Применение автокоррекции для исправления ошибок"""
        corrected_results = []
        corrections_applied = False
        
        for result in failed_results:
            if result.success:
                corrected_results.append(result)
                continue
            
            # Используем новый движок автокоррекции
            autocorrection_result = self.autocorrection_engine.correct_command(result, context)
            
            if autocorrection_result.success and autocorrection_result.final_command:
                self.logger.info(
                    "Применение автокоррекции",
                    original_command=result.command,
                    corrected_command=autocorrection_result.final_command,
                    attempts=autocorrection_result.total_attempts
                )
                
                # Выполняем исправленную команду
                corrected_result = self._execute_single_command(autocorrection_result.final_command, context)
                corrected_result.retry_count = result.retry_count + 1
                corrected_result.metadata["autocorrected"] = True
                corrected_result.metadata["original_command"] = result.command
                corrected_result.metadata["autocorrection_attempts"] = autocorrection_result.total_attempts
                corrected_result.metadata["autocorrection_strategies"] = [
                    attempt.strategy.value for attempt in autocorrection_result.attempts
                ]
                
                # Записываем попытку автокоррекции
                if self.error_tracker:
                    self.error_tracker.record_attempt(
                        step_id=context.subtask.subtask_id,
                        command=autocorrection_result.final_command,
                        success=corrected_result.success,
                        duration=corrected_result.duration or 0.0,
                        exit_code=corrected_result.exit_code,
                        error_message=corrected_result.error_message,
                        autocorrection_used=True,
                        metadata={
                            "subtask_id": context.subtask.subtask_id,
                            "command_type": "autocorrected_command",
                            "original_command": result.command,
                            "autocorrection_attempts": autocorrection_result.total_attempts
                        }
                    )
                
                corrected_results.append(corrected_result)
                corrections_applied = True
                self.execution_stats["autocorrections"] += 1
                self.execution_stats["autocorrection_successes"] += 1
            else:
                self.logger.warning(
                    "Автокоррекция не удалась",
                    original_command=result.command,
                    attempts=autocorrection_result.total_attempts if autocorrection_result else 0
                )
                corrected_results.append(result)
        
        return corrected_results if corrections_applied else None
    
    
    def _is_critical_command(self, command: str) -> bool:
        """Проверка, является ли команда критической"""
        critical_patterns = [
            "systemctl start",
            "systemctl enable",
            "service start",
            "docker start",
            "nginx -t",
            "apache2ctl configtest"
        ]
        
        command_lower = command.lower()
        return any(pattern in command_lower for pattern in critical_patterns)
    
    def _is_dangerous_command(self, command: str) -> bool:
        """Проверка на опасные команды"""
        dangerous_patterns = [
            "rm -rf /",
            "dd if=/dev/zero",
            "mkfs",
            "fdisk",
            "parted",
            "> /dev/sda",
            "chmod 777 /",
            "chown -R root:root /",
            "passwd root",
            "userdel -r",
            "groupdel",
            "killall -9",
            "pkill -9",
            "halt",
            "poweroff",
            "reboot",
            "shutdown"
        ]
        
        command_lower = command.lower().strip()
        return any(pattern in command_lower for pattern in dangerous_patterns)
    
    def _update_execution_stats(self, commands_results: List[CommandResult], 
                               health_check_results: List[CommandResult], duration: float):
        """Обновление статистики выполнения"""
        all_results = commands_results + health_check_results
        
        self.execution_stats["total_commands"] += len(all_results)
        self.execution_stats["successful_commands"] += len([r for r in all_results if r.success])
        self.execution_stats["failed_commands"] += len([r for r in all_results if not r.success])
        self.execution_stats["retry_attempts"] += sum(r.retry_count for r in all_results)
        self.execution_stats["total_duration"] += duration
    
    def _report_progress_to_taskmaster(self, context: ExecutionContext, event_type: str, data: Dict[str, Any]):
        """Отправка прогресса в Task Master"""
        if not self.task_master:
            return
        
        try:
            progress_data = {
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                "subtask_id": context.subtask.subtask_id,
                "data": data
            }
            
            result = self.task_master.report_progress(progress_data)
            if not result.success:
                self.logger.warning("Не удалось отправить прогресс в Task Master", error=result.error)
                
        except Exception as e:
            self.logger.warning("Ошибка отправки прогресса в Task Master", error=str(e))
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Получение статистики выполнения"""
        return {
            **self.execution_stats,
            "success_rate": (
                self.execution_stats["successful_commands"] / self.execution_stats["total_commands"] * 100
                if self.execution_stats["total_commands"] > 0 else 0
            ),
            "average_duration": (
                self.execution_stats["total_duration"] / self.execution_stats["total_commands"]
                if self.execution_stats["total_commands"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        """Сброс статистики выполнения"""
        self.execution_stats = {
            "total_commands": 0,
            "successful_commands": 0,
            "failed_commands": 0,
            "retry_attempts": 0,
            "autocorrections": 0,
            "autocorrection_successes": 0,
            "total_duration": 0.0
        }
        self.logger.info("Статистика выполнения сброшена")
    
    def get_error_tracking_stats(self) -> Dict[str, Any]:
        """Получить статистику системы подсчета ошибок"""
        if self.error_tracker:
            return self.error_tracker.get_global_stats()
        return {"total_errors": 0, "total_attempts": 0, "success_rate": 0.0}
    
    def get_step_error_summary(self, step_id: str) -> Dict[str, Any]:
        """Получить сводку ошибок для шага"""
        if self.error_tracker:
            return self.error_tracker.get_error_summary(step_id)
        return {"step_id": step_id, "error_count": 0, "attempt_count": 0, "success_rate": 0.0}
    
    def should_escalate_to_planner(self, step_id: str) -> bool:
        """Проверить, нужно ли эскалировать к планировщику"""
        if self.error_tracker:
            return self.error_tracker.should_escalate_to_planner(step_id)
        return False
    
    def should_escalate_to_human(self, step_id: str) -> bool:
        """Проверить, нужно ли эскалировать к человеку"""
        if self.error_tracker:
            return self.error_tracker.should_escalate_to_human(step_id)
        return False
    
    def get_escalation_level(self, step_id: str) -> str:
        """Получить текущий уровень эскалации для шага"""
        if self.error_tracker:
            return self.error_tracker.get_escalation_level(step_id).value
        return "none"
    
    def cleanup_old_error_records(self):
        """Очистка старых записей об ошибках"""
        if self.error_tracker:
            self.error_tracker.cleanup_old_records()
    
    def reset_step_error_stats(self, step_id: str):
        """Сброс статистики ошибок для шага"""
        if self.error_tracker:
            self.error_tracker.reset_step_stats(step_id)
