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
from ..utils.idempotency_system import IdempotencySystem, IdempotencyCheck
from ..utils.dry_run_system import DryRunSystem, DryRunResult
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
        
        # Инициализация системы идемпотентности (отключена для упрощения)
        self.idempotency_system = None
        
        # Инициализация системы dry-run
        self.dry_run_system = DryRunSystem(self.logger)
        
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
    
    async def execute_subtask(self, context: ExecutionContext) -> SubtaskExecutionResult:
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
            # Выводим информацию о выполнении
            print(f"\n⚡ ВЫПОЛНЕНИЕ ПОДЗАДАЧИ '{subtask.title}':")
            print(f"   ID: {subtask.subtask_id}")
            print(f"   Команд: {len(subtask.commands)}")
            print(f"   Health-check: {len(subtask.health_checks)}")
            if subtask.commands:
                print(f"   Команды:")
                for i, cmd in enumerate(subtask.commands, 1):
                    print(f"     {i}. {cmd}")
            print()
            
            # Выполняем команды подзадачи
            commands_results = await self._execute_commands(subtask.commands, context)
            
            # Проверяем успешность выполнения команд
            commands_success = all(cmd.success for cmd in commands_results)
            
            if not commands_success and self.executor_config.auto_correction_enabled:
                # Пытаемся исправить ошибки
                self.logger.info("Применение автокоррекции", subtask_id=subtask.subtask_id)
                corrected_results = await self._apply_autocorrection(commands_results, context)
                if corrected_results:
                    commands_results = corrected_results
                    commands_success = all(cmd.success for cmd in commands_results)
            
            # Выполняем health-check команды
            health_check_results = []
            if commands_success:
                health_check_results = await self._execute_health_checks(subtask.health_checks, context)
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
            
            # Выводим результаты выполнения
            print(f"📊 РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ:")
            print(f"   Команды: {'✅ Успешно' if commands_success else '❌ Ошибки'}")
            if health_check_results:
                health_success = all(cmd.success for cmd in health_check_results)
                print(f"   Health-check: {'✅ Успешно' if health_success else '❌ Ошибки'}")
            print(f"   Общий результат: {'✅ Успешно' if overall_success else '❌ Ошибки'}")
            
            # Выводим детали выполнения каждой команды
            print(f"   Детали выполнения команд:")
            for i, cmd in enumerate(commands_results, 1):
                status = "✅" if cmd.success else "❌"
                print(f"     {i}. {status} {cmd.command}")
                if cmd.stdout:
                    print(f"        Вывод: {cmd.stdout[:100]}{'...' if len(cmd.stdout) > 100 else ''}")
                if not cmd.success and cmd.stderr:
                    print(f"        Ошибка: {cmd.stderr[:100]}{'...' if len(cmd.stderr) > 100 else ''}")
                if not cmd.success:
                    print(f"        Код выхода: {cmd.exit_code}")
            
            if not commands_success:
                failed_commands = [cmd for cmd in commands_results if not cmd.success]
                print(f"   Неудачные команды:")
                for cmd in failed_commands:
                    print(f"     • {cmd.command} (код: {cmd.exit_code})")
                    if cmd.stderr:
                        print(f"       Ошибка: {cmd.stderr[:100]}{'...' if len(cmd.stderr) > 100 else ''}")
            print()
            
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
            
            # Выводим детали ошибки в консоль
            print(f"\n❌ ОШИБКА ВЫПОЛНЕНИЯ ПОДЗАДАЧИ '{subtask.title}':")
            print(f"   ID: {subtask.subtask_id}")
            print(f"   Тип ошибки: {type(e).__name__}")
            print(f"   Сообщение: {str(e)}")
            print(f"   Время выполнения: {total_duration:.2f}с")
            print(f"   Команд: {len(subtask.commands)}")
            print(f"   Health-check: {len(subtask.health_checks)}")
            print()
            
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
    
    async def _execute_commands(self, commands: List[str], context: ExecutionContext) -> List[CommandResult]:
        """Выполнение списка команд с интегрированной проверкой безопасности и идемпотентности"""
        results = []
        
        for i, command in enumerate(commands):
            # Проверяем, что command является строкой
            if not isinstance(command, str):
                self.logger.warning("Команда не является строкой", 
                                  command=command, 
                                  command_type=type(command).__name__,
                                  order=i+1)
                # Пропускаем невалидную команду
                continue
                
            self.logger.debug("Выполнение команды", command=command, order=i+1)
            
            # Контекст для валидации команды
            validation_context = {
                'step_id': getattr(context, 'step_id', None),
                'task_id': getattr(context, 'task_id', None),
                'subtask_id': context.subtask.subtask_id,
                'command_index': i,
                'server_info': context.server_info
            }
            
            # Проверяем идемпотентность команды
            idempotency_checks = self._extract_idempotency_checks(command)
            if idempotency_checks and self.check_command_idempotency(command, idempotency_checks):
                self.logger.info("Команда пропущена из-за идемпотентности", command=command)
                # Создаем фиктивный успешный результат
                result = CommandResult(
                    command=command,
                    success=True,
                    exit_code=0,
                    stdout=f"[IDEMPOTENT] Команда '{command}' пропущена - состояние уже достигнуто",
                    duration=0.0,
                    status=ExecutionStatus.COMPLETED,
                    metadata={
                        "idempotent_skip": True,
                        "execution_timestamp": datetime.now().isoformat()
                    }
                )
                results.append(result)
                continue
            
            # Проверяем режим dry-run
            if self.executor_config.dry_run_mode:
                result = self._simulate_command_execution(command, validation_context)
            else:
                result = await self._execute_single_command(command, context, validation_context)
            
            results.append(result)
            
            # Если команда не удалась и это критично, прерываем выполнение
            if not result.success and self._is_critical_command(command):
                self.logger.warning("Критическая команда не выполнена, прерывание", command=command)
                break
            
            # Небольшая пауза между командами
            time.sleep(0.1)
        
        return results
    
    async def _execute_single_command(self, command: str, context: ExecutionContext, validation_context: Dict[str, Any] = None) -> CommandResult:
        """Выполнение одной команды"""
        start_time = time.time()
        
        try:
            # Выполняем команду через SSH с передачей контекста валидации
            result = await context.ssh_connection.execute_command(
                command, 
                timeout=self.executor_config.command_timeout,
                context=validation_context
            )
            
            duration = time.time() - start_time
            success = result.exit_code == 0
            
            command_result = CommandResult(
                command=command,
                success=success,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
                error_message=result.stderr if not success else None,
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
                    exit_code=result.exit_code,
                    error_message=result.stderr if not success else None,
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
                exit_code=result.exit_code,
                duration=duration,
                stdout_length=len(result.stdout) if result.stdout else 0,
                stderr_length=len(result.stderr) if result.stderr else 0
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
    
    async def _execute_health_checks(self, health_checks: List[str], context: ExecutionContext) -> List[CommandResult]:
        """Выполнение health-check команд"""
        results = []
        
        for health_check in health_checks:
            self.logger.debug("Выполнение health-check", command=health_check)
            
            if self.executor_config.dry_run_mode:
                result = self._simulate_health_check(health_check)
            else:
                result = await self._execute_single_command(health_check, context)
            
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
    
    async def _execute_rollback(self, rollback_commands: List[str], context: ExecutionContext) -> List[CommandResult]:
        """Выполнение команд отката"""
        self.logger.info("Выполнение отката", commands_count=len(rollback_commands))
        
        results = []
        for rollback_command in rollback_commands:
            self.logger.debug("Выполнение команды отката", command=rollback_command)
            
            if self.executor_config.dry_run_mode:
                result = self._simulate_command_execution(rollback_command)
            else:
                result = await self._execute_single_command(rollback_command, context)
            
            results.append(result)
            
            # Небольшая пауза между командами отката
            time.sleep(0.1)
        
        return results
    
    async def _apply_autocorrection(self, failed_results: List[CommandResult], context: ExecutionContext) -> Optional[List[CommandResult]]:
        """Применение автокоррекции для исправления ошибок"""
        corrected_results = []
        corrections_applied = False
        
        for result in failed_results:
            if result.success:
                corrected_results.append(result)
                continue
            
            # Используем новый движок автокоррекции
            autocorrection_result = await self.autocorrection_engine.correct_command(result, context)
            
            if autocorrection_result.success and autocorrection_result.final_command:
                self.logger.info(
                    "Применение автокоррекции",
                    original_command=result.command,
                    corrected_command=autocorrection_result.final_command,
                    attempts=autocorrection_result.total_attempts
                )
                
                # Выполняем исправленную команду
                corrected_result = await self._execute_single_command(autocorrection_result.final_command, context)
                corrected_result.retry_count = getattr(result, 'retry_count', 0) + 1
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
                        error_message=getattr(corrected_result, 'error_message', None),
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
        self.execution_stats["retry_attempts"] += sum(getattr(r, 'retry_count', 0) for r in all_results)
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
    
    def create_idempotency_snapshot(self, task_id: str):
        """Создание снимка состояния для идемпотентности"""
        return self.idempotency_system.create_state_snapshot(task_id)
    
    def generate_idempotent_command(self, base_command: str, command_type: str, target: str, **kwargs):
        """Генерация идемпотентной команды"""
        return self.idempotency_system.generate_idempotent_command(base_command, command_type, target, **kwargs)
    
    def check_command_idempotency(self, command: str, checks: List[IdempotencyCheck]) -> bool:
        """Проверка необходимости пропуска команды из-за идемпотентности"""
        return self.idempotency_system.should_skip_command(command, checks)
    
    def execute_idempotency_rollback(self, snapshot_id: str):
        """Выполнение отката на основе снимка состояния"""
        return self.idempotency_system.execute_rollback(snapshot_id)
    
    def get_idempotency_status(self):
        """Получение статуса системы идемпотентности"""
        return self.idempotency_system.get_system_status()
    
    def _extract_idempotency_checks(self, command: str) -> List[IdempotencyCheck]:
        """Извлечение проверок идемпотентности из команды"""
        checks = []
        
        # Проверяем, что command является строкой
        if not isinstance(command, str):
            self.logger.warning("Команда не является строкой", command_type=type(command).__name__)
            return checks
        
        # Анализируем команду и определяем тип
        command_lower = command.lower().strip()
        
        # Проверка установки пакетов
        if command_lower.startswith(('apt-get install', 'apt install', 'yum install', 'dnf install')):
            package_name = self._extract_package_name(command)
            if package_name:
                checks.append(self.idempotency_system._create_package_check(package_name))
        
        # Проверка создания файлов
        elif (command_lower.startswith('touch ') or command_lower.startswith('echo ')) and '>' in command:
            file_path = self._extract_file_path(command)
            if file_path:
                checks.append(self.idempotency_system._create_file_check(file_path))
        
        # Проверка создания директорий
        elif command_lower.startswith('mkdir'):
            dir_path = self._extract_directory_path(command)
            if dir_path:
                checks.append(self.idempotency_system._create_directory_check(dir_path))
        
        # Проверка запуска сервисов
        elif command_lower.startswith(('systemctl start', 'service start')):
            service_name = self._extract_service_name(command)
            if service_name:
                checks.append(self.idempotency_system._create_service_check(service_name))
        
        # Проверка включения сервисов
        elif command_lower.startswith('systemctl enable'):
            service_name = self._extract_service_name(command)
            if service_name:
                checks.append(self.idempotency_system._create_service_enabled_check(service_name))
        
        # Проверка создания пользователей
        elif command_lower.startswith('useradd'):
            username = self._extract_username(command)
            if username:
                checks.append(self.idempotency_system._create_user_check(username))
        
        # Проверка создания групп
        elif command_lower.startswith('groupadd'):
            groupname = self._extract_groupname(command)
            if groupname:
                checks.append(self.idempotency_system._create_group_check(groupname))
        
        return checks
    
    def _extract_package_name(self, command: str) -> Optional[str]:
        """Извлечение имени пакета из команды установки"""
        import re
        # Паттерны для различных менеджеров пакетов
        patterns = [
            r'apt-get install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)',
            r'apt install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)',
            r'yum install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)',
            r'dnf install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)'
        ]
lear        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)
        return None
    
    def _extract_file_path(self, command: str) -> Optional[str]:
        """Извлечение пути к файлу из команды"""
        import re
        # Паттерны для создания файлов
        patterns = [
            r'touch\s+([^\s]+)',
            r'echo\s+.*>\s*([^\s]+)',
            r'echo\s+.*>>\s*([^\s]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)
        return None
    
    def _extract_directory_path(self, command: str) -> Optional[str]:
        """Извлечение пути к директории из команды"""
        import re
        # Паттерн для создания директорий
        match = re.search(r'mkdir\s+(-p\s+)?([^\s]+)', command)
        if match:
            return match.group(2)
        return None
    
    def _extract_service_name(self, command: str) -> Optional[str]:
        """Извлечение имени сервиса из команды"""
        import re
        # Паттерны для работы с сервисами
        patterns = [
            r'systemctl start\s+([^\s]+)',
            r'systemctl enable\s+([^\s]+)',
            r'service\s+([^\s]+)\s+start'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)
        return None
    
    def _extract_username(self, command: str) -> Optional[str]:
        """Извлечение имени пользователя из команды"""
        import re
        match = re.search(r'useradd\s+([^\s]+)', command)
        if match:
            return match.group(1)
        return None
    
    def _extract_groupname(self, command: str) -> Optional[str]:
        """Извлечение имени группы из команды"""
        import re
        match = re.search(r'groupadd\s+([^\s]+)', command)
        if match:
            return match.group(1)
        return None
    
    def preview_execution(self, context: ExecutionContext) -> DryRunResult:
        """
        Предварительный просмотр выполнения подзадачи (dry-run)
        
        Args:
            context: Контекст выполнения
            
        Returns:
            Результат предварительного просмотра
        """
        subtask = context.subtask
        
        self.logger.info(
            "Начало предварительного просмотра",
            subtask_id=subtask.subtask_id,
            title=subtask.title,
            commands_count=len(subtask.commands)
        )
        
        # Создаем контекст для dry-run
        dry_run_context = {
            "subtask_id": subtask.subtask_id,
            "subtask_title": subtask.title,
            "server_info": context.server_info,
            "step_id": getattr(context, 'step_id', None),
            "task_id": getattr(context, 'task_id', None)
        }
        
        # Симулируем выполнение команд
        all_commands = subtask.commands + subtask.health_checks + subtask.rollback_commands
        dry_run_result = self.dry_run_system.simulate_execution(all_commands, dry_run_context)
        
        # Добавляем информацию о подзадаче
        dry_run_result.metadata.update({
            "subtask_id": subtask.subtask_id,
            "subtask_title": subtask.title,
            "subtask_description": subtask.description,
            "main_commands": len(subtask.commands),
            "health_checks": len(subtask.health_checks),
            "rollback_commands": len(subtask.rollback_commands)
        })
        
        self.logger.info(
            "Предварительный просмотр завершен",
            subtask_id=subtask.subtask_id,
            success=dry_run_result.success,
            risk_level=dry_run_result.risk_summary.get("overall_risk", "unknown")
        )
        
        return dry_run_result
    
    def validate_plan(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Валидация плана выполнения подзадачи
        
        Args:
            context: Контекст выполнения
            
        Returns:
            Результат валидации плана
        """
        subtask = context.subtask
        
        self.logger.info(
            "Начало валидации плана",
            subtask_id=subtask.subtask_id,
            title=subtask.title
        )
        
        # Создаем контекст для валидации
        validation_context = {
            "subtask_id": subtask.subtask_id,
            "subtask_title": subtask.title,
            "server_info": context.server_info,
            "step_id": getattr(context, 'step_id', None),
            "task_id": getattr(context, 'task_id', None)
        }
        
        # Анализируем команды
        all_commands = subtask.commands + subtask.health_checks + subtask.rollback_commands
        dry_run_result = self.dry_run_system.simulate_execution(all_commands, validation_context)
        
        # Извлекаем результат валидации
        validation_result = dry_run_result.validation_result
        
        if validation_result:
            result = {
                "valid": validation_result.valid,
                "issues": validation_result.issues,
                "warnings": validation_result.warnings,
                "risk_assessment": validation_result.risk_assessment,
                "estimated_duration": validation_result.estimated_duration,
                "recommendations": validation_result.recommendations,
                "commands_analysis": [
                    {
                        "command": analysis.command,
                        "command_type": analysis.command_type.value,
                        "risk_level": analysis.risk_level.value,
                        "potential_issues": analysis.potential_issues,
                        "dependencies": analysis.dependencies,
                        "side_effects": analysis.side_effects,
                        "requires_confirmation": analysis.requires_confirmation
                    }
                    for analysis in validation_result.commands_analysis
                ]
            }
        else:
            result = {
                "valid": False,
                "issues": ["Не удалось выполнить валидацию плана"],
                "warnings": [],
                "risk_assessment": {},
                "estimated_duration": 0.0,
                "recommendations": [],
                "commands_analysis": []
            }
        
        self.logger.info(
            "Валидация плана завершена",
            subtask_id=subtask.subtask_id,
            valid=result["valid"],
            issues_count=len(result["issues"]),
            warnings_count=len(result["warnings"])
        )
        
        return result
    
    def generate_execution_report(self, context: ExecutionContext, format: str = "text") -> str:
        """
        Генерация отчета о планируемом выполнении
        
        Args:
            context: Контекст выполнения
            format: Формат отчета (text, json, markdown)
            
        Returns:
            Отчет в указанном формате
        """
        subtask = context.subtask
        
        self.logger.info(
            "Генерация отчета о выполнении",
            subtask_id=subtask.subtask_id,
            format=format
        )
        
        # Получаем результат dry-run
        dry_run_result = self.preview_execution(context)
        
        # Генерируем отчет
        report = self.dry_run_system.generate_dry_run_report(dry_run_result, format)
        
        self.logger.info(
            "Отчет сгенерирован",
            subtask_id=subtask.subtask_id,
            report_length=len(report)
        )
        
        return report
    
    def get_dry_run_summary(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Получение краткой сводки dry-run выполнения
        
        Args:
            context: Контекст выполнения
            
        Returns:
            Краткая сводка
        """
        subtask = context.subtask
        
        # Получаем результат dry-run
        dry_run_result = self.preview_execution(context)
        
        summary = {
            "subtask_id": subtask.subtask_id,
            "subtask_title": subtask.title,
            "success": dry_run_result.success,
            "execution_summary": dry_run_result.execution_summary,
            "risk_summary": dry_run_result.risk_summary,
            "requires_confirmation": dry_run_result.risk_summary.get("requires_confirmation", False),
            "estimated_duration": dry_run_result.execution_summary.get("estimated_total_duration", 0.0),
            "recommendations": dry_run_result.recommendations[:3],  # Только первые 3 рекомендации
            "metadata": dry_run_result.metadata
        }
        
        return summary
