"""
Utilities module for SSH Agent.

This module contains utility classes and helper functions.
"""

try:
    from .logger import LoggerSetup
    from .validator import CommandValidator
    from .formatter import OutputFormatter
    from .command_generator import LinuxCommandGenerator, CommandTemplate
    from .health_checker import HealthChecker, HealthCheckResult, HealthCheckStatus, HealthCheckConfig
    from .autocorrection import AutocorrectionEngine, CorrectionStrategy
except ImportError:
    # Игнорируем ошибки импорта для совместимости
    pass

__all__ = [
    "LoggerSetup", 
    "CommandValidator", 
    "OutputFormatter",
    "LinuxCommandGenerator",
    "CommandTemplate",
    "HealthChecker",
    "HealthCheckResult",
    "HealthCheckStatus",
    "HealthCheckConfig",
    "AutocorrectionEngine",
    "CorrectionStrategy"
]
