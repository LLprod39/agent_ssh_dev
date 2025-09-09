"""
Конфигурация сервера для SSH подключений
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml


class ServerConfig(BaseModel):
    """Конфигурация сервера"""
    
    host: str = Field(..., description="Хост сервера")
    port: int = Field(default=22, ge=1, le=65535, description="Порт SSH")
    username: str = Field(..., description="Имя пользователя")
    auth_method: str = Field(default="key", pattern="^(key|password)$", description="Метод аутентификации")
    key_path: Optional[str] = Field(None, description="Путь к приватному ключу")
    password: Optional[str] = Field(None, description="Пароль (если используется password auth)")
    timeout: int = Field(default=30, ge=1, le=300, description="Таймаут подключения в секундах")
    os_type: str = Field(default="ubuntu", pattern="^(ubuntu|centos|debian|rhel|fedora)$", description="Тип ОС")
    forbidden_commands: List[str] = Field(default_factory=list, description="Запрещенные команды")
    installed_services: List[str] = Field(default_factory=list, description="Установленные сервисы")
    installed_packages: List[str] = Field(default_factory=list, description="Установленные пакеты")
    disk_space_threshold: int = Field(default=1024, ge=0, description="Порог свободного места на диске в MB")
    memory_threshold: int = Field(default=512, ge=0, description="Порог свободной памяти в MB")
    
    @field_validator('auth_method')
    @classmethod
    def validate_auth_method(cls, v):
        """Валидация метода аутентификации"""
        if v not in ["key", "password"]:
            raise ValueError("auth_method должен быть 'key' или 'password'")
        return v
    
    @field_validator('key_path')
    @classmethod
    def validate_key_path(cls, v, info):
        """Валидация пути к ключу"""
        if v and hasattr(info, 'data') and info.data and info.data.get('auth_method') == 'key':
            key_path = Path(v)
            if not key_path.exists():
                raise ValueError(f"Файл ключа не найден: {v}")
        return v
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'ServerConfig':
        """Загрузка конфигурации из YAML файла"""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if 'server' not in data:
            raise ValueError("Отсутствует секция 'server' в конфигурации")
        
        return cls(**data['server'])
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return self.dict()
    
    def get_connection_params(self) -> Dict[str, Any]:
        """Получение параметров для SSH подключения"""
        params = {
            'hostname': self.host,
            'port': self.port,
            'username': self.username,
            'timeout': self.timeout
        }
        
        if self.auth_method == "key":
            if self.key_path:
                params['key_filename'] = self.key_path
        else:
            if self.password:
                params['password'] = self.password
        
        return params
    
    def load_credentials_from_manager(self, credentials_manager) -> bool:
        """Загружает учетные данные из менеджера учетных данных"""
        try:
            credentials = credentials_manager.load_credentials(self.host, self.username)
            if credentials:
                if self.auth_method == "password" and credentials.get('password'):
                    self.password = credentials['password']
                    return True
                elif self.auth_method == "key" and credentials.get('key_path'):
                    self.key_path = credentials['key_path']
                    return True
            return False
        except Exception:
            return False
    
    def is_command_forbidden(self, command: str) -> bool:
        """Проверка, запрещена ли команда"""
        command_lower = command.lower().strip()
        for forbidden in self.forbidden_commands:
            if forbidden.lower() in command_lower:
                return True
        return False
    
    def get_server_info(self) -> Dict[str, Any]:
        """Получение информации о сервере"""
        return {
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'os_type': self.os_type,
            'installed_services': self.installed_services,
            'installed_packages': self.installed_packages,
            'forbidden_commands': self.forbidden_commands,
            'disk_space_threshold': self.disk_space_threshold,
            'memory_threshold': self.memory_threshold
        }
