"""
Task Master Integration для улучшения промтов и планирования задач.

Этот модуль обеспечивает интеграцию с light-task-master для:
- Улучшения промтов через Task Master API
- Парсинга PRD (Product Requirements Document)
- Генерации задач из PRD
- Валидации и форматирования промтов
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging

from ..config.agent_config import TaskmasterConfig
from ..utils.logger import LoggerSetup


@dataclass
class TaskMasterResult:
    """Результат работы Task Master"""
    
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_output: Optional[str] = None


@dataclass
class ParsedPRD:
    """Распарсенный PRD документ"""
    
    overview: str
    core_features: List[Dict[str, str]]
    user_experience: Dict[str, Any]
    technical_architecture: Dict[str, Any]
    development_roadmap: List[Dict[str, Any]]
    risks_and_mitigations: List[Dict[str, str]]
    raw_content: str


@dataclass
class GeneratedTask:
    """Сгенерированная задача из PRD"""
    
    task_id: str
    title: str
    description: str
    priority: str
    estimated_effort: str
    dependencies: List[str]
    acceptance_criteria: List[str]
    subtasks: List[Dict[str, str]]


class TaskMasterIntegration:
    """
    Интеграция с light-task-master для улучшения промтов и планирования.
    
    Основные возможности:
    - Улучшение промтов через Task Master API
    - Парсинг PRD документов
    - Генерация задач из PRD
    - Валидация и форматирование промтов
    """
    
    def __init__(self, config: TaskmasterConfig, project_root: Optional[Path] = None):
        """
        Инициализация Task Master интеграции.
        
        Args:
            config: Конфигурация Task Master
            project_root: Корневая директория проекта (по умолчанию текущая)
        """
        self.config = config
        self.project_root = project_root or Path.cwd()
        self.taskmaster_dir = self.project_root / ".taskmaster"
        self.logger = LoggerSetup.get_logger(__name__)
        
        # Проверяем наличие Task Master только если он включен
        if self.config.enabled:
            self._check_taskmaster_installation()
            
            # Инициализируем Task Master если нужно
            if not self.taskmaster_dir.exists():
                self._initialize_taskmaster()
    
    def _check_taskmaster_installation(self) -> bool:
        """Проверка установки Task Master"""
        try:
            result = subprocess.run(
                ["npx", "task-master-ai", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.info(f"Task Master установлен: {result.stdout.strip()}")
                return True
            else:
                self.logger.warning("Task Master не найден, попытка установки...")
                return self._install_taskmaster()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.error(f"Ошибка проверки Task Master: {e}")
            return False
    
    def _install_taskmaster(self) -> bool:
        """Установка Task Master"""
        try:
            self.logger.info("Установка Task Master...")
            result = subprocess.run(
                ["npm", "install", "-g", "task-master-ai"],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                self.logger.info("Task Master успешно установлен")
                return True
            else:
                self.logger.error(f"Ошибка установки Task Master: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error("Таймаут при установке Task Master")
            return False
    
    def _initialize_taskmaster(self) -> bool:
        """Инициализация Task Master в проекте"""
        try:
            self.logger.info("Инициализация Task Master в проекте...")
            result = subprocess.run(
                ["npx", "task-master-ai", "init", "--rules", "cursor,windsurf,vscode"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                self.logger.info("Task Master успешно инициализирован")
                return True
            else:
                self.logger.error(f"Ошибка инициализации Task Master: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error("Таймаут при инициализации Task Master")
            return False
    
    def improve_prompt(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> TaskMasterResult:
        """
        Улучшение промта через Task Master.
        
        Args:
            prompt: Исходный промт
            context: Дополнительный контекст для улучшения
            
        Returns:
            TaskMasterResult с улучшенным промтом
        """
        if not self.config.enabled:
            self.logger.warning("Task Master отключен, возвращаем исходный промт")
            return TaskMasterResult(
                success=True,
                data={"improved_prompt": prompt, "original_prompt": prompt}
            )
        
        try:
            # Создаем временный файл с промтом
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            # Подготавливаем команду для Task Master
            cmd = [
                "npx", "task-master-ai", "improve-prompt",
                "--input", temp_file,
                "--model", self.config.model,
                "--temperature", str(self.config.temperature),
                "--max-tokens", str(self.config.max_tokens)
            ]
            
            # Добавляем контекст если есть
            if context:
                context_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                json.dump(context, context_file)
                context_file.close()
                cmd.extend(["--context", context_file.name])
            
            # Выполняем команду
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Очищаем временные файлы
            Path(temp_file).unlink(missing_ok=True)
            if context:
                Path(context_file.name).unlink(missing_ok=True)
            
            if result.returncode == 0:
                try:
                    # Пытаемся распарсить JSON ответ
                    improved_data = json.loads(result.stdout)
                    return TaskMasterResult(
                        success=True,
                        data=improved_data,
                        raw_output=result.stdout
                    )
                except json.JSONDecodeError:
                    # Если не JSON, возвращаем как текст
                    return TaskMasterResult(
                        success=True,
                        data={"improved_prompt": result.stdout.strip()},
                        raw_output=result.stdout
                    )
            else:
                return TaskMasterResult(
                    success=False,
                    error=result.stderr,
                    raw_output=result.stdout
                )
                
        except subprocess.TimeoutExpired:
            return TaskMasterResult(
                success=False,
                error="Таймаут при улучшении промта"
            )
        except Exception as e:
            self.logger.error(f"Ошибка при улучшении промта: {e}")
            return TaskMasterResult(
                success=False,
                error=str(e)
            )
    
    def parse_prd(self, prd_path: Optional[Union[str, Path]] = None) -> TaskMasterResult:
        """
        Парсинг PRD документа.
        
        Args:
            prd_path: Путь к PRD файлу (по умолчанию .taskmaster/docs/prd.txt)
            
        Returns:
            TaskMasterResult с распарсенным PRD
        """
        if not self.config.enabled:
            return TaskMasterResult(
                success=False,
                error="Task Master отключен"
            )
        
        # Определяем путь к PRD
        if prd_path is None:
            prd_path = self.taskmaster_dir / "docs" / "prd.txt"
        else:
            prd_path = Path(prd_path)
        
        if not prd_path.exists():
            return TaskMasterResult(
                success=False,
                error=f"PRD файл не найден: {prd_path}"
            )
        
        try:
            # Выполняем парсинг PRD через Task Master
            result = subprocess.run(
                ["npx", "task-master-ai", "parse-prd", str(prd_path)],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                try:
                    parsed_data = json.loads(result.stdout)
                    return TaskMasterResult(
                        success=True,
                        data=parsed_data,
                        raw_output=result.stdout
                    )
                except json.JSONDecodeError:
                    # Если не JSON, возвращаем как текст
                    return TaskMasterResult(
                        success=True,
                        data={"parsed_content": result.stdout.strip()},
                        raw_output=result.stdout
                    )
            else:
                return TaskMasterResult(
                    success=False,
                    error=result.stderr,
                    raw_output=result.stdout
                )
                
        except subprocess.TimeoutExpired:
            return TaskMasterResult(
                success=False,
                error="Таймаут при парсинге PRD"
            )
        except Exception as e:
            self.logger.error(f"Ошибка при парсинге PRD: {e}")
            return TaskMasterResult(
                success=False,
                error=str(e)
            )
    
    def generate_tasks_from_prd(self, prd_path: Optional[Union[str, Path]] = None, 
                               num_tasks: int = 10) -> TaskMasterResult:
        """
        Генерация задач из PRD.
        
        Args:
            prd_path: Путь к PRD файлу
            num_tasks: Количество задач для генерации
            
        Returns:
            TaskMasterResult с сгенерированными задачами
        """
        if not self.config.enabled:
            return TaskMasterResult(
                success=False,
                error="Task Master отключен"
            )
        
        # Определяем путь к PRD
        if prd_path is None:
            prd_path = self.taskmaster_dir / "docs" / "prd.txt"
        else:
            prd_path = Path(prd_path)
        
        if not prd_path.exists():
            return TaskMasterResult(
                success=False,
                error=f"PRD файл не найден: {prd_path}"
            )
        
        try:
            # Генерируем задачи через Task Master
            result = subprocess.run(
                [
                    "npx", "task-master-ai", "generate-tasks",
                    "--prd", str(prd_path),
                    "--num-tasks", str(num_tasks),
                    "--model", self.config.model,
                    "--temperature", str(self.config.temperature)
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode == 0:
                try:
                    tasks_data = json.loads(result.stdout)
                    return TaskMasterResult(
                        success=True,
                        data=tasks_data,
                        raw_output=result.stdout
                    )
                except json.JSONDecodeError:
                    return TaskMasterResult(
                        success=True,
                        data={"generated_tasks": result.stdout.strip()},
                        raw_output=result.stdout
                    )
            else:
                return TaskMasterResult(
                    success=False,
                    error=result.stderr,
                    raw_output=result.stdout
                )
                
        except subprocess.TimeoutExpired:
            return TaskMasterResult(
                success=False,
                error="Таймаут при генерации задач"
            )
        except Exception as e:
            self.logger.error(f"Ошибка при генерации задач: {e}")
            return TaskMasterResult(
                success=False,
                error=str(e)
            )
    
    def validate_prompt(self, prompt: str, prompt_type: str = "general") -> TaskMasterResult:
        """
        Валидация промта через Task Master.
        
        Args:
            prompt: Промт для валидации
            prompt_type: Тип промта (general, planning, execution, error_handling)
            
        Returns:
            TaskMasterResult с результатами валидации
        """
        if not self.config.enabled:
            return TaskMasterResult(
                success=True,
                data={"valid": True, "message": "Task Master отключен, валидация пропущена"}
            )
        
        try:
            # Создаем временный файл с промтом
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            # Выполняем валидацию
            result = subprocess.run(
                [
                    "npx", "task-master-ai", "validate-prompt",
                    "--input", temp_file,
                    "--type", prompt_type,
                    "--model", self.config.model
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Очищаем временный файл
            Path(temp_file).unlink(missing_ok=True)
            
            if result.returncode == 0:
                try:
                    validation_data = json.loads(result.stdout)
                    return TaskMasterResult(
                        success=True,
                        data=validation_data,
                        raw_output=result.stdout
                    )
                except json.JSONDecodeError:
                    return TaskMasterResult(
                        success=True,
                        data={"valid": True, "message": result.stdout.strip()},
                        raw_output=result.stdout
                    )
            else:
                return TaskMasterResult(
                    success=False,
                    error=result.stderr,
                    raw_output=result.stdout
                )
                
        except subprocess.TimeoutExpired:
            return TaskMasterResult(
                success=False,
                error="Таймаут при валидации промта"
            )
        except Exception as e:
            self.logger.error(f"Ошибка при валидации промта: {e}")
            return TaskMasterResult(
                success=False,
                error=str(e)
            )
    
    def format_prompt(self, prompt: str, format_type: str = "structured") -> TaskMasterResult:
        """
        Форматирование промта через Task Master.
        
        Args:
            prompt: Промт для форматирования
            format_type: Тип форматирования (structured, concise, detailed)
            
        Returns:
            TaskMasterResult с отформатированным промтом
        """
        if not self.config.enabled:
            return TaskMasterResult(
                success=True,
                data={"formatted_prompt": prompt}
            )
        
        try:
            # Создаем временный файл с промтом
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            # Выполняем форматирование
            result = subprocess.run(
                [
                    "npx", "task-master-ai", "format-prompt",
                    "--input", temp_file,
                    "--format", format_type,
                    "--model", self.config.model
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Очищаем временный файл
            Path(temp_file).unlink(missing_ok=True)
            
            if result.returncode == 0:
                try:
                    format_data = json.loads(result.stdout)
                    return TaskMasterResult(
                        success=True,
                        data=format_data,
                        raw_output=result.stdout
                    )
                except json.JSONDecodeError:
                    return TaskMasterResult(
                        success=True,
                        data={"formatted_prompt": result.stdout.strip()},
                        raw_output=result.stdout
                    )
            else:
                return TaskMasterResult(
                    success=False,
                    error=result.stderr,
                    raw_output=result.stdout
                )
                
        except subprocess.TimeoutExpired:
            return TaskMasterResult(
                success=False,
                error="Таймаут при форматировании промта"
            )
        except Exception as e:
            self.logger.error(f"Ошибка при форматировании промта: {e}")
            return TaskMasterResult(
                success=False,
                error=str(e)
            )
    
    def get_taskmaster_status(self) -> Dict[str, Any]:
        """
        Получение статуса Task Master.
        
        Returns:
            Словарь со статусом Task Master
        """
        status = {
            "enabled": self.config.enabled,
            "taskmaster_dir_exists": self.taskmaster_dir.exists(),
            "config_file_exists": (self.taskmaster_dir / "config.json").exists(),
            "prd_file_exists": (self.taskmaster_dir / "docs" / "prd.txt").exists(),
            "installation_status": "unknown"
        }
        
        # Проверяем установку
        try:
            result = subprocess.run(
                ["npx", "task-master-ai", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                status["installation_status"] = "installed"
                status["version"] = result.stdout.strip()
            else:
                status["installation_status"] = "not_installed"
        except Exception:
            status["installation_status"] = "error"
        
        return status
    
    def create_custom_prd(self, content: str, filename: str = "custom_prd.txt") -> bool:
        """
        Создание кастомного PRD файла.
        
        Args:
            content: Содержимое PRD
            filename: Имя файла
            
        Returns:
            True если файл создан успешно
        """
        try:
            docs_dir = self.taskmaster_dir / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            
            prd_file = docs_dir / filename
            with open(prd_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"PRD файл создан: {prd_file}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка создания PRD файла: {e}")
            return False
