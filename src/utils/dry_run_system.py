"""
Dry-run система - Режим симуляции выполнения

Этот модуль отвечает за:
- Симуляцию выполнения команд без реального воздействия на систему
- Предварительный просмотр команд и их результатов
- Валидацию планов перед выполнением
- Анализ потенциальных рисков и проблем
- Генерацию отчетов о планируемых изменениях
"""
import time
import json
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ..models.command_result import CommandResult, ExecutionStatus
from ..utils.logger import StructuredLogger


class RiskLevel(Enum):
    """Уровни риска команд"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommandType(Enum):
    """Типы команд"""
    INSTALL = "install"
    CONFIGURE = "configure"
    START_SERVICE = "start_service"
    STOP_SERVICE = "stop_service"
    CREATE_FILE = "create_file"
    DELETE_FILE = "delete_file"
    CREATE_USER = "create_user"
    DELETE_USER = "delete_user"
    NETWORK = "network"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class CommandAnalysis:
    """Анализ команды"""
    
    command: str
    command_type: CommandType
    risk_level: RiskLevel
    potential_issues: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    estimated_duration: float = 0.0
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanValidationResult:
    """Результат валидации плана"""
    
    valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    estimated_duration: float = 0.0
    commands_analysis: List[CommandAnalysis] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class DryRunResult:
    """Результат dry-run выполнения"""
    
    success: bool
    simulated_commands: List[CommandResult] = field(default_factory=list)
    validation_result: Optional[PlanValidationResult] = None
    execution_summary: Dict[str, Any] = field(default_factory=dict)
    risk_summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DryRunSystem:
    """
    Система dry-run режима
    
    Основные возможности:
    - Симуляция выполнения команд
    - Анализ рисков и потенциальных проблем
    - Валидация планов перед выполнением
    - Генерация отчетов о планируемых изменениях
    - Предварительный просмотр результатов
    """
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        """
        Инициализация системы dry-run
        
        Args:
            logger: Логгер для записи событий
        """
        self.logger = logger or StructuredLogger("DryRunSystem")
        
        # Паттерны для анализа команд
        self.command_patterns = {
            CommandType.INSTALL: [
                r'apt-get install', r'apt install', r'yum install', r'dnf install',
                r'pip install', r'npm install', r'gem install'
            ],
            CommandType.CONFIGURE: [
                r'configure', r'config', r'setup', r'update', r'modify'
            ],
            CommandType.START_SERVICE: [
                r'systemctl start', r'service start', r'systemctl enable'
            ],
            CommandType.STOP_SERVICE: [
                r'systemctl stop', r'service stop', r'systemctl disable'
            ],
            CommandType.CREATE_FILE: [
                r'touch', r'echo.*>', r'cat.*>', r'tee'
            ],
            CommandType.DELETE_FILE: [
                r'rm ', r'unlink', r'rmdir'
            ],
            CommandType.CREATE_USER: [
                r'useradd', r'adduser', r'groupadd', r'addgroup'
            ],
            CommandType.DELETE_USER: [
                r'userdel', r'deluser', r'groupdel', r'delgroup'
            ],
            CommandType.NETWORK: [
                r'iptables', r'ufw', r'firewall', r'netstat', r'ss'
            ],
            CommandType.SYSTEM: [
                r'reboot', r'shutdown', r'halt', r'poweroff', r'init'
            ]
        }
        
        # Опасные команды и их уровни риска
        self.dangerous_commands = {
            RiskLevel.CRITICAL: [
                r'rm -rf /', r'dd if=/dev/zero', r'mkfs', r'fdisk', r'parted',
                r'> /dev/sda', r'chmod 777 /', r'chown -R root:root /',
                r'passwd root', r'userdel -r', r'groupdel', r'killall -9',
                r'pkill -9', r'halt', r'poweroff', r'reboot', r'shutdown'
            ],
            RiskLevel.HIGH: [
                r'rm -rf', r'dd ', r'mkfs', r'fdisk', r'chmod 777',
                r'chown -R', r'userdel', r'groupdel', r'killall',
                r'pkill', r'systemctl stop', r'service stop'
            ],
            RiskLevel.MEDIUM: [
                r'rm ', r'mv ', r'cp ', r'chmod', r'chown',
                r'systemctl', r'service', r'iptables', r'ufw'
            ]
        }
        
        self.logger.info("Dry-run система инициализирована")
    
    def simulate_execution(self, commands: List[str], context: Optional[Dict[str, Any]] = None) -> DryRunResult:
        """
        Симуляция выполнения списка команд
        
        Args:
            commands: Список команд для симуляции
            context: Контекст выполнения
            
        Returns:
            Результат симуляции
        """
        start_time = time.time()
        
        try:
            self.logger.info("Начало симуляции выполнения", commands_count=len(commands))
            
            # Анализируем команды
            commands_analysis = []
            simulated_results = []
            total_risk_score = 0
            requires_confirmation = False
            
            for i, command in enumerate(commands):
                # Анализируем команду
                analysis = self._analyze_command(command, i)
                commands_analysis.append(analysis)
                
                # Симулируем выполнение
                simulated_result = self._simulate_command_execution(command, analysis, context)
                simulated_results.append(simulated_result)
                
                # Считаем общий риск
                risk_score = self._get_risk_score(analysis.risk_level)
                total_risk_score += risk_score
                
                if analysis.requires_confirmation:
                    requires_confirmation = True
                
                # Небольшая задержка для реалистичности
                time.sleep(0.05)
            
            # Валидируем план
            validation_result = self._validate_plan(commands_analysis, context)
            
            # Генерируем сводку
            execution_summary = self._generate_execution_summary(simulated_results, commands_analysis)
            risk_summary = self._generate_risk_summary(commands_analysis, total_risk_score)
            recommendations = self._generate_recommendations(commands_analysis, validation_result)
            
            duration = time.time() - start_time
            
            result = DryRunResult(
                success=True,
                simulated_commands=simulated_results,
                validation_result=validation_result,
                execution_summary=execution_summary,
                risk_summary=risk_summary,
                recommendations=recommendations,
                metadata={
                    "simulation_duration": duration,
                    "commands_count": len(commands),
                    "requires_confirmation": requires_confirmation,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            self.logger.info(
                "Симуляция завершена",
                duration=duration,
                commands_count=len(commands),
                risk_level=risk_summary.get("overall_risk", "unknown")
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Ошибка симуляции: {str(e)}"
            self.logger.error("Ошибка симуляции выполнения", error=error_msg, duration=duration)
            
            return DryRunResult(
                success=False,
                metadata={
                    "error": error_msg,
                    "simulation_duration": duration,
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    def _analyze_command(self, command: str, index: int) -> CommandAnalysis:
        """Анализ команды"""
        import re
        
        command_lower = command.lower().strip()
        
        # Определяем тип команды
        command_type = CommandType.UNKNOWN
        for cmd_type, patterns in self.command_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    command_type = cmd_type
                    break
            if command_type != CommandType.UNKNOWN:
                break
        
        # Определяем уровень риска
        risk_level = RiskLevel.LOW
        for risk, patterns in self.dangerous_commands.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    risk_level = risk
                    break
            if risk_level != RiskLevel.LOW:
                break
        
        # Анализируем потенциальные проблемы
        potential_issues = self._identify_potential_issues(command, command_type, risk_level)
        
        # Определяем зависимости
        dependencies = self._identify_dependencies(command, command_type)
        
        # Определяем побочные эффекты
        side_effects = self._identify_side_effects(command, command_type)
        
        # Оцениваем время выполнения
        estimated_duration = self._estimate_duration(command, command_type)
        
        # Определяем, требуется ли подтверждение
        requires_confirmation = risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        
        return CommandAnalysis(
            command=command,
            command_type=command_type,
            risk_level=risk_level,
            potential_issues=potential_issues,
            dependencies=dependencies,
            side_effects=side_effects,
            estimated_duration=estimated_duration,
            requires_confirmation=requires_confirmation,
            metadata={
                "command_index": index,
                "analysis_timestamp": datetime.now().isoformat()
            }
        )
    
    def _simulate_command_execution(self, command: str, analysis: CommandAnalysis, 
                                  context: Optional[Dict[str, Any]] = None) -> CommandResult:
        """Симуляция выполнения команды"""
        # Имитируем время выполнения
        time.sleep(0.01)
        
        # Определяем успешность на основе анализа
        success = analysis.risk_level not in [RiskLevel.CRITICAL]
        
        # Генерируем реалистичный вывод
        stdout, stderr = self._generate_simulated_output(command, analysis, success)
        
        # Определяем exit code
        exit_code = 0 if success else 1
        
        return CommandResult(
            command=command,
            success=success,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration=analysis.estimated_duration,
            status=ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED,
            error_message=stderr if not success else None,
            metadata={
                "dry_run": True,
                "command_type": analysis.command_type.value,
                "risk_level": analysis.risk_level.value,
                "simulation_timestamp": datetime.now().isoformat(),
                "analysis": analysis.__dict__
            }
        )
    
    def _generate_simulated_output(self, command: str, analysis: CommandAnalysis, success: bool) -> Tuple[str, str]:
        """Генерация симулированного вывода команды"""
        command_lower = command.lower().strip()
        
        if success:
            # Генерируем успешный вывод
            if analysis.command_type == CommandType.INSTALL:
                return f"[DRY-RUN] Пакет будет установлен успешно", ""
            elif analysis.command_type == CommandType.START_SERVICE:
                return f"[DRY-RUN] Сервис будет запущен успешно", ""
            elif analysis.command_type == CommandType.CREATE_FILE:
                return f"[DRY-RUN] Файл будет создан успешно", ""
            elif analysis.command_type == CommandType.CREATE_USER:
                return f"[DRY-RUN] Пользователь будет создан успешно", ""
            else:
                return f"[DRY-RUN] Команда '{command}' будет выполнена успешно", ""
        else:
            # Генерируем вывод ошибки
            if analysis.risk_level == RiskLevel.CRITICAL:
                return "", f"[DRY-RUN] КРИТИЧЕСКАЯ КОМАНДА: {command} - требует подтверждения"
            elif analysis.risk_level == RiskLevel.HIGH:
                return "", f"[DRY-RUN] ВЫСОКИЙ РИСК: {command} - рекомендуется проверить"
            else:
                return "", f"[DRY-RUN] ПРЕДУПРЕЖДЕНИЕ: {command} - возможны проблемы"
    
    def _identify_potential_issues(self, command: str, command_type: CommandType, risk_level: RiskLevel) -> List[str]:
        """Идентификация потенциальных проблем"""
        issues = []
        
        if risk_level == RiskLevel.CRITICAL:
            issues.append("Команда может нанести критический ущерб системе")
        
        if command_type == CommandType.DELETE_FILE:
            issues.append("Возможна потеря данных")
        
        if command_type == CommandType.STOP_SERVICE:
            issues.append("Может нарушить работу сервисов")
        
        if command_type == CommandType.SYSTEM:
            issues.append("Может перезагрузить или выключить систему")
        
        if "rm -rf" in command.lower():
            issues.append("Рекурсивное удаление - высокий риск потери данных")
        
        if "chmod 777" in command.lower():
            issues.append("Слишком открытые права доступа - угроза безопасности")
        
        return issues
    
    def _identify_dependencies(self, command: str, command_type: CommandType) -> List[str]:
        """Идентификация зависимостей команды"""
        dependencies = []
        
        if command_type == CommandType.INSTALL:
            dependencies.append("Доступ к репозиторию пакетов")
            dependencies.append("Свободное место на диске")
        
        if command_type == CommandType.START_SERVICE:
            dependencies.append("Сервис должен быть установлен")
            dependencies.append("Конфигурация сервиса должна быть корректной")
        
        if command_type == CommandType.CREATE_USER:
            dependencies.append("Права администратора")
            dependencies.append("Уникальное имя пользователя")
        
        return dependencies
    
    def _identify_side_effects(self, command: str, command_type: CommandType) -> List[str]:
        """Идентификация побочных эффектов"""
        side_effects = []
        
        if command_type == CommandType.INSTALL:
            side_effects.append("Увеличение использования дискового пространства")
            side_effects.append("Возможные конфликты с существующими пакетами")
        
        if command_type == CommandType.START_SERVICE:
            side_effects.append("Использование системных ресурсов")
            side_effects.append("Открытие сетевых портов")
        
        if command_type == CommandType.CREATE_USER:
            side_effects.append("Создание домашней директории")
            side_effects.append("Изменение системных файлов")
        
        return side_effects
    
    def _estimate_duration(self, command: str, command_type: CommandType) -> float:
        """Оценка времени выполнения команды"""
        base_duration = 1.0  # секунды
        
        if command_type == CommandType.INSTALL:
            return base_duration * 5  # Установка пакетов дольше
        elif command_type == CommandType.START_SERVICE:
            return base_duration * 2  # Запуск сервисов
        elif command_type == CommandType.SYSTEM:
            return base_duration * 10  # Системные команды
        else:
            return base_duration
    
    def _get_risk_score(self, risk_level: RiskLevel) -> int:
        """Получение числового значения риска"""
        risk_scores = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4
        }
        return risk_scores.get(risk_level, 1)
    
    def _validate_plan(self, commands_analysis: List[CommandAnalysis], 
                      context: Optional[Dict[str, Any]] = None) -> PlanValidationResult:
        """Валидация плана выполнения"""
        issues = []
        warnings = []
        recommendations = []
        
        # Проверяем критические команды
        critical_commands = [cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.CRITICAL]
        if critical_commands:
            issues.append(f"Обнаружено {len(critical_commands)} критических команд")
            recommendations.append("Требуется ручное подтверждение для критических команд")
        
        # Проверяем команды высокого риска
        high_risk_commands = [cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.HIGH]
        if high_risk_commands:
            warnings.append(f"Обнаружено {len(high_risk_commands)} команд высокого риска")
            recommendations.append("Рекомендуется проверить команды высокого риска")
        
        # Проверяем зависимости
        for analysis in commands_analysis:
            if analysis.dependencies:
                warnings.append(f"Команда '{analysis.command}' имеет зависимости: {', '.join(analysis.dependencies)}")
        
        # Проверяем порядок выполнения
        install_commands = [cmd for cmd in commands_analysis if cmd.command_type == CommandType.INSTALL]
        start_commands = [cmd for cmd in commands_analysis if cmd.command_type == CommandType.START_SERVICE]
        
        if install_commands and start_commands:
            # Проверяем, что установка идет перед запуском
            install_indices = [i for i, cmd in enumerate(commands_analysis) if cmd.command_type == CommandType.INSTALL]
            start_indices = [i for i, cmd in enumerate(commands_analysis) if cmd.command_type == CommandType.START_SERVICE]
            
            if any(start_idx < max(install_indices) for start_idx in start_indices):
                warnings.append("Некоторые сервисы могут быть запущены до установки")
                recommendations.append("Убедитесь, что установка пакетов происходит перед запуском сервисов")
        
        # Оценка общего риска
        total_risk_score = sum(self._get_risk_score(cmd.risk_level) for cmd in commands_analysis)
        max_possible_score = len(commands_analysis) * 4  # Максимальный риск на команду
        
        risk_percentage = (total_risk_score / max_possible_score) * 100 if max_possible_score > 0 else 0
        
        risk_assessment = {
            "total_risk_score": total_risk_score,
            "max_possible_score": max_possible_score,
            "risk_percentage": risk_percentage,
            "critical_commands": len(critical_commands),
            "high_risk_commands": len(high_risk_commands),
            "medium_risk_commands": len([cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.MEDIUM]),
            "low_risk_commands": len([cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.LOW])
        }
        
        # Общая оценка времени
        estimated_duration = sum(cmd.estimated_duration for cmd in commands_analysis)
        
        return PlanValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            risk_assessment=risk_assessment,
            estimated_duration=estimated_duration,
            commands_analysis=commands_analysis,
            recommendations=recommendations
        )
    
    def _generate_execution_summary(self, simulated_results: List[CommandResult], 
                                  commands_analysis: List[CommandAnalysis]) -> Dict[str, Any]:
        """Генерация сводки выполнения"""
        total_commands = len(simulated_results)
        successful_commands = len([r for r in simulated_results if r.success])
        failed_commands = total_commands - successful_commands
        
        command_types = {}
        for analysis in commands_analysis:
            cmd_type = analysis.command_type.value
            command_types[cmd_type] = command_types.get(cmd_type, 0) + 1
        
        return {
            "total_commands": total_commands,
            "successful_commands": successful_commands,
            "failed_commands": failed_commands,
            "success_rate": (successful_commands / total_commands * 100) if total_commands > 0 else 0,
            "command_types": command_types,
            "estimated_total_duration": sum(r.duration for r in simulated_results),
            "requires_confirmation": any(analysis.requires_confirmation for analysis in commands_analysis)
        }
    
    def _generate_risk_summary(self, commands_analysis: List[CommandAnalysis], total_risk_score: int) -> Dict[str, Any]:
        """Генерация сводки рисков"""
        risk_counts = {
            "critical": len([cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.CRITICAL]),
            "high": len([cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.HIGH]),
            "medium": len([cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.MEDIUM]),
            "low": len([cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.LOW])
        }
        
        max_possible_score = len(commands_analysis) * 4
        risk_percentage = (total_risk_score / max_possible_score * 100) if max_possible_score > 0 else 0
        
        # Определяем общий уровень риска
        if risk_counts["critical"] > 0:
            overall_risk = "critical"
        elif risk_counts["high"] > 0:
            overall_risk = "high"
        elif risk_counts["medium"] > 0:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        return {
            "overall_risk": overall_risk,
            "risk_percentage": risk_percentage,
            "total_risk_score": total_risk_score,
            "risk_breakdown": risk_counts,
            "requires_confirmation": risk_counts["critical"] > 0 or risk_counts["high"] > 0
        }
    
    def _generate_recommendations(self, commands_analysis: List[CommandAnalysis], 
                                validation_result: PlanValidationResult) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []
        
        # Рекомендации на основе анализа команд
        critical_commands = [cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.CRITICAL]
        if critical_commands:
            recommendations.append("⚠️  Критические команды требуют ручного подтверждения")
            recommendations.append("🔍 Проверьте каждую критическую команду перед выполнением")
        
        high_risk_commands = [cmd for cmd in commands_analysis if cmd.risk_level == RiskLevel.HIGH]
        if high_risk_commands:
            recommendations.append("⚠️  Команды высокого риска требуют внимательного рассмотрения")
        
        # Рекомендации на основе валидации
        recommendations.extend(validation_result.recommendations)
        
        # Общие рекомендации
        if len(commands_analysis) > 10:
            recommendations.append("📋 Большое количество команд - рассмотрите разбиение на этапы")
        
        install_commands = [cmd for cmd in commands_analysis if cmd.command_type == CommandType.INSTALL]
        if install_commands:
            recommendations.append("📦 Убедитесь в наличии свободного места для установки пакетов")
        
        service_commands = [cmd for cmd in commands_analysis if cmd.command_type in [CommandType.START_SERVICE, CommandType.STOP_SERVICE]]
        if service_commands:
            recommendations.append("🔧 Проверьте зависимости сервисов перед их запуском/остановкой")
        
        return recommendations
    
    def generate_dry_run_report(self, dry_run_result: DryRunResult, format: str = "text") -> str:
        """
        Генерация отчета о dry-run выполнении
        
        Args:
            dry_run_result: Результат dry-run выполнения
            format: Формат отчета (text, json, markdown)
            
        Returns:
            Отчет в указанном формате
        """
        if format == "json":
            return self._generate_json_report(dry_run_result)
        elif format == "markdown":
            return self._generate_markdown_report(dry_run_result)
        else:
            return self._generate_text_report(dry_run_result)
    
    def _generate_text_report(self, dry_run_result: DryRunResult) -> str:
        """Генерация текстового отчета"""
        report_lines = [
            "=" * 60,
            "ОТЧЕТ О DRY-RUN ВЫПОЛНЕНИИ",
            "=" * 60,
            f"Время: {dry_run_result.metadata.get('timestamp', 'N/A')}",
            f"Длительность симуляции: {dry_run_result.metadata.get('simulation_duration', 0):.2f} сек",
            f"Количество команд: {dry_run_result.metadata.get('commands_count', 0)}",
            ""
        ]
        
        # Сводка выполнения
        if dry_run_result.execution_summary:
            summary = dry_run_result.execution_summary
            report_lines.extend([
                "СВОДКА ВЫПОЛНЕНИЯ:",
                f"  Всего команд: {summary.get('total_commands', 0)}",
                f"  Успешных: {summary.get('successful_commands', 0)}",
                f"  Неудачных: {summary.get('failed_commands', 0)}",
                f"  Процент успеха: {summary.get('success_rate', 0):.1f}%",
                f"  Оценочное время: {summary.get('estimated_total_duration', 0):.1f} сек",
                ""
            ])
        
        # Сводка рисков
        if dry_run_result.risk_summary:
            risk = dry_run_result.risk_summary
            report_lines.extend([
                "СВОДКА РИСКОВ:",
                f"  Общий уровень риска: {risk.get('overall_risk', 'unknown').upper()}",
                f"  Процент риска: {risk.get('risk_percentage', 0):.1f}%",
                f"  Требуется подтверждение: {'Да' if risk.get('requires_confirmation', False) else 'Нет'}",
                ""
            ])
            
            if risk.get('risk_breakdown'):
                breakdown = risk['risk_breakdown']
                report_lines.extend([
                    "  Распределение рисков:",
                    f"    Критические: {breakdown.get('critical', 0)}",
                    f"    Высокие: {breakdown.get('high', 0)}",
                    f"    Средние: {breakdown.get('medium', 0)}",
                    f"    Низкие: {breakdown.get('low', 0)}",
                    ""
                ])
        
        # Валидация плана
        if dry_run_result.validation_result:
            validation = dry_run_result.validation_result
            report_lines.extend([
                "ВАЛИДАЦИЯ ПЛАНА:",
                f"  План валиден: {'Да' if validation.valid else 'Нет'}",
                ""
            ])
            
            if validation.issues:
                report_lines.extend([
                    "  ПРОБЛЕМЫ:",
                    *[f"    ❌ {issue}" for issue in validation.issues],
                    ""
                ])
            
            if validation.warnings:
                report_lines.extend([
                    "  ПРЕДУПРЕЖДЕНИЯ:",
                    *[f"    ⚠️  {warning}" for warning in validation.warnings],
                    ""
                ])
        
        # Рекомендации
        if dry_run_result.recommendations:
            report_lines.extend([
                "РЕКОМЕНДАЦИИ:",
                *[f"  {rec}" for rec in dry_run_result.recommendations],
                ""
            ])
        
        # Детали команд
        if dry_run_result.simulated_commands:
            report_lines.extend([
                "ДЕТАЛИ КОМАНД:",
                ""
            ])
            
            for i, result in enumerate(dry_run_result.simulated_commands, 1):
                status = "✅" if result.success else "❌"
                risk_level = result.metadata.get('risk_level', 'unknown')
                
                report_lines.extend([
                    f"  {i}. {status} {result.command}",
                    f"     Статус: {'Успешно' if result.success else 'Ошибка'}",
                    f"     Риск: {risk_level.upper()}",
                    f"     Время: {result.duration:.1f} сек",
                    ""
                ])
                
                if result.stdout:
                    report_lines.append(f"     Вывод: {result.stdout}")
                if result.stderr:
                    report_lines.append(f"     Ошибка: {result.stderr}")
                report_lines.append("")
        
        report_lines.extend([
            "=" * 60,
            "КОНЕЦ ОТЧЕТА",
            "=" * 60
        ])
        
        return "\n".join(report_lines)
    
    def _generate_json_report(self, dry_run_result: DryRunResult) -> str:
        """Генерация JSON отчета"""
        report_data = {
            "dry_run_result": {
                "success": dry_run_result.success,
                "execution_summary": dry_run_result.execution_summary,
                "risk_summary": dry_run_result.risk_summary,
                "validation_result": {
                    "valid": dry_run_result.validation_result.valid if dry_run_result.validation_result else None,
                    "issues": dry_run_result.validation_result.issues if dry_run_result.validation_result else [],
                    "warnings": dry_run_result.validation_result.warnings if dry_run_result.validation_result else [],
                    "risk_assessment": dry_run_result.validation_result.risk_assessment if dry_run_result.validation_result else {}
                } if dry_run_result.validation_result else None,
                "recommendations": dry_run_result.recommendations,
                "metadata": dry_run_result.metadata
            },
            "simulated_commands": [
                {
                    "command": cmd.command,
                    "success": cmd.success,
                    "exit_code": cmd.exit_code,
                    "stdout": cmd.stdout,
                    "stderr": cmd.stderr,
                    "duration": cmd.duration,
                    "metadata": cmd.metadata
                }
                for cmd in dry_run_result.simulated_commands
            ]
        }
        
        return json.dumps(report_data, indent=2, ensure_ascii=False)
    
    def _generate_markdown_report(self, dry_run_result: DryRunResult) -> str:
        """Генерация Markdown отчета"""
        report_lines = [
            "# Отчет о Dry-Run Выполнении",
            "",
            f"**Время:** {dry_run_result.metadata.get('timestamp', 'N/A')}",
            f"**Длительность симуляции:** {dry_run_result.metadata.get('simulation_duration', 0):.2f} сек",
            f"**Количество команд:** {dry_run_result.metadata.get('commands_count', 0)}",
            ""
        ]
        
        # Сводка выполнения
        if dry_run_result.execution_summary:
            summary = dry_run_result.execution_summary
            report_lines.extend([
                "## Сводка Выполнения",
                "",
                f"- **Всего команд:** {summary.get('total_commands', 0)}",
                f"- **Успешных:** {summary.get('successful_commands', 0)}",
                f"- **Неудачных:** {summary.get('failed_commands', 0)}",
                f"- **Процент успеха:** {summary.get('success_rate', 0):.1f}%",
                f"- **Оценочное время:** {summary.get('estimated_total_duration', 0):.1f} сек",
                ""
            ])
        
        # Сводка рисков
        if dry_run_result.risk_summary:
            risk = dry_run_result.risk_summary
            report_lines.extend([
                "## Сводка Рисков",
                "",
                f"- **Общий уровень риска:** {risk.get('overall_risk', 'unknown').upper()}",
                f"- **Процент риска:** {risk.get('risk_percentage', 0):.1f}%",
                f"- **Требуется подтверждение:** {'Да' if risk.get('requires_confirmation', False) else 'Нет'}",
                ""
            ])
        
        # Рекомендации
        if dry_run_result.recommendations:
            report_lines.extend([
                "## Рекомендации",
                ""
            ])
            for rec in dry_run_result.recommendations:
                report_lines.append(f"- {rec}")
            report_lines.append("")
        
        # Детали команд
        if dry_run_result.simulated_commands:
            report_lines.extend([
                "## Детали Команд",
                ""
            ])
            
            for i, result in enumerate(dry_run_result.simulated_commands, 1):
                status = "✅" if result.success else "❌"
                risk_level = result.metadata.get('risk_level', 'unknown')
                
                report_lines.extend([
                    f"### {i}. {result.command}",
                    "",
                    f"- **Статус:** {'Успешно' if result.success else 'Ошибка'} {status}",
                    f"- **Риск:** {risk_level.upper()}",
                    f"- **Время:** {result.duration:.1f} сек",
                    ""
                ])
                
                if result.stdout:
                    report_lines.extend([
                        "**Вывод:**",
                        "```",
                        result.stdout,
                        "```",
                        ""
                    ])
                
                if result.stderr:
                    report_lines.extend([
                        "**Ошибка:**",
                        "```",
                        result.stderr,
                        "```",
                        ""
                    ])
        
        return "\n".join(report_lines)
