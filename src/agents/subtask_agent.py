"""
Subtask Agent - Модель планирования малых шагов

Этот модуль отвечает за:
- Разбиение основных шагов на подзадачи
- Генерацию команд Linux
- Систему health-check для команд
- Использование Task Master для детализации планов
"""
import json
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import logging

from ..config.agent_config import SubtaskAgentConfig, AgentConfig
from ..models.planning_model import TaskStep, StepStatus, Priority
from ..models.llm_interface import LLMInterface, LLMRequest, LLMRequestBuilder, LLMInterfaceFactory
from ..agents.task_master_integration import TaskMasterIntegration, TaskMasterResult
from ..utils.logger import StructuredLogger
from ..utils.idempotency_system import IdempotencySystem, IdempotencyCheck


@dataclass
class Subtask:
    """Подзадача для выполнения"""
    
    subtask_id: str
    title: str
    description: str
    commands: List[str]
    health_checks: List[str]
    expected_output: Optional[str] = None
    rollback_commands: List[str] = None
    dependencies: List[str] = None
    timeout: int = 30
    retry_count: int = 0
    max_retries: int = 2
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.rollback_commands is None:
            self.rollback_commands = []
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SubtaskPlanningContext:
    """Контекст для планирования подзадач"""
    
    step: TaskStep
    server_info: Dict[str, Any]
    os_type: str
    installed_services: List[str]
    available_tools: List[str]
    constraints: List[str]
    previous_subtasks: List[Dict[str, Any]]
    environment: Dict[str, Any]


@dataclass
class SubtaskPlanningResult:
    """Результат планирования подзадач"""
    
    success: bool
    subtasks: List[Subtask] = None
    error_message: Optional[str] = None
    planning_duration: Optional[float] = None
    llm_usage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.subtasks is None:
            self.subtasks = []
        if self.metadata is None:
            self.metadata = {}


class SubtaskAgent:
    """
    Агент планирования подзадач
    
    Основные возможности:
    - Разбиение основных шагов на детальные подзадачи
    - Генерация команд Linux для выполнения
    - Создание health-check команд для проверки
    - Интеграция с Task Master для улучшения планов
    - Валидация и оптимизация подзадач
    """
    
    def __init__(self, config: AgentConfig, task_master: Optional[TaskMasterIntegration] = None, 
                 ssh_connector=None):
        """
        Инициализация Subtask Agent
        
        Args:
            config: Конфигурация агентов
            task_master: Интеграция с Task Master
            ssh_connector: SSH коннектор для системы идемпотентности
        """
        self.config = config
        self.subtask_agent_config = config.subtask_agent
        self.task_master = task_master
        self.logger = StructuredLogger("SubtaskAgent")
        
        # Инициализация системы идемпотентности
        if ssh_connector:
            idempotency_config = config.get("idempotency", {})
            self.idempotency_system = IdempotencySystem(ssh_connector, idempotency_config)
        else:
            self.idempotency_system = None
        
        # Создаем интерфейс LLM
        self.llm_interface = LLMInterfaceFactory.create_interface(
            config.llm,
            self.logger,
            mock_mode=False
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
            "Subtask Agent инициализирован",
            model=self.subtask_agent_config.model,
            max_subtasks=self.subtask_agent_config.max_subtasks,
            task_master_enabled=self.task_master is not None
        )
    
    def plan_subtasks(self, step: TaskStep, context: Optional[SubtaskPlanningContext] = None) -> SubtaskPlanningResult:
        """
        Планирование подзадач для основного шага
        
        Args:
            step: Основной шаг для разбиения
            context: Контекст планирования
            
        Returns:
            Результат планирования с подзадачами
        """
        start_time = time.time()
        
        try:
            self.logger.info("Начало планирования подзадач", step_id=step.step_id, step_title=step.title)
            
            # Создаем контекст если не передан
            if context is None:
                context = self._create_default_context(step)
            
            # Генерируем промт для планирования подзадач
            planning_prompt = self._build_subtask_planning_prompt(step, context)
            
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
                default_model=self.subtask_agent_config.model,
                default_temperature=self.subtask_agent_config.temperature
            ).with_system_message(self._get_subtask_planning_system_message()).with_context(
                self._build_llm_context(context)
            ).build(planning_prompt, self.subtask_agent_config.max_tokens)
            
            llm_response = self.llm_interface.generate_response(llm_request)
            
            if not llm_response.success:
                return SubtaskPlanningResult(
                    success=False,
                    error_message=f"Ошибка LLM: {llm_response.error}",
                    planning_duration=time.time() - start_time
                )
            
            # Парсим ответ LLM и создаем подзадачи
            subtasks = self._parse_llm_response(llm_response.content, step.step_id)
            
            if not subtasks:
                return SubtaskPlanningResult(
                    success=False,
                    error_message="Не удалось извлечь подзадачи из ответа LLM",
                    planning_duration=time.time() - start_time
                )
            
            # Валидируем подзадачи
            validation_result = self._validate_subtasks(subtasks, context)
            if not validation_result["valid"]:
                self.logger.warning("Подзадачи не прошли валидацию", issues=validation_result["issues"])
            
            # Оптимизируем подзадачи
            self._optimize_subtasks(subtasks, context)
            
            planning_duration = time.time() - start_time
            
            self.logger.info(
                "Планирование подзадач завершено",
                step_id=step.step_id,
                subtasks_count=len(subtasks),
                duration=planning_duration
            )
            
            return SubtaskPlanningResult(
                success=True,
                subtasks=subtasks,
                planning_duration=planning_duration,
                llm_usage=llm_response.usage,
                metadata={
                    "validation_result": validation_result,
                    "task_master_used": self.task_master is not None,
                    "step_id": step.step_id
                }
            )
            
        except Exception as e:
            planning_duration = time.time() - start_time
            error_msg = f"Ошибка планирования подзадач: {str(e)}"
            self.logger.error("Ошибка планирования подзадач", error=error_msg, duration=planning_duration)
            
            return SubtaskPlanningResult(
                success=False,
                error_message=error_msg,
                planning_duration=planning_duration
            )
    
    def _create_default_context(self, step: TaskStep) -> SubtaskPlanningContext:
        """Создание контекста по умолчанию"""
        return SubtaskPlanningContext(
            step=step,
            server_info={"os": "linux", "arch": "x86_64"},
            os_type="ubuntu",
            installed_services=[],
            available_tools=["apt", "systemctl", "curl", "wget"],
            constraints=[],
            previous_subtasks=[],
            environment={}
        )
    
    def _build_subtask_planning_prompt(self, step: TaskStep, context: SubtaskPlanningContext) -> str:
        """Построение промта для планирования подзадач"""
        prompt_parts = [
            "Ты - эксперт по автоматизации Linux систем. Твоя задача - разбить основной шаг на детальные подзадачи с командами.",
            "",
            f"ОСНОВНОЙ ШАГ: {step.title}",
            f"ОПИСАНИЕ: {step.description}",
            "",
            "ТРЕБОВАНИЯ К ПЛАНИРОВАНИЮ:",
            "1. Разбей шаг на 2-8 конкретных подзадач",
            "2. Каждая подзадача должна содержать точные команды Linux",
            "3. Добавь health-check команды для проверки успешности",
            "4. Укажи ожидаемый результат каждой команды",
            "5. Добавь команды отката (rollback) если необходимо",
            "6. Команды должны быть идемпотентными",
            "7. Учитывай зависимости между подзадачами",
            "",
            "ФОРМАТ ОТВЕТА (строго JSON):",
            "{",
            '  "subtasks": [',
            '    {',
            '      "title": "Название подзадачи",',
            '      "description": "Описание подзадачи",',
            '      "commands": ["команда1", "команда2"],',
            '      "health_checks": ["проверка1", "проверка2"],',
            '      "expected_output": "ожидаемый результат",',
            '      "rollback_commands": ["откат1", "откат2"],',
            '      "dependencies": [],',
            '      "timeout": 30',
            '    }',
            '  ]',
            "}",
            "",
            "ВАЖНО:",
            "- Отвечай ТОЛЬКО в формате JSON",
            "- Команды должны быть готовы к выполнению",
            "- Health-check команды должны проверять успешность",
            "- Учитывай тип ОС и доступные инструменты",
            "- Избегай опасных команд (rm -rf, dd, mkfs и т.д.)"
        ]
        
        # Добавляем контекст
        prompt_parts.extend([
            "",
            "КОНТЕКСТ:",
            f"Тип ОС: {context.os_type}",
            f"Установленные сервисы: {', '.join(context.installed_services)}",
            f"Доступные инструменты: {', '.join(context.available_tools)}",
            f"Ограничения: {', '.join(context.constraints)}"
        ])
        
        return "\n".join(prompt_parts)
    
    def _get_subtask_planning_system_message(self) -> str:
        """Получение системного сообщения для планирования подзадач"""
        return """Ты - эксперт по автоматизации Linux систем и DevOps.
Твоя задача - создавать детальные, выполнимые планы с конкретными командами.
Всегда отвечай в строгом JSON формате без дополнительных комментариев.
Генерируй безопасные, идемпотентные команды с проверками."""
    
    def _build_llm_context(self, context: SubtaskPlanningContext) -> Dict[str, Any]:
        """Построение контекста для LLM"""
        return {
            "max_subtasks": self.subtask_agent_config.max_subtasks,
            "os_type": context.os_type,
            "server_info": context.server_info,
            "installed_services": context.installed_services,
            "available_tools": context.available_tools,
            "constraints": context.constraints,
            "step_priority": context.step.priority.value,
            "planning_guidelines": [
                "Команды должны быть атомарными",
                "Каждая команда должна иметь четкий критерий успеха",
                "Избегай опасных команд",
                "Учитывай идемпотентность",
                "Добавляй проверки работоспособности"
            ]
        }
    
    def _improve_prompt_with_taskmaster(self, prompt: str, context: SubtaskPlanningContext) -> TaskMasterResult:
        """Улучшение промта через Task Master"""
        if not self.task_master:
            return TaskMasterResult(success=False, error="Task Master не доступен")
        
        taskmaster_context = {
            "prompt_type": "subtask_planning",
            "agent_type": "subtask_agent",
            "max_subtasks": self.subtask_agent_config.max_subtasks,
            "os_type": context.os_type,
            "step_title": context.step.title
        }
        
        return self.task_master.improve_prompt(prompt, taskmaster_context)
    
    def _parse_llm_response(self, response_content: str, step_id: str) -> List[Subtask]:
        """Парсинг ответа LLM и создание подзадач"""
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
            subtasks_data = data.get("subtasks", [])
            
            if not subtasks_data:
                self.logger.error("Подзадачи не найдены в JSON ответе")
                return []
            
            # Создаем объекты Subtask
            subtasks = []
            for i, subtask_data in enumerate(subtasks_data):
                try:
                    subtask = Subtask(
                        subtask_id=f"{step_id}_subtask_{i+1}",
                        title=subtask_data.get("title", f"Подзадача {i+1}"),
                        description=subtask_data.get("description", ""),
                        commands=subtask_data.get("commands", []),
                        health_checks=subtask_data.get("health_checks", []),
                        expected_output=subtask_data.get("expected_output"),
                        rollback_commands=subtask_data.get("rollback_commands", []),
                        dependencies=subtask_data.get("dependencies", []),
                        timeout=subtask_data.get("timeout", 30),
                        metadata={
                            "step_id": step_id,
                            "subtask_order": i + 1,
                            "llm_generated": True
                        }
                    )
                    subtasks.append(subtask)
                    
                except Exception as e:
                    self.logger.warning(f"Ошибка создания подзадачи {i+1}", error=str(e))
                    continue
            
            self.logger.info(f"Создано {len(subtasks)} подзадач из ответа LLM")
            return subtasks
            
        except json.JSONDecodeError as e:
            self.logger.error("Ошибка парсинга JSON ответа LLM", error=str(e), response_preview=response_content[:200])
            return []
        except Exception as e:
            self.logger.error("Неожиданная ошибка при парсинге ответа LLM", error=str(e))
            return []
    
    def _validate_subtasks(self, subtasks: List[Subtask], context: SubtaskPlanningContext) -> Dict[str, Any]:
        """Валидация подзадач"""
        issues = []
        
        # Проверяем количество подзадач
        if len(subtasks) == 0:
            issues.append("Нет подзадач")
        elif len(subtasks) > self.subtask_agent_config.max_subtasks:
            issues.append(f"Слишком много подзадач: {len(subtasks)} > {self.subtask_agent_config.max_subtasks}")
        
        # Проверяем каждую подзадачу
        for i, subtask in enumerate(subtasks):
            if not subtask.commands:
                issues.append(f"Подзадача {i+1} не содержит команд")
            
            if not subtask.health_checks:
                issues.append(f"Подзадача {i+1} не содержит health-check команд")
            
            # Проверяем опасные команды
            for command in subtask.commands:
                if self._is_dangerous_command(command):
                    issues.append(f"Подзадача {i+1} содержит опасную команду: {command}")
        
        # Проверяем зависимости
        subtask_ids = {subtask.subtask_id for subtask in subtasks}
        for subtask in subtasks:
            for dep in subtask.dependencies:
                if dep not in subtask_ids:
                    issues.append(f"Подзадача {subtask.subtask_id} ссылается на несуществующую зависимость {dep}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "subtasks_count": len(subtasks),
            "total_commands": sum(len(subtask.commands) for subtask in subtasks),
            "total_health_checks": sum(len(subtask.health_checks) for subtask in subtasks)
        }
    
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
    
    def _optimize_subtasks(self, subtasks: List[Subtask], context: SubtaskPlanningContext):
        """Оптимизация подзадач"""
        # Сортируем подзадачи по зависимостям
        self._sort_subtasks_by_dependencies(subtasks)
        
        # Добавляем общие проверки если нужно
        self._add_common_health_checks(subtasks, context)
        
        # Улучшаем подзадачи идемпотентностью
        if self.idempotency_system:
            for i, subtask in enumerate(subtasks):
                subtasks[i] = self.enhance_subtask_with_idempotency(subtask)
        
        self.logger.debug(
            "Подзадачи оптимизированы",
            subtasks_count=len(subtasks),
            total_commands=sum(len(subtask.commands) for subtask in subtasks),
            idempotency_enabled=self.idempotency_system is not None
        )
    
    def _sort_subtasks_by_dependencies(self, subtasks: List[Subtask]):
        """Сортировка подзадач по зависимостям"""
        # Топологическая сортировка
        sorted_subtasks = []
        visited = set()
        temp_visited = set()
        
        def visit(subtask):
            if subtask.subtask_id in temp_visited:
                return  # Циклическая зависимость
            if subtask.subtask_id in visited:
                return
            
            temp_visited.add(subtask.subtask_id)
            
            # Сначала посещаем зависимости
            for dep_id in subtask.dependencies:
                dep_subtask = next((s for s in subtasks if s.subtask_id == dep_id), None)
                if dep_subtask:
                    visit(dep_subtask)
            
            temp_visited.remove(subtask.subtask_id)
            visited.add(subtask.subtask_id)
            sorted_subtasks.append(subtask)
        
        # Посещаем все подзадачи
        for subtask in subtasks:
            if subtask.subtask_id not in visited:
                visit(subtask)
        
        # Обновляем порядок
        subtasks.clear()
        subtasks.extend(sorted_subtasks)
        
        # Обновляем порядок в метаданных
        for i, subtask in enumerate(subtasks):
            subtask.metadata["execution_order"] = i + 1
    
    def _add_common_health_checks(self, subtasks: List[Subtask], context: SubtaskPlanningContext):
        """Добавление общих health-check команд"""
        # Добавляем проверку доступности системы
        for subtask in subtasks:
            if not any("systemctl" in check for check in subtask.health_checks):
                # Если есть команды с systemctl, добавляем проверку
                if any("systemctl" in cmd for cmd in subtask.commands):
                    subtask.health_checks.append("systemctl is-system-running")
            
            # Добавляем проверку дискового пространства для команд установки
            if any("install" in cmd or "apt" in cmd for cmd in subtask.commands):
                if not any("df" in check for check in subtask.health_checks):
                    subtask.health_checks.append("df -h | grep -E '^/dev/' | awk '{print $5}' | sed 's/%//' | awk '$1 > 90 {exit 1}'")
    
    def get_subtask_status(self, subtasks: List[Subtask]) -> Dict[str, Any]:
        """Получение статуса подзадач"""
        return {
            "subtasks_count": len(subtasks),
            "total_commands": sum(len(subtask.commands) for subtask in subtasks),
            "total_health_checks": sum(len(subtask.health_checks) for subtask in subtasks),
            "subtasks": [
                {
                    "subtask_id": subtask.subtask_id,
                    "title": subtask.title,
                    "commands_count": len(subtask.commands),
                    "health_checks_count": len(subtask.health_checks),
                    "dependencies": subtask.dependencies,
                    "timeout": subtask.timeout
                }
                for subtask in subtasks
            ]
        }
    
    def generate_health_check_commands(self, subtask: Subtask, context: SubtaskPlanningContext) -> List[str]:
        """Генерация дополнительных health-check команд"""
        health_checks = []
        
        # Проверки для команд установки
        if any("install" in cmd for cmd in subtask.commands):
            health_checks.extend([
                "dpkg -l | grep -E '^ii' | wc -l",  # Количество установленных пакетов
                "apt list --installed | wc -l"  # Альтернативная проверка
            ])
        
        # Проверки для команд с systemctl
        if any("systemctl" in cmd for cmd in subtask.commands):
            health_checks.extend([
                "systemctl is-system-running",
                "systemctl --failed | grep -v '0 loaded units listed'"
            ])
        
        # Проверки для команд с docker
        if any("docker" in cmd for cmd in subtask.commands):
            health_checks.extend([
                "docker ps",
                "docker system df"
            ])
        
        # Проверки для команд с nginx
        if any("nginx" in cmd for cmd in subtask.commands):
            health_checks.extend([
                "nginx -t",  # Проверка конфигурации
                "curl -I http://localhost"
            ])
        
        return health_checks
    
    def generate_idempotent_commands(self, subtask: Subtask) -> List[str]:
        """Генерация идемпотентных команд для подзадачи"""
        if not self.idempotency_system:
            return subtask.commands
        
        idempotent_commands = []
        
        for command in subtask.commands:
            # Определяем тип команды и цель
            command_type, target = self._analyze_command(command)
            
            if command_type and target:
                # Генерируем идемпотентную команду
                idempotent_cmd, checks = self.idempotency_system.generate_idempotent_command(
                    command, command_type, target
                )
                idempotent_commands.append(idempotent_cmd)
                
                # Добавляем проверки идемпотентности в метаданные
                if not hasattr(subtask, 'idempotency_checks'):
                    subtask.idempotency_checks = []
                subtask.idempotency_checks.extend(checks)
            else:
                # Если не можем определить тип, оставляем команду как есть
                idempotent_commands.append(command)
        
        self.logger.info(
            "Сгенерированы идемпотентные команды",
            subtask_id=subtask.subtask_id,
            original_commands=len(subtask.commands),
            idempotent_commands=len(idempotent_commands)
        )
        
        return idempotent_commands
    
    def _analyze_command(self, command: str) -> tuple:
        """Анализ команды для определения типа и цели"""
        command_lower = command.lower().strip()
        
        # Установка пакетов
        if command_lower.startswith(('apt-get install', 'apt install', 'yum install', 'dnf install')):
            package_name = self._extract_package_name(command)
            if package_name:
                return "install_package", package_name
        
        # Создание файлов
        elif command_lower.startswith('touch'):
            file_path = self._extract_file_path(command)
            if file_path:
                return "create_file", file_path
        
        # Создание директорий
        elif command_lower.startswith('mkdir'):
            dir_path = self._extract_directory_path(command)
            if dir_path:
                return "create_directory", dir_path
        
        # Запуск сервисов
        elif command_lower.startswith(('systemctl start', 'service start')):
            service_name = self._extract_service_name(command)
            if service_name:
                return "start_service", service_name
        
        # Включение сервисов
        elif command_lower.startswith('systemctl enable'):
            service_name = self._extract_service_name(command)
            if service_name:
                return "enable_service", service_name
        
        # Создание пользователей
        elif command_lower.startswith('useradd'):
            username = self._extract_username(command)
            if username:
                return "create_user", username
        
        # Создание групп
        elif command_lower.startswith('groupadd'):
            groupname = self._extract_groupname(command)
            if groupname:
                return "create_group", groupname
        
        return None, None
    
    def _extract_package_name(self, command: str) -> Optional[str]:
        """Извлечение имени пакета из команды установки"""
        import re
        patterns = [
            r'apt-get install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)',
            r'apt install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)',
            r'yum install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)',
            r'dnf install[^a-zA-Z0-9-]*([a-zA-Z0-9-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)
        return None
    
    def _extract_file_path(self, command: str) -> Optional[str]:
        """Извлечение пути к файлу из команды"""
        import re
        match = re.search(r'touch\s+([^\s]+)', command)
        if match:
            return match.group(1)
        return None
    
    def _extract_directory_path(self, command: str) -> Optional[str]:
        """Извлечение пути к директории из команды"""
        import re
        match = re.search(r'mkdir\s+(-p\s+)?([^\s]+)', command)
        if match:
            return match.group(2)
        return None
    
    def _extract_service_name(self, command: str) -> Optional[str]:
        """Извлечение имени сервиса из команды"""
        import re
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
    
    def enhance_subtask_with_idempotency(self, subtask: Subtask) -> Subtask:
        """Улучшение подзадачи с помощью идемпотентности"""
        if not self.idempotency_system:
            return subtask
        
        # Генерируем идемпотентные команды
        idempotent_commands = self.generate_idempotent_commands(subtask)
        
        # Создаем улучшенную подзадачу
        enhanced_subtask = Subtask(
            subtask_id=subtask.subtask_id,
            title=subtask.title,
            description=subtask.description,
            commands=idempotent_commands,
            health_checks=subtask.health_checks,
            expected_output=subtask.expected_output,
            rollback_commands=subtask.rollback_commands,
            dependencies=subtask.dependencies,
            timeout=subtask.timeout,
            retry_count=subtask.retry_count,
            max_retries=subtask.max_retries,
            metadata={
                **subtask.metadata,
                "idempotent_enhanced": True,
                "original_commands": subtask.commands,
                "idempotency_checks": getattr(subtask, 'idempotency_checks', [])
            }
        )
        
        self.logger.info(
            "Подзадача улучшена идемпотентностью",
            subtask_id=subtask.subtask_id,
            enhanced_commands=len(idempotent_commands)
        )
        
        return enhanced_subtask

