"""
Task Agent - Модель планирования основных шагов

Этот модуль отвечает за:
- Разбиение задач на основные шаги
- Систему идентификации шагов (step_id)
- Взаимодействие с LLM для планирования
- Интеграцию с Task Master для улучшения промтов
"""
import json
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import logging

from ..config.agent_config import TaskAgentConfig, AgentConfig
from ..models.planning_model import Task, TaskStep, PlanningResult, TaskStatus, StepStatus, Priority
from ..models.llm_interface import LLMInterface, LLMRequest, LLMRequestBuilder, LLMInterfaceFactory
from ..agents.task_master_integration import TaskMasterIntegration, TaskMasterResult
from ..utils.logger import StructuredLogger


@dataclass
class TaskPlanningContext:
    """Контекст для планирования задачи"""
    
    server_info: Dict[str, Any]
    user_requirements: str
    constraints: List[str]
    available_tools: List[str]
    previous_tasks: List[Dict[str, Any]]
    environment: Dict[str, Any]


class TaskAgent:
    """
    Агент планирования основных шагов
    
    Основные возможности:
    - Разбиение задач на логические шаги
    - Генерация уникальных ID для шагов
    - Планирование зависимостей между шагами
    - Интеграция с Task Master для улучшения промтов
    - Валидация и оптимизация планов
    """
    
    def __init__(self, config: AgentConfig, task_master: Optional[TaskMasterIntegration] = None):
        """
        Инициализация Task Agent
        
        Args:
            config: Конфигурация агентов
            task_master: Интеграция с Task Master
        """
        self.config = config
        self.task_agent_config = config.task_agent
        self.task_master = task_master
        self.logger = StructuredLogger("TaskAgent")
        
        # Система подсчета ошибок будет инициализирована отдельно
        self.error_tracker = None
        
        # Создаем интерфейс LLM
        self.llm_interface = LLMInterfaceFactory.create_interface(
            config.llm,
            self.logger,
            mock_mode=False  # В production должно быть False
        )
        
        # Проверяем доступность LLM
        if not self.llm_interface.is_available():
            self.logger.warning("LLM интерфейс недоступен, используется мок-режим")
            self.llm_interface = LLMInterfaceFactory.create_interface(
                config.llm,
                self.logger,
                mock_mode=True
            )
        
        self.logger.info(
            "Task Agent инициализирован",
            model=self.task_agent_config.model,
            max_steps=self.task_agent_config.max_steps,
            task_master_enabled=self.task_master is not None
        )
    
    def plan_task(self, task_description: str, context: Optional[TaskPlanningContext] = None) -> PlanningResult:
        """
        Планирование задачи - разбиение на основные шаги
        
        Args:
            task_description: Описание задачи
            context: Контекст планирования
            
        Returns:
            Результат планирования с разбитой на шаги задачей
        """
        start_time = time.time()
        
        try:
            self.logger.info("Начало планирования задачи", task_description=task_description)
            
            # Создаем базовую задачу
            task = Task(
                title=self._extract_task_title(task_description),
                description=task_description,
                context=context.__dict__ if context else {}
            )
            
            # Генерируем промт для планирования
            planning_prompt = self._build_planning_prompt(task_description, context)
            
            # Улучшаем промт через Task Master если доступен
            if self.task_master:
                improved_result = self._improve_prompt_with_taskmaster(planning_prompt, context)
                if improved_result.success:
                    planning_prompt = improved_result.data.get("improved_prompt", planning_prompt)
                    self.logger.info("Промт улучшен через Task Master")
                else:
                    self.logger.warning("Не удалось улучшить промт через Task Master", error=improved_result.error)
            
            # Отправляем запрос к LLM
            llm_request = LLMRequestBuilder(
                default_model=self.task_agent_config.model,
                default_temperature=self.task_agent_config.temperature
            ).with_system_message(self._get_planning_system_message()).with_context(
                self._build_llm_context(context)
            ).build(planning_prompt, self.task_agent_config.max_tokens)
            
            llm_response = self.llm_interface.generate_response(llm_request)
            
            if not llm_response.success:
                return PlanningResult(
                    success=False,
                    error_message=f"Ошибка LLM: {llm_response.error}",
                    planning_duration=time.time() - start_time
                )
            
            # Парсим ответ LLM и создаем шаги
            steps = self._parse_llm_response(llm_response.content, task.task_id)
            
            if not steps:
                return PlanningResult(
                    success=False,
                    error_message="Не удалось извлечь шаги из ответа LLM",
                    planning_duration=time.time() - start_time
                )
            
            # Добавляем шаги к задаче
            for step in steps:
                task.add_step(step)
            
            # Валидируем план
            validation_result = self._validate_plan(task)
            if not validation_result["valid"]:
                self.logger.warning("План не прошел валидацию", 
                                  issues=validation_result["issues"],
                                  steps_count=validation_result["steps_count"],
                                  dependencies_count=validation_result["dependencies_count"])
                
                # Выводим детали валидации в консоль
                print(f"\n❌ ПЛАН НЕ ПРОШЕЛ ВАЛИДАЦИЮ:")
                print(f"   Шагов: {validation_result['steps_count']}")
                print(f"   Зависимостей: {validation_result['dependencies_count']}")
                print(f"   Проблемы:")
                for issue in validation_result["issues"]:
                    print(f"     • {issue}")
                print()
                # Можно попробовать исправить или вернуть с предупреждением
            
            # Оптимизируем план
            self._optimize_plan(task)
            
            planning_duration = time.time() - start_time
            
            self.logger.info(
                "Планирование завершено",
                task_id=task.task_id,
                steps_count=len(task.steps),
                duration=planning_duration
            )
            
            # Выводим информацию о созданном плане
            print(f"\n📋 СОЗДАН ПЛАН ЗАДАЧИ:")
            print(f"   ID задачи: {task.task_id}")
            print(f"   Шагов: {len(task.steps)}")
            print(f"   Время планирования: {planning_duration:.2f}с")
            print(f"   Шаги:")
            for i, step in enumerate(task.steps, 1):
                print(f"     {i}. {step.title}")
                if step.description:
                    print(f"        {step.description}")
            print()
            
            return PlanningResult(
                success=True,
                task=task,
                planning_duration=planning_duration,
                llm_usage=llm_response.usage,
                metadata={
                    "validation_result": validation_result,
                    "task_master_used": self.task_master is not None
                }
            )
            
        except Exception as e:
            planning_duration = time.time() - start_time
            error_msg = f"Ошибка планирования: {str(e)}"
            self.logger.error("Ошибка планирования задачи", error=error_msg, duration=planning_duration)
            
            return PlanningResult(
                success=False,
                error_message=error_msg,
                planning_duration=planning_duration
            )
    
    def _extract_task_title(self, description: str) -> str:
        """Извлечение заголовка задачи из описания"""
        # Простая логика извлечения заголовка
        lines = description.strip().split('\n')
        first_line = lines[0].strip()
        
        # Ограничиваем длину заголовка
        if len(first_line) > 100:
            first_line = first_line[:97] + "..."
        
        return first_line
    
    def _build_planning_prompt(self, task_description: str, context: Optional[TaskPlanningContext] = None) -> str:
        """Построение промта для планирования"""
        prompt_parts = [
            "Ты - эксперт по планированию задач на Linux серверах. Твоя задача - разбить задачу на логические шаги.",
            "",
            f"ЗАДАЧА: {task_description}",
            "",
            "ТРЕБОВАНИЯ К ПЛАНИРОВАНИЮ:",
            "1. Разбей задачу на 3-10 логических шагов",
            "2. Каждый шаг должен быть конкретным и выполнимым",
            "3. Укажи зависимости между шагами по ИНДЕКСАМ (0, 1, 2, ...), а не по названиям",
            "4. Оцени время выполнения каждого шага в минутах",
            "5. Присвой приоритет каждому шагу (low, medium, high, critical)",
            "6. Шаги должны быть идемпотентными (безопасно выполнять повторно)",
            "",
            "ФОРМАТ ОТВЕТА (строго JSON):",
            "{",
            '  "steps": [',
            '    {',
            '      "title": "Название шага",',
            '      "description": "Подробное описание шага",',
            '      "priority": "high",',
            '      "estimated_duration": 15,',
            '      "dependencies": [0, 1]',
            '    }',
            '  ]',
            "}",
            "",
            "ВАЖНО:",
            "- Отвечай ТОЛЬКО в формате JSON",
            "- Не добавляй никаких комментариев или объяснений",
            "- Убедись что JSON валидный",
            "- Шаги должны быть в логическом порядке выполнения"
        ]
        
        # Добавляем контекст если есть
        if context:
            prompt_parts.extend([
                "",
                "КОНТЕКСТ:",
                f"Информация о сервере: {json.dumps(context.server_info, ensure_ascii=False)}",
                f"Ограничения: {', '.join(context.constraints)}",
                f"Доступные инструменты: {', '.join(context.available_tools)}"
            ])
        
        return "\n".join(prompt_parts)
    
    def _get_planning_system_message(self) -> str:
        """Получение системного сообщения для планирования"""
        return """Ты - эксперт по планированию задач на Linux серверах. 
Твоя задача - создавать детальные, выполнимые планы для автоматизации системных задач.
Всегда отвечай в строгом JSON формате без дополнительных комментариев."""
    
    def _build_llm_context(self, context: Optional[TaskPlanningContext] = None) -> Dict[str, Any]:
        """Построение контекста для LLM"""
        llm_context = {
            "max_steps": self.task_agent_config.max_steps,
            "planning_guidelines": [
                "Шаги должны быть атомарными",
                "Каждый шаг должен иметь четкий критерий успеха",
                "Избегай опасных команд",
                "Учитывай идемпотентность"
            ]
        }
        
        if context:
            llm_context.update({
                "server_info": context.server_info,
                "constraints": context.constraints,
                "available_tools": context.available_tools,
                "environment": context.environment
            })
        
        return llm_context
    
    def _improve_prompt_with_taskmaster(self, prompt: str, context: Optional[TaskPlanningContext] = None) -> TaskMasterResult:
        """Улучшение промта через Task Master"""
        if not self.task_master:
            return TaskMasterResult(success=False, error="Task Master не доступен")
        
        taskmaster_context = {
            "prompt_type": "planning",
            "agent_type": "task_agent",
            "max_steps": self.task_agent_config.max_steps
        }
        
        if context:
            taskmaster_context.update({
                "server_info": context.server_info,
                "constraints": context.constraints
            })
        
        return self.task_master.improve_prompt(prompt, taskmaster_context)
    
    def _parse_llm_response(self, response_content: str, task_id: str) -> List[TaskStep]:
        """Парсинг ответа LLM и создание шагов"""
        try:
            # Очищаем ответ от возможных лишних символов
            cleaned_content = response_content.strip()
            
            # Ищем JSON в ответе
            json_start = cleaned_content.find('{')
            json_end = cleaned_content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                self.logger.error("JSON не найден в ответе LLM", response_preview=cleaned_content[:200])
                return []
            
            json_content = cleaned_content[json_start:json_end]
            
            # Парсим JSON
            data = json.loads(json_content)
            steps_data = data.get("steps", [])
            
            if not steps_data:
                self.logger.error("Шаги не найдены в JSON ответе")
                return []
            
            # Создаем объекты TaskStep
            steps = []
            for i, step_data in enumerate(steps_data):
                try:
                    # Преобразуем зависимости из индексов в ID шагов
                    dependencies = step_data.get("dependencies", [])
                    if dependencies:
                        # Сначала создаем все шаги без зависимостей
                        step = TaskStep(
                            title=step_data.get("title", f"Шаг {i+1}"),
                            description=step_data.get("description", ""),
                            priority=Priority(step_data.get("priority", "medium")),
                            estimated_duration=step_data.get("estimated_duration"),
                            dependencies=[],  # Пока пустые зависимости
                            metadata={
                                "task_id": task_id,
                                "step_order": i + 1,
                                "llm_generated": True
                            }
                        )
                        steps.append(step)
                    else:
                        step = TaskStep(
                            title=step_data.get("title", f"Шаг {i+1}"),
                            description=step_data.get("description", ""),
                            priority=Priority(step_data.get("priority", "medium")),
                            estimated_duration=step_data.get("estimated_duration"),
                            dependencies=[],
                            metadata={
                                "task_id": task_id,
                                "step_order": i + 1,
                                "llm_generated": True
                            }
                        )
                        steps.append(step)
                    
                except Exception as e:
                    self.logger.warning(f"Ошибка создания шага {i+1}", error=str(e))
                    continue
            
            # Теперь устанавливаем зависимости по индексам
            for i, step_data in enumerate(steps_data):
                dependencies = step_data.get("dependencies", [])
                if dependencies and i < len(steps):
                    # Преобразуем индексы в ID шагов
                    step_dependencies = []
                    for dep_index in dependencies:
                        if isinstance(dep_index, int) and 0 <= dep_index < len(steps):
                            step_dependencies.append(steps[dep_index].step_id)
                        else:
                            self.logger.warning(f"Некорректный индекс зависимости: {dep_index}")
                    steps[i].dependencies = step_dependencies
            
            self.logger.info(f"Создано {len(steps)} шагов из ответа LLM")
            return steps
            
        except json.JSONDecodeError as e:
            self.logger.error("Ошибка парсинга JSON ответа LLM", error=str(e), response_preview=response_content[:200])
            return []
        except Exception as e:
            self.logger.error("Неожиданная ошибка при парсинге ответа LLM", error=str(e))
            return []
    
    def _validate_plan(self, task: Task) -> Dict[str, Any]:
        """Валидация плана задачи"""
        issues = []
        
        # Проверяем количество шагов
        if len(task.steps) == 0:
            issues.append("План не содержит шагов")
        elif len(task.steps) > self.task_agent_config.max_steps:
            issues.append(f"Слишком много шагов: {len(task.steps)} > {self.task_agent_config.max_steps}")
        
        # Проверяем зависимости
        step_ids = {step.step_id for step in task.steps}
        for step in task.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    issues.append(f"Шаг {step.step_id} ссылается на несуществующую зависимость {dep}")
        
        # Проверяем циклические зависимости
        if self._has_cyclic_dependencies(task.steps):
            issues.append("Обнаружены циклические зависимости")
        
        # Проверяем что есть хотя бы один шаг без зависимостей
        steps_without_deps = [step for step in task.steps if not step.dependencies]
        if not steps_without_deps:
            issues.append("Нет шагов без зависимостей (план может быть невыполнимым)")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "steps_count": len(task.steps),
            "dependencies_count": sum(len(step.dependencies) for step in task.steps)
        }
    
    def _has_cyclic_dependencies(self, steps: List[TaskStep]) -> bool:
        """Проверка на циклические зависимости"""
        # Создаем граф зависимостей
        graph = {step.step_id: step.dependencies for step in steps}
        
        # Используем DFS для поиска циклов
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for step_id in graph:
            if step_id not in visited:
                if has_cycle(step_id):
                    return True
        
        return False
    
    def _optimize_plan(self, task: Task):
        """Оптимизация плана задачи"""
        # Сортируем шаги по приоритету и зависимостям
        self._sort_steps_by_execution_order(task)
        
        # Обновляем общую оценку времени
        total_duration = sum(
            step.estimated_duration for step in task.steps 
            if step.estimated_duration is not None
        )
        task.total_estimated_duration = total_duration
        
        self.logger.debug(
            "План оптимизирован",
            total_duration=total_duration,
            steps_count=len(task.steps)
        )
    
    def _sort_steps_by_execution_order(self, task: Task):
        """Сортировка шагов в порядке выполнения"""
        # Топологическая сортировка
        sorted_steps = []
        visited = set()
        temp_visited = set()
        
        def visit(step):
            if step.step_id in temp_visited:
                return  # Циклическая зависимость
            if step.step_id in visited:
                return
            
            temp_visited.add(step.step_id)
            
            # Сначала посещаем зависимости
            for dep_id in step.dependencies:
                dep_step = task.get_step(dep_id)
                if dep_step:
                    visit(dep_step)
            
            temp_visited.remove(step.step_id)
            visited.add(step.step_id)
            sorted_steps.append(step)
        
        # Посещаем все шаги
        for step in task.steps:
            if step.step_id not in visited:
                visit(step)
        
        # Обновляем порядок шагов
        task.steps = sorted_steps
        
        # Обновляем порядок в метаданных
        for i, step in enumerate(task.steps):
            step.metadata["execution_order"] = i + 1
    
    def get_task_status(self, task: Task) -> Dict[str, Any]:
        """Получение статуса задачи"""
        return {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status.value,
            "progress": task.get_progress(),
            "steps": [
                {
                    "step_id": step.step_id,
                    "title": step.title,
                    "status": step.status.value,
                    "priority": step.priority.value,
                    "error_count": step.error_count
                }
                for step in task.steps
            ]
        }
    
    def update_step_status(self, task: Task, step_id: str, status: StepStatus, 
                          error_count: Optional[int] = None) -> bool:
        """Обновление статуса шага"""
        step = task.get_step(step_id)
        if not step:
            self.logger.warning(f"Шаг {step_id} не найден в задаче {task.task_id}")
            return False
        
        step.status = status
        
        # Устанавливаем счетчик ошибок до вызова mark_failed()
        if error_count is not None:
            step.error_count = error_count
        
        if status == StepStatus.EXECUTING:
            step.mark_started()
        elif status == StepStatus.COMPLETED:
            step.mark_completed()
        elif status == StepStatus.FAILED:
            # Если error_count не передан, используем mark_failed() для увеличения счетчика
            if error_count is None:
                step.mark_failed()
            # Иначе просто устанавливаем статус (счетчик уже установлен выше)
        
        # Проверяем необходимость эскалации (если система подсчета ошибок доступна)
        if self.error_tracker:
            escalation_level = self.error_tracker.get_escalation_level(step_id)
            if escalation_level.value == "planner_notification":
                self.logger.warning(
                    "Эскалация к планировщику",
                    task_id=task.task_id,
                    step_id=step_id,
                    error_count=step.error_count,
                    escalation_level=escalation_level.value
                )
            elif escalation_level.value == "human_escalation":
                self.logger.error(
                    "Эскалация к человеку",
                    task_id=task.task_id,
                    step_id=step_id,
                    error_count=step.error_count,
                    escalation_level=escalation_level.value
                )
        
        # Обновляем статус задачи
        if task.is_completed():
            task.mark_completed()
        elif task.is_failed():
            task.mark_failed()
        
        self.logger.info(
            "Статус шага обновлен",
            task_id=task.task_id,
            step_id=step_id,
            status=status.value,
            error_count=step.error_count,
            escalation_level=escalation_level.value if self.error_tracker else "none"
        )
        
        return True
    
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
    
    def get_error_tracking_stats(self) -> Dict[str, Any]:
        """Получить статистику системы подсчета ошибок"""
        if self.error_tracker:
            return self.error_tracker.get_global_stats()
        return {"total_errors": 0, "total_attempts": 0, "success_rate": 0.0}
    
    def cleanup_old_error_records(self):
        """Очистка старых записей об ошибках"""
        if self.error_tracker:
            self.error_tracker.cleanup_old_records()
    
    def reset_step_error_stats(self, step_id: str):
        """Сброс статистики ошибок для шага"""
        if self.error_tracker:
            self.error_tracker.reset_step_stats(step_id)
    
    def set_error_tracker(self, error_tracker):
        """Установить систему подсчета ошибок"""
        self.error_tracker = error_tracker
