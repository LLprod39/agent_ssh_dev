"""
Утилиты для валидации данных
"""
import re
import os
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import yaml
from pydantic import BaseModel, ValidationError
from .logger import StructuredLogger


class ValidationError(Exception):
    """Кастомное исключение для ошибок валидации"""
    pass


class ConfigValidator:
    """Валидатор конфигурационных файлов"""
    
    @staticmethod
    def validate_yaml_file(file_path: str) -> bool:
        """
        Валидация YAML файла
        
        Args:
            file_path: Путь к YAML файлу
            
        Returns:
            True если файл валиден
            
        Raises:
            ValidationError: Если файл невалиден
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            return True
        except yaml.YAMLError as e:
            raise ValidationError(f"Ошибка парсинга YAML файла {file_path}: {e}")
        except FileNotFoundError:
            raise ValidationError(f"Файл не найден: {file_path}")
    
    @staticmethod
    def validate_config_structure(config: Dict[str, Any], required_sections: List[str]) -> bool:
        """
        Валидация структуры конфигурации
        
        Args:
            config: Словарь конфигурации
            required_sections: Список обязательных секций
            
        Returns:
            True если структура валидна
            
        Raises:
            ValidationError: Если структура невалидна
        """
        missing_sections = []
        for section in required_sections:
            if section not in config:
                missing_sections.append(section)
        
        if missing_sections:
            raise ValidationError(f"Отсутствуют обязательные секции: {', '.join(missing_sections)}")
        
        return True


class CommandValidator:
    """
    Валидатор команд с проверкой на запрещенные операции
    
    Этот класс проверяет команды на безопасность и соответствие
    политикам безопасности перед их выполнением.
    """
    
    def __init__(self, forbidden_commands: List[str] = None, allowed_commands: List[str] = None, security_config: dict = None):
        """
        Инициализация валидатора команд
        
        Args:
            forbidden_commands: Список запрещенных команд
            allowed_commands: Список разрешенных команд (если указан, то только эти команды разрешены)
            security_config: Конфигурация безопасности
        """
        self.forbidden_commands = forbidden_commands or self._get_default_forbidden_commands()
        self.allowed_commands = allowed_commands
        self.dangerous_patterns = self._get_default_dangerous_patterns()
        self._compile_patterns()
        
        # Инициализация логгера
        self.logger = StructuredLogger("CommandValidator")
        
        # Настройки безопасности
        self.security_config = security_config or {}
        self.validate_commands = self.security_config.get('validate_commands', True)
        self.log_forbidden_attempts = self.security_config.get('log_forbidden_attempts', True)
        self.require_confirmation_for_dangerous = self.security_config.get('require_confirmation_for_dangerous', True)
        self.allowed_commands_only = self.security_config.get('allowed_commands_only', False)
        
        # Счетчики для статистики
        self.validation_stats = {
            'total_validations': 0,
            'forbidden_attempts': 0,
            'dangerous_patterns_detected': 0,
            'allowed_commands': 0,
            'rejected_commands': 0
        }
    
    def _get_default_forbidden_commands(self) -> List[str]:
        """Получить список запрещенных команд по умолчанию"""
        return [
            "rm -rf /",
            "dd if=/dev/zero",
            ":(){ :|:& };:",  # fork bomb
            "shutdown",
            "reboot", 
            "halt",
            "poweroff",
            "mkfs",
            "fdisk",
            "parted",
            "wipefs",
            "format",
            "deltree",
            "chmod 777 /",
            "chown root:root /",
            "mount /dev/sda",
            "umount /",
            "crontab -r"
        ]
    
    def _get_default_dangerous_patterns(self) -> List[str]:
        """Получить список опасных паттернов по умолчанию"""
        return [
            r"rm\s+-rf\s+/",
            r"dd\s+if=/dev/(zero|random|urandom)",
            r"mkfs\.\w+",
            r"wipefs",
            r"fdisk\s+/dev/",
            r"parted\s+/dev/",
            r":\(\)\{.*:\|:&\s*\};:",  # fork bomb pattern
            r"shutdown\s+",
            r"reboot\s+",
            r"halt\s+",
            r"poweroff\s+",
            r"init\s+[06]",
            r"telinit\s+[06]",
            r">/dev/sd[a-z]",
            r"cat\s+/dev/(zero|random|urandom)\s*>",
            r"chmod\s+(777|666)\s+/",
            r"chown\s+\w+:\w+\s+/",
            r"crontab\s+-r",
            r">\s*/dev/null.*2>&1.*&",  # background processes with output suppression
            r"nohup.*&",  # long-running background processes
        ]
    
    def _compile_patterns(self):
        """Компиляция регулярных выражений для запрещенных команд"""
        self.forbidden_patterns = []
        for cmd in self.forbidden_commands:
            # Экранируем специальные символы и создаем паттерн
            escaped_cmd = re.escape(cmd.lower())
            pattern = re.compile(escaped_cmd, re.IGNORECASE)
            self.forbidden_patterns.append(pattern)
        
        # Компиляция паттернов для опасных команд
        self.compiled_dangerous_patterns = []
        for pattern in self.dangerous_patterns:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self.compiled_dangerous_patterns.append(compiled_pattern)
    
    def validate_command(self, command: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Валидация команды с улучшенной системой безопасности
        
        Args:
            command: Команда для валидации
            context: Контекст выполнения (step_id, task_id и т.д.)
            
        Returns:
            Словарь с результатами валидации
        """
        self.validation_stats['total_validations'] += 1
        
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'command': command,
            'security_level': 'safe',
            'requires_confirmation': False
        }
        
        # Проверка на пустую команду
        if not command or not command.strip():
            result['valid'] = False
            result['errors'].append("Команда не может быть пустой")
            self.validation_stats['rejected_commands'] += 1
            return result
        
        command_lower = command.lower().strip()
        
        # Проверка разрешенных команд (если указан белый список)
        if self.allowed_commands_only and self.allowed_commands:
            if not self._is_command_allowed(command_lower):
                result['valid'] = False
                result['errors'].append(f"Команда не входит в список разрешенных: {command}")
                self._log_forbidden_attempt(command, "not_in_allowed_list", context)
                self.validation_stats['rejected_commands'] += 1
                return result
        
        # Проверка запрещенных команд
        if self._is_command_forbidden(command_lower):
            result['valid'] = False
            result['errors'].append(f"Команда запрещена: {command}")
            result['security_level'] = 'forbidden'
            self._log_forbidden_attempt(command, "forbidden_command", context)
            self.validation_stats['forbidden_attempts'] += 1
            self.validation_stats['rejected_commands'] += 1
            return result
        
        # Проверка на потенциально опасные паттерны
        dangerous_patterns = self._check_dangerous_patterns_advanced(command_lower)
        if dangerous_patterns:
            result['warnings'].extend(dangerous_patterns)
            result['security_level'] = 'dangerous'
            self.validation_stats['dangerous_patterns_detected'] += 1
            
            if self.require_confirmation_for_dangerous:
                result['requires_confirmation'] = True
        
        # Если команда прошла все проверки
        if result['valid']:
            self.validation_stats['allowed_commands'] += 1
        
        return result
    
    def _is_command_allowed(self, command: str) -> bool:
        """Проверка, разрешена ли команда"""
        for allowed in self.allowed_commands:
            if command.startswith(allowed.lower()):
                return True
        return False
    
    def _is_command_forbidden(self, command: str) -> bool:
        """Проверка, запрещена ли команда"""
        for pattern in self.forbidden_patterns:
            if pattern.search(command):
                return True
        return False
    
    def _check_dangerous_patterns(self, command: str) -> List[str]:
        """Проверка на потенциально опасные паттерны (старый метод)"""
        warnings = []
        
        # Паттерны для проверки
        dangerous_patterns = {
            r'rm\s+-rf\s+/': "Опасная команда удаления корневой директории",
            r'dd\s+if=/dev/': "Команда dd может повредить данные",
            r'mkfs\.': "Команда форматирования файловой системы",
            r'fdisk\s+/dev/': "Команда разметки диска",
            r'shutdown|reboot|halt|poweroff': "Команда выключения/перезагрузки",
            r'>\s*/dev/': "Перенаправление в системные устройства",
            r'chmod\s+777': "Слишком открытые права доступа",
            r'chown\s+root': "Изменение владельца на root"
        }
        
        for pattern, warning in dangerous_patterns.items():
            if re.search(pattern, command):
                warnings.append(warning)
        
        return warnings
    
    def _check_dangerous_patterns_advanced(self, command: str) -> List[str]:
        """Расширенная проверка на потенциально опасные паттерны"""
        warnings = []
        
        for pattern in self.compiled_dangerous_patterns:
            if pattern.search(command):
                warnings.append(f"Обнаружен опасный паттерн: {pattern.pattern}")
        
        return warnings
    
    def _log_forbidden_attempt(self, command: str, reason: str, context: Dict[str, Any] = None):
        """Логирование попытки выполнения запрещенной команды"""
        if not self.log_forbidden_attempts:
            return
        
        log_data = {
            'reason': reason,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }
        
        if context:
            log_data.update(context)
        
        self.logger.log_forbidden_command_attempt(
            command=command,
            user=context.get('user', 'unknown') if context else 'unknown'
        )
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Получить статистику валидации"""
        total = self.validation_stats['total_validations']
        if total == 0:
            success_rate = 0.0
        else:
            success_rate = (self.validation_stats['allowed_commands'] / total) * 100
        
        return {
            **self.validation_stats,
            'success_rate': success_rate
        }
    
    def reset_stats(self):
        """Сброс статистики валидации"""
        self.validation_stats = {
            'total_validations': 0,
            'forbidden_attempts': 0,
            'dangerous_patterns_detected': 0,
            'allowed_commands': 0,
            'rejected_commands': 0
        }
    
    def add_forbidden_command(self, command: str):
        """Добавить команду в список запрещенных"""
        if command not in self.forbidden_commands:
            self.forbidden_commands.append(command)
            self._compile_patterns()
    
    def remove_forbidden_command(self, command: str):
        """Удалить команду из списка запрещенных"""
        if command in self.forbidden_commands:
            self.forbidden_commands.remove(command)
            self._compile_patterns()
    
    def add_dangerous_pattern(self, pattern: str):
        """Добавить опасный паттерн"""
        if pattern not in self.dangerous_patterns:
            self.dangerous_patterns.append(pattern)
            self._compile_patterns()
    
    def is_command_safe(self, command: str) -> bool:
        """Быстрая проверка - безопасна ли команда"""
        result = self.validate_command(command)
        return result['valid'] and result['security_level'] == 'safe'


class ServerInfoValidator:
    """Валидатор информации о сервере"""
    
    @staticmethod
    def validate_host(host: str) -> bool:
        """
        Валидация хоста
        
        Args:
            host: Хост для валидации
            
        Returns:
            True если хост валиден
            
        Raises:
            ValidationError: Если хост невалиден
        """
        if not host or not host.strip():
            raise ValidationError("Хост не может быть пустым")
        
        # Проверка на IP адрес
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ip_pattern, host):
            # Валидация IP адреса
            parts = host.split('.')
            for part in parts:
                if not 0 <= int(part) <= 255:
                    raise ValidationError(f"Невалидный IP адрес: {host}")
            return True
        
        # Проверка на доменное имя
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        if re.match(domain_pattern, host):
            return True
        
        raise ValidationError(f"Невалидный формат хоста: {host}")
    
    @staticmethod
    def validate_port(port: Union[int, str]) -> bool:
        """
        Валидация порта
        
        Args:
            port: Порт для валидации
            
        Returns:
            True если порт валиден
            
        Raises:
            ValidationError: Если порт невалиден
        """
        try:
            port_int = int(port)
            if not 1 <= port_int <= 65535:
                raise ValidationError(f"Порт должен быть в диапазоне 1-65535: {port}")
            return True
        except ValueError:
            raise ValidationError(f"Порт должен быть числом: {port}")
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """
        Валидация имени пользователя
        
        Args:
            username: Имя пользователя для валидации
            
        Returns:
            True если имя пользователя валидно
            
        Raises:
            ValidationError: Если имя пользователя невалидно
        """
        if not username or not username.strip():
            raise ValidationError("Имя пользователя не может быть пустым")
        
        # Проверка на допустимые символы
        username_pattern = r'^[a-zA-Z0-9._-]+$'
        if not re.match(username_pattern, username):
            raise ValidationError(f"Имя пользователя содержит недопустимые символы: {username}")
        
        # Проверка длины
        if len(username) > 32:
            raise ValidationError(f"Имя пользователя слишком длинное (максимум 32 символа): {username}")
        
        return True


class FileValidator:
    """Валидатор файлов"""
    
    @staticmethod
    def validate_file_exists(file_path: str) -> bool:
        """
        Проверка существования файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл существует
            
        Raises:
            ValidationError: Если файл не существует
        """
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(f"Файл не существует: {file_path}")
        return True
    
    @staticmethod
    def validate_file_permissions(file_path: str, required_permissions: str = "r") -> bool:
        """
        Проверка прав доступа к файлу
        
        Args:
            file_path: Путь к файлу
            required_permissions: Требуемые права доступа ('r', 'w', 'rw')
            
        Returns:
            True если права доступа корректны
            
        Raises:
            ValidationError: Если права доступа некорректны
        """
        path = Path(file_path)
        
        if 'r' in required_permissions and not path.is_file():
            raise ValidationError(f"Файл не является обычным файлом: {file_path}")
        
        if 'r' in required_permissions and not os.access(path, os.R_OK):
            raise ValidationError(f"Нет прав на чтение файла: {file_path}")
        
        if 'w' in required_permissions and not os.access(path, os.W_OK):
            raise ValidationError(f"Нет прав на запись в файл: {file_path}")
        
        return True
    
    @staticmethod
    def validate_ssh_key(key_path: str) -> bool:
        """
        Валидация SSH ключа
        
        Args:
            key_path: Путь к SSH ключу
            
        Returns:
            True если ключ валиден
            
        Raises:
            ValidationError: Если ключ невалиден
        """
        FileValidator.validate_file_exists(key_path)
        FileValidator.validate_file_permissions(key_path, "r")
        
        # Проверка содержимого ключа
        try:
            with open(key_path, 'r') as f:
                content = f.read()
            
            # Проверка на наличие заголовков SSH ключей
            ssh_headers = [
                '-----BEGIN OPENSSH PRIVATE KEY-----',
                '-----BEGIN RSA PRIVATE KEY-----',
                '-----BEGIN DSA PRIVATE KEY-----',
                '-----BEGIN EC PRIVATE KEY-----',
                '-----BEGIN PRIVATE KEY-----'
            ]
            
            if not any(header in content for header in ssh_headers):
                raise ValidationError(f"Файл не является валидным SSH ключом: {key_path}")
            
            return True
            
        except Exception as e:
            raise ValidationError(f"Ошибка чтения SSH ключа {key_path}: {e}")


class DataValidator:
    """Валидатор данных"""
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> bool:
        """
        Проверка наличия обязательных полей
        
        Args:
            data: Словарь с данными
            required_fields: Список обязательных полей
            
        Returns:
            True если все поля присутствуют
            
        Raises:
            ValidationError: Если отсутствуют обязательные поля
        """
        missing_fields = []
        for field in required_fields:
            if field not in data or data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValidationError(f"Отсутствуют обязательные поля: {', '.join(missing_fields)}")
        
        return True
    
    @staticmethod
    def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]) -> bool:
        """
        Проверка типов полей
        
        Args:
            data: Словарь с данными
            field_types: Словарь с ожидаемыми типами полей
            
        Returns:
            True если типы корректны
            
        Raises:
            ValidationError: Если типы некорректны
        """
        for field, expected_type in field_types.items():
            if field in data and not isinstance(data[field], expected_type):
                raise ValidationError(
                    f"Поле '{field}' должно быть типа {expected_type.__name__}, "
                    f"получен {type(data[field]).__name__}"
                )
        
        return True


def validate_config_file(file_path: str, config_class: BaseModel) -> BaseModel:
    """
    Валидация конфигурационного файла с помощью Pydantic модели
    
    Args:
        file_path: Путь к конфигурационному файлу
        config_class: Класс Pydantic для валидации
        
    Returns:
        Валидированный экземпляр конфигурации
        
    Raises:
        ValidationError: Если конфигурация невалидна
    """
    try:
        # Валидация YAML файла
        ConfigValidator.validate_yaml_file(file_path)
        
        # Загрузка и валидация с помощью Pydantic
        if hasattr(config_class, 'from_yaml'):
            return config_class.from_yaml(file_path)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return config_class(**data)
            
    except ValidationError as e:
        raise ValidationError(f"Ошибка валидации конфигурации {file_path}: {e}")
    except Exception as e:
        raise ValidationError(f"Неожиданная ошибка при валидации {file_path}: {e}")
