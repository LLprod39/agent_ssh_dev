"""
Модели результатов выполнения команд
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class ExecutionStatus(Enum):
    """Статус выполнения команды"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class CommandResult:
    """Результат выполнения команды"""
    
    def __init__(
        self,
        command: str,
        success: bool,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        duration: Optional[float] = None,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.command = command
        self.success = success
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration or 0.0
        self.status = status
        self.error_message = error_message
        self.retry_count = retry_count
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    @property
    def failed(self) -> bool:
        """Проверка неуспешности выполнения команды"""
        return not self.success
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'command': self.command,
            'success': self.success,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'duration': self.duration,
            'status': self.status.value,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"Command: {self.command} | Status: {status} | Exit Code: {self.exit_code}"
    
    def __repr__(self) -> str:
        return f"CommandResult(command='{self.command}', success={self.success}, status={self.status.value})"
