"""
Система идемпотентности для SSH агента

Этот модуль обеспечивает:
- Генерацию идемпотентных команд
- Проверки состояния перед выполнением
- Систему отката изменений
- Отслеживание состояния системы
"""

from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import re

from .logger import StructuredLogger
from .health_checker import HealthChecker
from .command_generator import LinuxCommandGenerator
from .validator import CommandValidator
from ..connectors.ssh_connector import SSHConnector, CommandResult


class IdempotencyCheckType(Enum):
    """Типы проверок идемпотентности"""
    FILE_EXISTS = "file_exists"
    DIRECTORY_EXISTS = "directory_exists"
    SERVICE_RUNNING = "service_running"
    PACKAGE_INSTALLED = "package_installed"
    USER_EXISTS = "user_exists"
    GROUP_EXISTS = "group_exists"
    PORT_OPEN = "port_open"
    PROCESS_RUNNING = "process_running"
    CONFIG_EXISTS = "config_exists"
    CUSTOM_CHECK = "custom_check"


@dataclass
class IdempotencyCheck:
    """Проверка идемпотентности"""
    
    check_type: IdempotencyCheckType
    target: str  # Файл, сервис, пакет и т.д.
    expected_state: Any  # Ожидаемое состояние
    check_command: str  # Команда для проверки
    success_pattern: str  # Паттерн успешного результата
    description: str = ""
    timeout: int = 30
    retry_count: int = 3


@dataclass
class IdempotencyResult:
    """Результат проверки идемпотентности"""
    
    check: IdempotencyCheck
    success: bool
    current_state: Any
    command_result: Optional[CommandResult] = None
    error_message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StateSnapshot:
    """Снимок состояния системы"""
    
    snapshot_id: str
    timestamp: datetime
    checks: List[IdempotencyResult]
    system_info: Dict[str, Any]
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    services_started: List[str] = field(default_factory=list)
    packages_installed: List[str] = field(default_factory=list)
    users_created: List[str] = field(default_factory=list)
    groups_created: List[str] = field(default_factory=list)


class IdempotencySystem:
    """
    Система идемпотентности для SSH агента
    
    Обеспечивает:
    - Генерацию идемпотентных команд
    - Проверки состояния перед выполнением
    - Систему отката изменений
    """
    
    def __init__(self, ssh_connector: SSHConnector, config: Dict[str, Any]):
        """
        Инициализация системы идемпотентности
        
        Args:
            ssh_connector: SSH коннектор для выполнения команд
            config: Конфигурация системы
        """
        self.ssh_connector = ssh_connector
        self.config = config
        self.logger = StructuredLogger("IdempotencySystem")
        
        # Инициализируем компоненты
        self.health_checker = HealthChecker({})
        self.command_generator = LinuxCommandGenerator({})
        self.command_validator = CommandValidator({})
        
        # Хранилище снимков состояния
        self.state_snapshots: Dict[str, StateSnapshot] = {}
        self.current_snapshot: Optional[StateSnapshot] = None
        
        # Кэш проверок
        self.check_cache: Dict[str, IdempotencyResult] = {}
        self.cache_ttl = getattr(config, 'cache_ttl', 300)  # 5 минут
        
        self.logger.info("Система идемпотентности инициализирована")
    
    def create_state_snapshot(self, task_id: str) -> StateSnapshot:
        """
        Создание снимка текущего состояния системы
        
        Args:
            task_id: Идентификатор задачи
            
        Returns:
            Снимок состояния системы
        """
        snapshot_id = f"{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Собираем информацию о системе
        system_info = self._collect_system_info()
        
        # Создаем снимок
        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now(),
            checks=[],
            system_info=system_info
        )
        
        self.state_snapshots[snapshot_id] = snapshot
        self.current_snapshot = snapshot
        
        self.logger.info("Создан снимок состояния системы", snapshot_id=snapshot_id)
        return snapshot
    
    def generate_idempotent_command(self, base_command: str, command_type: str, 
                                  target: str, **kwargs) -> Tuple[str, List[IdempotencyCheck]]:
        """
        Генерация идемпотентной команды
        
        Args:
            base_command: Базовая команда
            command_type: Тип команды (install, create, start, etc.)
            target: Цель команды (файл, сервис, пакет)
            **kwargs: Дополнительные параметры
            
        Returns:
            Кортеж (идемпотентная команда, список проверок)
        """
        checks = []
        
        if command_type == "install_package":
            checks.append(self._create_package_check(target))
            idempotent_command = f"dpkg -l | grep -q '^ii  {target}' || apt-get install -y {target}"
            
        elif command_type == "create_file":
            checks.append(self._create_file_check(target))
            idempotent_command = f"test -f {target} || (mkdir -p $(dirname {target}) && touch {target})"
            
        elif command_type == "create_directory":
            checks.append(self._create_directory_check(target))
            idempotent_command = f"test -d {target} || mkdir -p {target}"
            
        elif command_type == "start_service":
            checks.append(self._create_service_check(target))
            idempotent_command = f"systemctl is-active --quiet {target} || systemctl start {target}"
            
        elif command_type == "enable_service":
            checks.append(self._create_service_enabled_check(target))
            idempotent_command = f"systemctl is-enabled --quiet {target} || systemctl enable {target}"
            
        elif command_type == "create_user":
            checks.append(self._create_user_check(target))
            idempotent_command = f"id {target} >/dev/null 2>&1 || useradd {target}"
            
        elif command_type == "create_group":
            checks.append(self._create_group_check(target))
            idempotent_command = f"getent group {target} >/dev/null 2>&1 || groupadd {target}"
            
        elif command_type == "open_port":
            port = kwargs.get("port", target)
            checks.append(self._create_port_check(port))
            idempotent_command = f"netstat -tuln | grep -q ':{port} ' || (iptables -A INPUT -p tcp --dport {port} -j ACCEPT)"
            
        else:
            # Для неизвестных типов команд добавляем базовую проверку
            checks.append(self._create_custom_check(target, base_command))
            idempotent_command = base_command
        
        self.logger.info(
            "Сгенерирована идемпотентная команда",
            command_type=command_type,
            target=target,
            checks_count=len(checks)
        )
        
        return idempotent_command, checks
    
    def check_idempotency(self, checks: List[IdempotencyCheck]) -> List[IdempotencyResult]:
        """
        Проверка идемпотентности для списка проверок
        
        Args:
            checks: Список проверок
            
        Returns:
            Список результатов проверок
        """
        results = []
        
        for check in checks:
            # Проверяем кэш
            cache_key = self._get_cache_key(check)
            if cache_key in self.check_cache:
                cached_result = self.check_cache[cache_key]
                if self._is_cache_valid(cached_result):
                    results.append(cached_result)
                    continue
            
            # Выполняем проверку
            result = self._execute_check(check)
            results.append(result)
            
            # Сохраняем в кэш
            self.check_cache[cache_key] = result
        
        # Обновляем текущий снимок
        if self.current_snapshot:
            self.current_snapshot.checks.extend(results)
        
        self.logger.info(
            "Выполнены проверки идемпотентности",
            total_checks=len(checks),
            successful_checks=len([r for r in results if r.success])
        )
        
        return results
    
    def should_skip_command(self, command: str, checks: List[IdempotencyCheck]) -> bool:
        """
        Определение необходимости пропуска команды
        
        Args:
            command: Команда для проверки
            checks: Список проверок
            
        Returns:
            True если команду можно пропустить
        """
        if not checks:
            return False
        
        results = self.check_idempotency(checks)
        
        # Если все проверки показывают, что состояние уже достигнуто
        all_already_done = all(result.success for result in results)
        
        if all_already_done:
            self.logger.info("Команда пропущена - состояние уже достигнуто", command=command)
            return True
        
        return False
    
    def create_rollback_commands(self, snapshot: StateSnapshot) -> List[str]:
        """
        Создание команд отката на основе снимка состояния
        
        Args:
            snapshot: Снимок состояния для отката
            
        Returns:
            Список команд отката
        """
        rollback_commands = []
        
        # Откат установленных пакетов
        for package in snapshot.packages_installed:
            rollback_commands.append(f"apt-get remove -y {package}")
        
        # Откат созданных пользователей
        for user in snapshot.users_created:
            rollback_commands.append(f"userdel -r {user}")
        
        # Откат созданных групп
        for group in snapshot.groups_created:
            rollback_commands.append(f"groupdel {group}")
        
        # Откат запущенных сервисов
        for service in snapshot.services_started:
            rollback_commands.append(f"systemctl stop {service}")
        
        # Откат созданных файлов
        for file_path in snapshot.files_created:
            rollback_commands.append(f"rm -f {file_path}")
        
        # Откат созданных директорий
        for file_path in snapshot.files_created:
            dir_path = file_path.rsplit('/', 1)[0]
            if dir_path and dir_path != '/':
                rollback_commands.append(f"rmdir {dir_path} 2>/dev/null || true")
        
        self.logger.info(
            "Созданы команды отката",
            snapshot_id=snapshot.snapshot_id,
            commands_count=len(rollback_commands)
        )
        
        return rollback_commands
    
    async def execute_rollback(self, snapshot_id: str) -> List[CommandResult]:
        """
        Выполнение отката к состоянию снимка
        
        Args:
            snapshot_id: Идентификатор снимка для отката
            
        Returns:
            Список результатов выполнения команд отката
        """
        if snapshot_id not in self.state_snapshots:
            raise ValueError(f"Снимок {snapshot_id} не найден")
        
        snapshot = self.state_snapshots[snapshot_id]
        rollback_commands = self.create_rollback_commands(snapshot)
        
        results = []
        for command in rollback_commands:
            try:
                result = await self.ssh_connector.execute_command(command)
                results.append(result)
                
                if result.success:
                    self.logger.info("Команда отката выполнена успешно", command=command)
                else:
                    self.logger.warning("Команда отката завершилась с ошибкой", 
                                      command=command, exit_code=result.exit_code)
            except Exception as e:
                self.logger.error("Ошибка выполнения команды отката", 
                                command=command, error=str(e))
                # Создаем фиктивный результат для отслеживания
                from ..connectors.ssh_connector import CommandResult
                results.append(CommandResult(command, 1, stderr=str(e)))
        
        self.logger.info(
            "Выполнен откат состояния",
            snapshot_id=snapshot_id,
            commands_executed=len(rollback_commands),
            successful_commands=len([r for r in results if r.success])
        )
        
        return results
    
    def _create_package_check(self, package: str) -> IdempotencyCheck:
        """Создание проверки установки пакета"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.PACKAGE_INSTALLED,
            target=package,
            expected_state=True,
            check_command=f"dpkg -l | grep -q '^ii  {package}'",
            success_pattern=r".*",
            description=f"Проверка установки пакета {package}"
        )
    
    def _create_file_check(self, file_path: str) -> IdempotencyCheck:
        """Создание проверки существования файла"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.FILE_EXISTS,
            target=file_path,
            expected_state=True,
            check_command=f"test -f {file_path}",
            success_pattern=r".*",
            description=f"Проверка существования файла {file_path}"
        )
    
    def _create_directory_check(self, dir_path: str) -> IdempotencyCheck:
        """Создание проверки существования директории"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.DIRECTORY_EXISTS,
            target=dir_path,
            expected_state=True,
            check_command=f"test -d {dir_path}",
            success_pattern=r".*",
            description=f"Проверка существования директории {dir_path}"
        )
    
    def _create_service_check(self, service: str) -> IdempotencyCheck:
        """Создание проверки запуска сервиса"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.SERVICE_RUNNING,
            target=service,
            expected_state=True,
            check_command=f"systemctl is-active --quiet {service}",
            success_pattern=r".*",
            description=f"Проверка запуска сервиса {service}"
        )
    
    def _create_service_enabled_check(self, service: str) -> IdempotencyCheck:
        """Создание проверки включения сервиса"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.SERVICE_RUNNING,
            target=service,
            expected_state=True,
            check_command=f"systemctl is-enabled --quiet {service}",
            success_pattern=r".*",
            description=f"Проверка включения сервиса {service}"
        )
    
    def _create_user_check(self, username: str) -> IdempotencyCheck:
        """Создание проверки существования пользователя"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.USER_EXISTS,
            target=username,
            expected_state=True,
            check_command=f"id {username} >/dev/null 2>&1",
            success_pattern=r".*",
            description=f"Проверка существования пользователя {username}"
        )
    
    def _create_group_check(self, groupname: str) -> IdempotencyCheck:
        """Создание проверки существования группы"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.GROUP_EXISTS,
            target=groupname,
            expected_state=True,
            check_command=f"getent group {groupname} >/dev/null 2>&1",
            success_pattern=r".*",
            description=f"Проверка существования группы {groupname}"
        )
    
    def _create_port_check(self, port: str) -> IdempotencyCheck:
        """Создание проверки открытого порта"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.PORT_OPEN,
            target=port,
            expected_state=True,
            check_command=f"netstat -tuln | grep -q ':{port} '",
            success_pattern=r".*",
            description=f"Проверка открытого порта {port}"
        )
    
    def _create_custom_check(self, target: str, command: str) -> IdempotencyCheck:
        """Создание пользовательской проверки"""
        return IdempotencyCheck(
            check_type=IdempotencyCheckType.CUSTOM_CHECK,
            target=target,
            expected_state=True,
            check_command=command,
            success_pattern=r".*",
            description=f"Пользовательская проверка для {target}"
        )
    
    async def _execute_check(self, check: IdempotencyCheck) -> IdempotencyResult:
        """Выполнение отдельной проверки"""
        try:
            result = await self.ssh_connector.execute_command(check.check_command)
            
            # Проверяем успешность по exit code
            success = result.exit_code == 0
            
            # Дополнительная проверка по паттерну
            if success and check.success_pattern:
                pattern_match = re.search(check.success_pattern, result.stdout)
                success = pattern_match is not None
            
            return IdempotencyResult(
                check=check,
                success=success,
                current_state=result.stdout if success else None,
                command_result=result,
                error_message=result.stderr if not success else ""
            )
            
        except Exception as e:
            return IdempotencyResult(
                check=check,
                success=False,
                current_state=None,
                error_message=str(e)
            )
    
    async def _collect_system_info(self) -> Dict[str, Any]:
        """Сбор информации о системе"""
        system_info = {}
        
        try:
            # Информация о системе
            result = await self.ssh_connector.execute_command("uname -a")
            if result.success:
                system_info["uname"] = result.stdout.strip()
            
            # Информация о дисках
            result = await self.ssh_connector.execute_command("df -h")
            if result.success:
                system_info["disk_usage"] = result.stdout.strip()
            
            # Информация о памяти
            result = await self.ssh_connector.execute_command("free -h")
            if result.success:
                system_info["memory"] = result.stdout.strip()
            
        except Exception as e:
            self.logger.warning("Ошибка сбора информации о системе", error=str(e))
        
        return system_info
    
    def _get_cache_key(self, check: IdempotencyCheck) -> str:
        """Генерация ключа кэша для проверки"""
        key_data = f"{check.check_type.value}:{check.target}:{check.check_command}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, result: IdempotencyResult) -> bool:
        """Проверка валидности кэшированного результата"""
        age = (datetime.now() - result.timestamp).total_seconds()
        return age < self.cache_ttl
    
    def get_system_status(self) -> Dict[str, Any]:
        """Получение статуса системы идемпотентности"""
        return {
            "snapshots_count": len(self.state_snapshots),
            "current_snapshot": self.current_snapshot.snapshot_id if self.current_snapshot else None,
            "cache_size": len(self.check_cache),
            "cache_ttl": self.cache_ttl
        }
