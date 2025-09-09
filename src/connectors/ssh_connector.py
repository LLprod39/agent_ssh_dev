"""
SSH Connector для безопасного подключения к удаленным серверам
"""
import paramiko
import asyncio
import socket
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import getpass
import os
from contextlib import asynccontextmanager

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config.server_config import ServerConfig
from ..utils.logger import setup_logging
from ..utils.credentials_manager import CredentialsManager, KeyringCredentialsManager, SSHKeyManager
from ..utils.validator import CommandValidator


class SSHConnectionError(Exception):
    """Исключение для ошибок SSH подключения"""
    pass


class SSHCommandError(Exception):
    """Исключение для ошибок выполнения команд"""
    pass


class CommandResult:
    """Результат выполнения команды"""
    
    def __init__(
        self,
        command: str,
        exit_code: int,
        stdout: str = "",
        stderr: str = "",
        duration: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ):
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration or 0.0
        self.timestamp = timestamp or datetime.now()
    
    @property
    def success(self) -> bool:
        """Проверка успешности выполнения команды"""
        return self.exit_code == 0
    
    @property
    def failed(self) -> bool:
        """Проверка неуспешности выполнения команды"""
        return not self.success
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'command': self.command,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'duration': self.duration,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success
        }
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"Command: {self.command} | Status: {status} | Exit Code: {self.exit_code}"


class SSHConnector:
    """SSH Connector для безопасного подключения к удаленным серверам"""
    
    def __init__(self, config: ServerConfig, use_credentials_manager: bool = True, security_config: dict = None):
        self.config = config
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.connected = False
        self.connection_time: Optional[datetime] = None
        self.last_activity: Optional[datetime] = None
        
        # Настройка логирования
        self.logger = logger.bind(component="SSHConnector", host=config.host)
        
        # Валидатор команд для безопасности
        self.command_validator = CommandValidator(
            forbidden_commands=getattr(config, 'forbidden_commands', None),
            security_config=security_config
        )
        
        # Менеджеры учетных данных
        self.use_credentials_manager = use_credentials_manager
        if use_credentials_manager:
            self.credentials_manager = CredentialsManager()
            self.keyring_manager = KeyringCredentialsManager()
            self.key_manager = SSHKeyManager()
        
        # Статистика подключения
        self.stats = {
            'connection_attempts': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'commands_executed': 0,
            'commands_failed': 0,
            'total_connection_time': 0.0,
            'forbidden_attempts': 0,
            'validation_failures': 0
        }
    
    async def connect(self) -> bool:
        """Устанавливает SSH соединение с retry логикой"""
        self.logger.info(f"Попытка подключения к {self.config.host}:{self.config.port}")
        
        try:
            await self._connect_with_retry()
            self.connected = True
            self.connection_time = datetime.now()
            self.last_activity = datetime.now()
            self.stats['successful_connections'] += 1
            self.logger.info("SSH подключение установлено успешно")
            return True
            
        except Exception as e:
            self.stats['failed_connections'] += 1
            self.logger.error(f"Ошибка SSH подключения: {e}")
            raise SSHConnectionError(f"Не удалось подключиться к {self.config.host}: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((paramiko.SSHException, socket.error, ConnectionError))
    )
    async def _connect_with_retry(self):
        """Подключение с повторными попытками"""
        self.stats['connection_attempts'] += 1
        
        # Создаем SSH клиент
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Настройка параметров подключения
        connect_params = self._prepare_connection_params()
        
        # Выполняем подключение в отдельном потоке
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            self._do_connect, 
            connect_params
        )
        
        # Открываем SFTP соединение
        self.sftp = self.client.open_sftp()
    
    def _prepare_connection_params(self) -> Dict[str, Any]:
        """Подготовка параметров подключения"""
        params = {
            'hostname': self.config.host,
            'port': self.config.port,
            'username': self.config.username,
            'timeout': self.config.timeout,
            'banner_timeout': 30,
            'auth_timeout': 30
        }
        
        # Загружаем учетные данные из менеджера если необходимо
        if self.use_credentials_manager:
            self._load_credentials_from_manager()
        
        if self.config.auth_method == "key":
            key_path = self._resolve_key_path()
            if not key_path:
                raise ValueError("Не удалось найти SSH ключ для аутентификации")
            
            params['key_filename'] = str(key_path)
            self.logger.debug(f"Используется аутентификация по ключу: {key_path}")
            
        elif self.config.auth_method == "password":
            password = self._resolve_password()
            if not password:
                raise ValueError("Пароль не найден для аутентификации")
            
            params['password'] = password
            self.logger.debug("Используется аутентификация по паролю")
        
        return params
    
    def _load_credentials_from_manager(self):
        """Загружает учетные данные из менеджера"""
        try:
            # Пытаемся загрузить из keyring
            if self.config.auth_method == "password":
                password = self.keyring_manager.load_credentials(self.config.host, self.config.username)
                if password:
                    self.config.password = password
                    self.logger.debug("Пароль загружен из keyring")
                    return
            
            # Пытаемся загрузить из файлового менеджера
            self.config.load_credentials_from_manager(self.credentials_manager)
            
        except Exception as e:
            self.logger.debug(f"Не удалось загрузить учетные данные из менеджера: {e}")
    
    def _resolve_key_path(self) -> Optional[Path]:
        """Определяет путь к SSH ключу"""
        # Если путь указан в конфигурации
        if self.config.key_path:
            key_path = Path(self.config.key_path).expanduser()
            if key_path.exists() and self.key_manager.validate_key(str(key_path)):
                return key_path
        
        # Ищем доступные ключи
        if self.use_credentials_manager:
            available_keys = self.key_manager.find_available_keys()
            for key_path in available_keys:
                if self.key_manager.validate_key(str(key_path)):
                    self.logger.info(f"Найден валидный SSH ключ: {key_path}")
                    return key_path
        
        return None
    
    def _resolve_password(self) -> Optional[str]:
        """Определяет пароль для аутентификации"""
        # Если пароль указан в конфигурации
        if self.config.password:
            return self.config.password
        
        # Пытаемся загрузить из keyring
        if self.use_credentials_manager:
            password = self.keyring_manager.load_credentials(self.config.host, self.config.username)
            if password:
                return password
        
        # Запрашиваем пароль интерактивно
        try:
            return getpass.getpass(f"Введите пароль для {self.config.username}@{self.config.host}: ")
        except KeyboardInterrupt:
            raise SSHConnectionError("Отменено пользователем")
    
    def store_credentials(self, password: Optional[str] = None, key_path: Optional[str] = None) -> bool:
        """Сохраняет учетные данные в менеджере"""
        if not self.use_credentials_manager:
            return False
        
        try:
            if self.config.auth_method == "password" and password:
                # Сохраняем в keyring
                success = self.keyring_manager.store_credentials(
                    self.config.host, 
                    self.config.username, 
                    password
                )
                if success:
                    self.logger.info(f"Пароль сохранен для {self.config.username}@{self.config.host}")
                return success
            
            elif self.config.auth_method == "key" and key_path:
                # Сохраняем путь к ключу
                success = self.credentials_manager.store_credentials(
                    self.config.host,
                    self.config.username,
                    key_path=key_path
                )
                if success:
                    self.logger.info(f"Путь к ключу сохранен для {self.config.username}@{self.config.host}")
                return success
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения учетных данных: {e}")
            return False
    
    def _do_connect(self, params: Dict[str, Any]):
        """Синхронное подключение (выполняется в executor)"""
        self.client.connect(**params)
    
    async def disconnect(self):
        """Закрывает SSH соединение"""
        if self.connected:
            try:
                if self.sftp:
                    self.sftp.close()
                    self.sftp = None
                
                if self.client:
                    self.client.close()
                    self.client = None
                
                # Обновляем статистику
                if self.connection_time:
                    connection_duration = (datetime.now() - self.connection_time).total_seconds()
                    self.stats['total_connection_time'] += connection_duration
                
                self.connected = False
                self.logger.info("SSH соединение закрыто")
                
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии SSH соединения: {e}")
    
    async def execute_command(
        self, 
        command: str, 
        timeout: Optional[int] = None,
        check_forbidden: bool = True,
        context: Dict[str, Any] = None
    ) -> CommandResult:
        """Выполняет команду через SSH с расширенной проверкой безопасности"""
        if not self.connected or not self.client:
            raise SSHConnectionError("SSH соединение не установлено")
        
        # Расширенная проверка безопасности
        if check_forbidden:
            validation_result = self.command_validator.validate_command(command, context)
            
            if not validation_result['valid']:
                self.stats['forbidden_attempts'] += 1
                self.stats['validation_failures'] += 1
                error_msg = f"Команда заблокирована системой безопасности: {command}. Причины: {', '.join(validation_result['errors'])}"
                raise SSHCommandError(error_msg)
            
            # Логируем предупреждения для опасных команд
            if validation_result['warnings']:
                self.logger.warning(
                    f"Выполнение потенциально опасной команды: {command}",
                    warnings=validation_result['warnings'],
                    security_level=validation_result['security_level'],
                    requires_confirmation=validation_result['requires_confirmation']
                )
        
        timeout = timeout or self.config.timeout
        start_time = datetime.now()
        
        self.logger.info(f"Выполнение команды: {command}")
        
        try:
            # Выполняем команду в отдельном потоке
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._do_execute_command,
                command,
                timeout
            )
            
            # Обновляем статистику
            self.stats['commands_executed'] += 1
            if result.failed:
                self.stats['commands_failed'] += 1
            
            self.last_activity = datetime.now()
            
            # Логируем результат
            if result.success:
                self.logger.info(f"Команда выполнена успешно: {command}")
            else:
                self.logger.warning(f"Команда завершилась с ошибкой: {command} (код: {result.exit_code})")
                if result.stderr:
                    self.logger.debug(f"Stderr: {result.stderr}")
            
            return result
            
        except Exception as e:
            self.stats['commands_failed'] += 1
            self.logger.error(f"Ошибка выполнения команды '{command}': {e}")
            raise SSHCommandError(f"Ошибка выполнения команды: {e}")
    
    def _do_execute_command(self, command: str, timeout: int) -> CommandResult:
        """Синхронное выполнение команды"""
        start_time = datetime.now()
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Ждем завершения команды
            exit_code = stdout.channel.recv_exit_status()
            
            # Читаем вывод
            stdout_data = stdout.read().decode('utf-8', errors='replace')
            stderr_data = stderr.read().decode('utf-8', errors='replace')
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return CommandResult(
                command=command,
                exit_code=exit_code,
                stdout=stdout_data,
                stderr=stderr_data,
                duration=duration,
                timestamp=start_time
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                timestamp=start_time
            )
    
    async def execute_commands_batch(
        self, 
        commands: List[str], 
        timeout: Optional[int] = None,
        stop_on_error: bool = False
    ) -> List[CommandResult]:
        """Выполняет несколько команд последовательно"""
        results = []
        
        for command in commands:
            try:
                result = await self.execute_command(command, timeout)
                results.append(result)
                
                if stop_on_error and result.failed:
                    self.logger.warning(f"Остановка выполнения из-за ошибки в команде: {command}")
                    break
                    
            except Exception as e:
                self.logger.error(f"Ошибка при выполнении команды '{command}': {e}")
                results.append(CommandResult(
                    command=command,
                    exit_code=-1,
                    stderr=str(e)
                ))
                
                if stop_on_error:
                    break
        
        return results
    
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Загружает файл на сервер"""
        if not self.connected or not self.sftp:
            raise SSHConnectionError("SSH соединение не установлено")
        
        try:
            local_file = Path(local_path)
            if not local_file.exists():
                raise FileNotFoundError(f"Локальный файл не найден: {local_path}")
            
            self.logger.info(f"Загрузка файла: {local_path} -> {remote_path}")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.sftp.put,
                str(local_file),
                remote_path
            )
            
            self.logger.info(f"Файл успешно загружен: {remote_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла: {e}")
            return False
    
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Скачивает файл с сервера"""
        if not self.connected or not self.sftp:
            raise SSHConnectionError("SSH соединение не установлено")
        
        try:
            local_file = Path(local_path)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"Скачивание файла: {remote_path} -> {local_path}")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.sftp.get,
                remote_path,
                str(local_file)
            )
            
            self.logger.info(f"Файл успешно скачан: {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка скачивания файла: {e}")
            return False
    
    async def check_connection(self) -> bool:
        """Проверяет состояние SSH соединения"""
        if not self.connected or not self.client:
            return False
        
        try:
            # Выполняем простую команду для проверки соединения
            result = await self.execute_command("echo 'connection_test'", timeout=5)
            return result.success and "connection_test" in result.stdout
        except:
            return False
    
    async def get_server_info(self) -> Dict[str, Any]:
        """Получает информацию о сервере"""
        if not self.connected:
            raise SSHConnectionError("SSH соединение не установлено")
        
        info = {}
        
        try:
            # Информация об ОС
            result = await self.execute_command("uname -a")
            if result.success:
                info['uname'] = result.stdout.strip()
            
            # Информация о дисках
            result = await self.execute_command("df -h")
            if result.success:
                info['disk_usage'] = result.stdout.strip()
            
            # Информация о памяти
            result = await self.execute_command("free -h")
            if result.success:
                info['memory_usage'] = result.stdout.strip()
            
            # Информация о загрузке
            result = await self.execute_command("uptime")
            if result.success:
                info['uptime'] = result.stdout.strip()
            
            # Информация о процессах
            result = await self.execute_command("ps aux --sort=-%cpu | head -10")
            if result.success:
                info['top_processes'] = result.stdout.strip()
            
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о сервере: {e}")
        
        return info
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику подключения"""
        return {
            **self.stats,
            'connected': self.connected,
            'connection_time': self.connection_time.isoformat() if self.connection_time else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'host': self.config.host,
            'username': self.config.username,
            'security_stats': self.get_security_stats()
        }
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Возвращает статистику безопасности"""
        validation_stats = self.command_validator.get_validation_stats()
        return {
            'command_validation': validation_stats,
            'forbidden_attempts': self.stats['forbidden_attempts'],
            'validation_failures': self.stats['validation_failures'],
            'security_enabled': True
        }
    
    def is_command_safe(self, command: str) -> bool:
        """Проверяет безопасность команды без выполнения"""
        return self.command_validator.is_command_safe(command)
    
    @asynccontextmanager
    async def connection_context(self):
        """Контекстный менеджер для SSH соединения"""
        try:
            await self.connect()
            yield self
        finally:
            await self.disconnect()
    
    def __str__(self) -> str:
        status = "Connected" if self.connected else "Disconnected"
        return f"SSHConnector({self.config.host}:{self.config.port}, {status})"
    
    def __repr__(self) -> str:
        return f"SSHConnector(host='{self.config.host}', port={self.config.port}, connected={self.connected})"
