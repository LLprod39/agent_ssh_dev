"""
Система автокоррекции для SSH Agent

Этот модуль содержит:
- Стратегии автокоррекции ошибок
- Проверку синтаксических ошибок
- Альтернативные флаги команд
- Проверку сетевого соединения
- Перезапуск сервисов
- Систему локальных попыток исправления
"""
import re
import time
import socket
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum
import logging

from ..models.command_result import CommandResult, ExecutionStatus
from ..models.execution_context import ExecutionContext
from ..utils.logger import StructuredLogger


class CorrectionStrategy(Enum):
    """Стратегии автокоррекции"""
    SYNTAX_CHECK = "syntax_check"
    ALTERNATIVE_FLAGS = "alternative_flags"
    NETWORK_CHECK = "network_check"
    SERVICE_RESTART = "service_restart"
    PERMISSION_FIX = "permission_fix"
    PACKAGE_UPDATE = "package_update"
    PATH_CORRECTION = "path_correction"
    COMMAND_SUBSTITUTION = "command_substitution"


@dataclass
class CorrectionAttempt:
    """Попытка исправления команды"""
    
    original_command: str
    corrected_command: str
    strategy: CorrectionStrategy
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AutocorrectionResult:
    """Результат автокоррекции"""
    
    success: bool
    final_command: Optional[str] = None
    attempts: List[CorrectionAttempt] = None
    total_attempts: int = 0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []


class AutocorrectionEngine:
    """
    Движок автокоррекции команд
    
    Основные возможности:
    - Проверка синтаксических ошибок
    - Альтернативные флаги команд
    - Проверка сетевого соединения
    - Перезапуск сервисов
    - Система локальных попыток исправления
    """
    
    def __init__(self, max_attempts: int = 3, timeout: int = 30):
        """
        Инициализация движка автокоррекции
        
        Args:
            max_attempts: Максимальное количество попыток исправления
            timeout: Таймаут для сетевых проверок
        """
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.logger = StructuredLogger("AutocorrectionEngine")
        
        # Словарь альтернативных флагов для команд
        self.alternative_flags = {
            "ls": {
                "default": ["-la", "-l", "-a", "-lh"],
                "fallback": ["-1", "-F", "-G"]
            },
            "grep": {
                "default": ["-r", "-i", "-n", "-v"],
                "fallback": ["-E", "-F", "-P"]
            },
            "find": {
                "default": ["-name", "-type", "-size"],
                "fallback": ["-iname", "-path", "-regex"]
            },
            "systemctl": {
                "default": ["start", "stop", "restart", "status"],
                "fallback": ["reload", "reload-or-restart", "try-restart"]
            },
            "docker": {
                "default": ["run", "start", "stop", "ps"],
                "fallback": ["exec", "logs", "inspect"]
            },
            "apt": {
                "default": ["install", "update", "upgrade", "remove"],
                "fallback": ["autoremove", "purge", "search"]
            }
        }
        
        # Словарь замен команд
        self.command_substitutions = {
            "service": "systemctl",
            "chkconfig": "systemctl",
            "iptables": "ufw",
            "ifconfig": "ip",
            "netstat": "ss",
            "ps aux": "ps -ef",
            "killall": "pkill"
        }
        
        # Регулярные выражения для синтаксических ошибок
        self.syntax_patterns = {
            "missing_sudo": re.compile(r"permission denied|access denied|operation not permitted"),
            "command_not_found": re.compile(r"command not found|no such file or directory"),
            "package_not_found": re.compile(r"package.*not found|unable to locate package"),
            "service_not_found": re.compile(r"service.*not found|unit.*not found"),
            "connection_refused": re.compile(r"connection refused|connection timed out"),
            "file_not_found": re.compile(r"no such file or directory|file not found"),
            "syntax_error": re.compile(r"syntax error|invalid option|unrecognized option"),
            "network_error": re.compile(r"network is unreachable|name or service not known")
        }
        
        self.logger.info(
            "Autocorrection Engine инициализирован",
            max_attempts=max_attempts,
            timeout=timeout,
            strategies_count=len(CorrectionStrategy)
        )
    
    async def correct_command(self, command_result: CommandResult, context: ExecutionContext) -> AutocorrectionResult:
        """
        Основной метод исправления команды
        
        Args:
            command_result: Результат выполнения команды с ошибкой
            context: Контекст выполнения
            
        Returns:
            Результат автокоррекции
        """
        original_command = command_result.command
        error_message = getattr(command_result, 'error_message', None) or command_result.stderr or ""
        
        self.logger.info(
            "Начало автокоррекции команды",
            original_command=original_command,
            error_message=error_message[:100] if error_message else None
        )
        
        attempts = []
        current_command = original_command
        
        for attempt_num in range(1, self.max_attempts + 1):
            self.logger.debug(
                "Попытка исправления",
                attempt=attempt_num,
                command=current_command
            )
            
            # Определяем стратегию исправления
            strategy = self._determine_correction_strategy(current_command, error_message)
            
            if not strategy:
                self.logger.warning("Не удалось определить стратегию исправления")
                break
            
            # Применяем исправление
            corrected_command = self._apply_correction_strategy(
                current_command, error_message, strategy, context
            )
            
            if not corrected_command or corrected_command == current_command:
                self.logger.debug("Исправление не найдено или не изменило команду")
                break
            
            # Тестируем исправленную команду
            test_result = await self._test_corrected_command(corrected_command, context)
            
            attempt = CorrectionAttempt(
                original_command=current_command,
                corrected_command=corrected_command,
                strategy=strategy,
                success=test_result.success,
                error_message=getattr(test_result, 'error_message', None),
                metadata={
                    "attempt_number": attempt_num,
                    "test_result": test_result.to_dict() if hasattr(test_result, 'to_dict') else str(test_result)
                }
            )
            
            attempts.append(attempt)
            
            if test_result.success:
                self.logger.info(
                    "Автокоррекция успешна",
                    original_command=original_command,
                    final_command=corrected_command,
                    strategy=strategy.value,
                    attempts=attempt_num
                )
                
                return AutocorrectionResult(
                    success=True,
                    final_command=corrected_command,
                    attempts=attempts,
                    total_attempts=attempt_num
                )
            
            # Обновляем команду и сообщение об ошибке для следующей попытки
            current_command = corrected_command
            error_message = getattr(test_result, 'error_message', None) or test_result.stderr or ""
        
        self.logger.warning(
            "Автокоррекция не удалась",
            original_command=original_command,
            total_attempts=len(attempts)
        )
        
        return AutocorrectionResult(
            success=False,
            attempts=attempts,
            total_attempts=len(attempts),
            error_message="Все попытки исправления исчерпаны"
        )
    
    def _determine_correction_strategy(self, command: str, error_message: str) -> Optional[CorrectionStrategy]:
        """Определение стратегии исправления на основе ошибки"""
        error_lower = error_message.lower()
        command_lower = command.lower()
        
        # Проверяем паттерны ошибок
        for pattern_name, pattern in self.syntax_patterns.items():
            if pattern.search(error_lower):
                if pattern_name == "missing_sudo":
                    return CorrectionStrategy.PERMISSION_FIX
                elif pattern_name == "command_not_found":
                    return CorrectionStrategy.COMMAND_SUBSTITUTION
                elif pattern_name == "package_not_found":
                    return CorrectionStrategy.PACKAGE_UPDATE
                elif pattern_name == "service_not_found":
                    return CorrectionStrategy.SERVICE_RESTART
                elif pattern_name == "connection_refused":
                    return CorrectionStrategy.NETWORK_CHECK
                elif pattern_name == "file_not_found":
                    return CorrectionStrategy.PATH_CORRECTION
                elif pattern_name == "syntax_error":
                    return CorrectionStrategy.ALTERNATIVE_FLAGS
                elif pattern_name == "network_error":
                    return CorrectionStrategy.NETWORK_CHECK
        
        # Дополнительные проверки
        if "systemctl" in command_lower and "failed" in error_lower:
            return CorrectionStrategy.SERVICE_RESTART
        elif any(cmd in command_lower for cmd in ["curl", "wget", "ping"]) and "network" in error_lower:
            return CorrectionStrategy.NETWORK_CHECK
        elif "apt" in command_lower and "not found" in error_lower:
            return CorrectionStrategy.PACKAGE_UPDATE
        
        return CorrectionStrategy.SYNTAX_CHECK
    
    def _apply_correction_strategy(self, command: str, error_message: str, 
                                 strategy: CorrectionStrategy, context: ExecutionContext) -> Optional[str]:
        """Применение конкретной стратегии исправления"""
        
        if strategy == CorrectionStrategy.SYNTAX_CHECK:
            return self._fix_syntax_errors(command, error_message)
        elif strategy == CorrectionStrategy.ALTERNATIVE_FLAGS:
            return self._try_alternative_flags(command, error_message)
        elif strategy == CorrectionStrategy.NETWORK_CHECK:
            return self._fix_network_issues(command, error_message)
        elif strategy == CorrectionStrategy.SERVICE_RESTART:
            return self._fix_service_issues(command, error_message)
        elif strategy == CorrectionStrategy.PERMISSION_FIX:
            return self._fix_permission_issues(command, error_message)
        elif strategy == CorrectionStrategy.PACKAGE_UPDATE:
            return self._fix_package_issues(command, error_message)
        elif strategy == CorrectionStrategy.PATH_CORRECTION:
            return self._fix_path_issues(command, error_message)
        elif strategy == CorrectionStrategy.COMMAND_SUBSTITUTION:
            return self._substitute_command(command, error_message)
        
        return None
    
    def _fix_syntax_errors(self, command: str, error_message: str) -> Optional[str]:
        """Исправление синтаксических ошибок"""
        # Убираем лишние пробелы и символы
        corrected = command.strip()
        
        # Исправляем двойные пробелы
        corrected = re.sub(r'\s+', ' ', corrected)
        
        # Исправляем неправильные кавычки
        corrected = corrected.replace('"', '"').replace('"', '"')
        corrected = corrected.replace(''', "'").replace(''', "'")
        
        # Исправляем неправильные слеши
        if '\\' in corrected and '/' not in corrected:
            corrected = corrected.replace('\\', '/')
        
        return corrected if corrected != command else None
    
    def _try_alternative_flags(self, command: str, error_message: str) -> Optional[str]:
        """Попытка использования альтернативных флагов"""
        parts = command.split()
        if len(parts) < 2:
            return None
        
        base_command = parts[0]
        if base_command not in self.alternative_flags:
            return None
        
        # Пытаемся заменить флаги
        for flag_group in ["default", "fallback"]:
            if flag_group in self.alternative_flags[base_command]:
                for flag in self.alternative_flags[base_command][flag_group]:
                    if flag not in command:
                        # Добавляем новый флаг
                        new_command = f"{base_command} {flag} {' '.join(parts[1:])}"
                        return new_command
        
        return None
    
    def _fix_network_issues(self, command: str, error_message: str) -> Optional[str]:
        """Исправление сетевых проблем"""
        # Проверяем сетевое соединение
        if not self._check_network_connectivity():
            return None
        
        # Добавляем проверку сети перед командой
        if any(cmd in command.lower() for cmd in ["curl", "wget", "ping"]):
            return f"ping -c 1 8.8.8.8 > /dev/null 2>&1 && {command}"
        
        return None
    
    def _fix_service_issues(self, command: str, error_message: str) -> Optional[str]:
        """Исправление проблем с сервисами"""
        if "systemctl" not in command.lower():
            return None
        
        # Если сервис не найден, пытаемся перезапустить
        if "not found" in error_message.lower() or "failed" in error_message.lower():
            # Извлекаем имя сервиса
            parts = command.split()
            if len(parts) >= 3:
                service_name = parts[-1]
                return f"sudo systemctl daemon-reload && sudo systemctl restart {service_name}"
        
        return None
    
    def _fix_permission_issues(self, command: str, error_message: str) -> Optional[str]:
        """Исправление проблем с правами доступа"""
        # Проверяем, что command является строкой
        if not isinstance(command, str):
            self.logger.warning(f"Команда не является строкой в _fix_permission_issues: {type(command)} = {command}")
            return None
            
        if command.startswith("sudo "):
            return None
        
        # Команды, которые обычно требуют sudo
        sudo_commands = [
            "apt", "systemctl", "service", "docker", "chmod", "chown",
            "mkdir", "rm", "cp", "mv", "ln", "mount", "umount"
        ]
        
        if any(cmd in command.lower() for cmd in sudo_commands):
            return f"sudo {command}"
        
        return None
    
    def _fix_package_issues(self, command: str, error_message: str) -> Optional[str]:
        """Исправление проблем с пакетами"""
        if "apt" not in command.lower():
            return None
        
        # Обновляем список пакетов перед установкой
        if "install" in command.lower():
            return f"sudo apt update && {command}"
        
        return None
    
    def _fix_path_issues(self, command: str, error_message: str) -> Optional[str]:
        """Исправление проблем с путями"""
        # Создаем директорию если нужно
        if "mkdir" in command.lower() and "sudo" not in command.lower():
            return f"sudo {command}"
        
        # Исправляем относительные пути
        if isinstance(command, str) and "./" in command and not command.startswith("./"):
            return command.replace("./", "/")
        
        return None
    
    def _substitute_command(self, command: str, error_message: str) -> Optional[str]:
        """Замена команды на альтернативную"""
        for old_cmd, new_cmd in self.command_substitutions.items():
            if old_cmd in command.lower():
                return command.lower().replace(old_cmd, new_cmd)
        
        return None
    
    def _check_network_connectivity(self) -> bool:
        """Проверка сетевого соединения"""
        try:
            # Проверяем соединение с Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=self.timeout)
            return True
        except OSError:
            return False
    
    async def _test_corrected_command(self, command: str, context: ExecutionContext) -> CommandResult:
        """Тестирование исправленной команды"""
        try:
            # Выполняем команду в dry-run режиме или с ограниченным таймаутом
            result = await context.ssh_connection.execute_command(
                command, 
                timeout=10  # Короткий таймаут для тестирования
            )
            
            return CommandResult(
                command=command,
                success=result.exit_code == 0,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=0.1,  # Примерное время
                status=ExecutionStatus.COMPLETED if result.exit_code == 0 else ExecutionStatus.FAILED,
                error_message=result.stderr if result.exit_code != 0 else None
            )
            
        except Exception as e:
            return CommandResult(
                command=command,
                success=False,
                duration=0.1,
                status=ExecutionStatus.FAILED,
                error_message=str(e)
            )
    
    def get_correction_stats(self) -> Dict[str, Any]:
        """Получение статистики исправлений"""
        return {
            "max_attempts": self.max_attempts,
            "timeout": self.timeout,
            "alternative_flags_count": len(self.alternative_flags),
            "command_substitutions_count": len(self.command_substitutions),
            "syntax_patterns_count": len(self.syntax_patterns)
        }
