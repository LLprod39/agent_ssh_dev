"""
Система health-check для проверки состояния сервисов и команд
"""
import subprocess
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from ..utils.logger import StructuredLogger


class HealthCheckStatus(Enum):
    """Статус health-check"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Результат health-check"""
    
    check_name: str
    command: str
    status: HealthCheckStatus
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    duration: Optional[float] = None
    expected_output: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class HealthCheckConfig:
    """Конфигурация health-check"""
    
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    expected_exit_code: int = 0
    expected_output_pattern: Optional[str] = None
    critical: bool = True
    description: str = ""


class HealthChecker:
    """
    Система health-check для проверки состояния системы
    
    Основные возможности:
    - Выполнение health-check команд
    - Проверка статуса сервисов
    - Мониторинг ресурсов системы
    - Валидация результатов команд
    - Агрегация результатов проверок
    """
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger("HealthChecker")
        self.health_check_configs = self._initialize_health_check_configs()
    
    def _initialize_health_check_configs(self) -> Dict[str, HealthCheckConfig]:
        """Инициализация конфигураций health-check"""
        return {
            "system_running": HealthCheckConfig(
                timeout=10,
                retry_count=2,
                expected_output_pattern=r"running|degraded",
                critical=True,
                description="Проверка состояния системы"
            ),
            "service_active": HealthCheckConfig(
                timeout=15,
                retry_count=3,
                expected_output_pattern=r"active",
                critical=True,
                description="Проверка активности сервиса"
            ),
            "port_listening": HealthCheckConfig(
                timeout=10,
                retry_count=2,
                expected_output_pattern=r"LISTEN",
                critical=True,
                description="Проверка прослушивания порта"
            ),
            "disk_space": HealthCheckConfig(
                timeout=10,
                retry_count=1,
                expected_output_pattern=r"^\d+$",
                critical=True,
                description="Проверка дискового пространства"
            ),
            "memory_usage": HealthCheckConfig(
                timeout=10,
                retry_count=1,
                expected_output_pattern=r"^\d+\.?\d*%$",
                critical=False,
                description="Проверка использования памяти"
            ),
            "http_response": HealthCheckConfig(
                timeout=30,
                retry_count=3,
                expected_output_pattern=r"^[23]\d\d$",
                critical=True,
                description="Проверка HTTP ответа"
            )
        }
    
    def run_health_check(self, command: str, check_type: str = "general", 
                        config: Optional[HealthCheckConfig] = None) -> HealthCheckResult:
        """
        Выполнение health-check команды
        
        Args:
            command: Команда для выполнения
            check_type: Тип проверки
            config: Конфигурация проверки
            
        Returns:
            Результат health-check
        """
        if config is None:
            config = self.health_check_configs.get(check_type, HealthCheckConfig())
        
        start_time = time.time()
        
        try:
            self.logger.debug(f"Выполнение health-check: {command}")
            
            # Выполняем команду с повторными попытками
            for attempt in range(config.retry_count):
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=config.timeout
                    )
                    
                    duration = time.time() - start_time
                    
                    # Анализируем результат
                    status = self._analyze_result(result, config)
                    
                    health_result = HealthCheckResult(
                        check_name=check_type,
                        command=command,
                        status=status,
                        output=result.stdout.strip() if result.stdout else None,
                        error=result.stderr.strip() if result.stderr else None,
                        exit_code=result.returncode,
                        duration=duration,
                        expected_output=config.expected_output_pattern,
                        metadata={
                            "attempt": attempt + 1,
                            "timeout": config.timeout,
                            "critical": config.critical
                        }
                    )
                    
                    # Если проверка прошла успешно или это не критическая проверка, возвращаем результат
                    if status == HealthCheckStatus.PASSED or not config.critical:
                        self.logger.debug(f"Health-check завершен: {status.value}")
                        return health_result
                    
                    # Если это критическая проверка и она не прошла, ждем перед повторной попыткой
                    if attempt < config.retry_count - 1:
                        time.sleep(config.retry_delay)
                        self.logger.debug(f"Повторная попытка health-check ({attempt + 2}/{config.retry_count})")
                    
                except subprocess.TimeoutExpired:
                    duration = time.time() - start_time
                    self.logger.warning(f"Таймаут health-check: {command}")
                    
                    if attempt < config.retry_count - 1:
                        time.sleep(config.retry_delay)
                        continue
                    
                    return HealthCheckResult(
                        check_name=check_type,
                        command=command,
                        status=HealthCheckStatus.FAILED,
                        error=f"Таймаут выполнения ({config.timeout}s)",
                        duration=duration,
                        metadata={"attempt": attempt + 1, "timeout": config.timeout}
                    )
            
            # Если все попытки исчерпаны
            duration = time.time() - start_time
            return HealthCheckResult(
                check_name=check_type,
                command=command,
                status=HealthCheckStatus.FAILED,
                error="Все попытки исчерпаны",
                duration=duration,
                metadata={"attempts": config.retry_count}
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Ошибка выполнения health-check: {str(e)}"
            self.logger.error(error_msg)
            
            return HealthCheckResult(
                check_name=check_type,
                command=command,
                status=HealthCheckStatus.FAILED,
                error=error_msg,
                duration=duration
            )
    
    def _analyze_result(self, result: subprocess.CompletedProcess, 
                       config: HealthCheckConfig) -> HealthCheckStatus:
        """Анализ результата выполнения команды"""
        # Проверяем код возврата
        if result.returncode != config.expected_exit_code:
            return HealthCheckStatus.FAILED
        
        # Если нет ожидаемого паттерна, считаем успешным
        if not config.expected_output_pattern:
            return HealthCheckStatus.PASSED
        
        # Проверяем соответствие паттерну
        output = result.stdout.strip() if result.stdout else ""
        if re.search(config.expected_output_pattern, output, re.IGNORECASE):
            return HealthCheckStatus.PASSED
        
        # Проверяем на предупреждения
        if "warning" in output.lower() or "warn" in output.lower():
            return HealthCheckStatus.WARNING
        
        return HealthCheckStatus.FAILED
    
    def check_service_status(self, service_name: str) -> HealthCheckResult:
        """Проверка статуса сервиса"""
        command = f"systemctl is-active {service_name}"
        return self.run_health_check(command, "service_active")
    
    def check_port_listening(self, port: int, protocol: str = "tcp") -> HealthCheckResult:
        """Проверка прослушивания порта"""
        command = f"netstat -tlnp | grep :{port}"
        return self.run_health_check(command, "port_listening")
    
    def check_http_endpoint(self, url: str) -> HealthCheckResult:
        """Проверка HTTP endpoint"""
        command = f"curl -s -o /dev/null -w '%{{http_code}}' {url}"
        return self.run_health_check(command, "http_response")
    
    def check_disk_space(self, threshold: int = 90) -> HealthCheckResult:
        """Проверка дискового пространства"""
        command = f"df -h | awk 'NR>1 {{gsub(/%/, \"\", $5); if($5 > {threshold}) exit 1}}'"
        config = HealthCheckConfig(
            expected_exit_code=0,
            critical=True,
            description=f"Проверка дискового пространства (порог: {threshold}%)"
        )
        return self.run_health_check(command, "disk_space", config)
    
    def check_memory_usage(self, threshold: int = 90) -> HealthCheckResult:
        """Проверка использования памяти"""
        command = f"free | awk 'NR==2{{printf \"%.2f%%\", $3*100/$2}}' | sed 's/%//' | awk '$1 > {threshold} {{exit 1}}'"
        config = HealthCheckConfig(
            expected_exit_code=0,
            critical=False,
            description=f"Проверка использования памяти (порог: {threshold}%)"
        )
        return self.run_health_check(command, "memory_usage", config)
    
    def check_system_health(self) -> List[HealthCheckResult]:
        """Комплексная проверка состояния системы"""
        checks = [
            self.run_health_check("systemctl is-system-running", "system_running"),
            self.check_disk_space(),
            self.check_memory_usage()
        ]
        
        return checks
    
    def check_nginx_health(self) -> List[HealthCheckResult]:
        """Проверка состояния Nginx"""
        checks = [
            self.check_service_status("nginx"),
            self.run_health_check("nginx -t", "nginx_config"),
            self.check_http_endpoint("http://localhost"),
            self.check_port_listening(80),
            self.check_port_listening(443)
        ]
        
        return checks
    
    def check_postgresql_health(self) -> List[HealthCheckResult]:
        """Проверка состояния PostgreSQL"""
        checks = [
            self.check_service_status("postgresql"),
            self.run_health_check("sudo -u postgres psql -c 'SELECT 1;'", "postgresql_connection"),
            self.check_port_listening(5432)
        ]
        
        return checks
    
    def check_docker_health(self) -> List[HealthCheckResult]:
        """Проверка состояния Docker"""
        checks = [
            self.check_service_status("docker"),
            self.run_health_check("docker --version", "docker_version"),
            self.run_health_check("docker ps", "docker_containers"),
            self.run_health_check("docker system df", "docker_disk_usage")
        ]
        
        return checks
    
    def run_multiple_checks(self, commands: List[str], check_type: str = "general") -> List[HealthCheckResult]:
        """Выполнение множественных проверок"""
        results = []
        
        for command in commands:
            result = self.run_health_check(command, check_type)
            results.append(result)
        
        return results
    
    def aggregate_results(self, results: List[HealthCheckResult]) -> Dict[str, Any]:
        """Агрегация результатов проверок"""
        total_checks = len(results)
        passed_checks = len([r for r in results if r.status == HealthCheckStatus.PASSED])
        failed_checks = len([r for r in results if r.status == HealthCheckStatus.FAILED])
        warning_checks = len([r for r in results if r.status == HealthCheckStatus.WARNING])
        unknown_checks = len([r for r in results if r.status == HealthCheckStatus.UNKNOWN])
        
        critical_failures = len([
            r for r in results 
            if r.status == HealthCheckStatus.FAILED and r.metadata.get("critical", False)
        ])
        
        overall_status = HealthCheckStatus.PASSED
        if critical_failures > 0:
            overall_status = HealthCheckStatus.FAILED
        elif failed_checks > 0:
            overall_status = HealthCheckStatus.WARNING
        elif warning_checks > 0:
            overall_status = HealthCheckStatus.WARNING
        
        return {
            "overall_status": overall_status.value,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "unknown_checks": unknown_checks,
            "critical_failures": critical_failures,
            "success_rate": (passed_checks / total_checks * 100) if total_checks > 0 else 0,
            "results": [
                {
                    "check_name": r.check_name,
                    "command": r.command,
                    "status": r.status.value,
                    "output": r.output,
                    "error": r.error,
                    "duration": r.duration,
                    "critical": r.metadata.get("critical", False)
                }
                for r in results
            ]
        }
    
    def validate_command_output(self, command: str, expected_pattern: str, 
                              timeout: int = 30) -> Tuple[bool, str]:
        """
        Валидация вывода команды по паттерну
        
        Args:
            command: Команда для выполнения
            expected_pattern: Ожидаемый паттерн
            timeout: Таймаут выполнения
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return False, f"Команда завершилась с кодом {result.returncode}: {result.stderr}"
            
            output = result.stdout.strip()
            if re.search(expected_pattern, output, re.IGNORECASE):
                return True, f"Паттерн найден в выводе: {output}"
            else:
                return False, f"Паттерн не найден в выводе: {output}"
                
        except subprocess.TimeoutExpired:
            return False, f"Таймаут выполнения команды ({timeout}s)"
        except Exception as e:
            return False, f"Ошибка выполнения команды: {str(e)}"
    
    def get_health_summary(self, results: List[HealthCheckResult]) -> str:
        """Получение краткого отчета о состоянии системы"""
        if not results:
            return "Нет данных о проверках"
        
        passed = len([r for r in results if r.status == HealthCheckStatus.PASSED])
        failed = len([r for r in results if r.status == HealthCheckStatus.FAILED])
        warning = len([r for r in results if r.status == HealthCheckStatus.WARNING])
        
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        summary = f"Проверок выполнено: {total}, успешно: {passed}, ошибок: {failed}, предупреждений: {warning}"
        summary += f"\nУспешность: {success_rate:.1f}%"
        
        if failed > 0:
            failed_checks = [r.check_name for r in results if r.status == HealthCheckStatus.FAILED]
            summary += f"\nНеудачные проверки: {', '.join(failed_checks)}"
        
        return summary

