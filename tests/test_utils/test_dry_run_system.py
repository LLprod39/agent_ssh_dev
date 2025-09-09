#!/usr/bin/env python3
"""
Тесты для Dry-Run системы

Тестирует:
- Симуляцию выполнения команд
- Анализ рисков и потенциальных проблем
- Валидацию планов
- Генерацию отчетов
"""

import unittest
import json
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.utils.dry_run_system import (
    DryRunSystem, DryRunResult, CommandAnalysis, PlanValidationResult,
    RiskLevel, CommandType
)
from src.utils.logger import StructuredLogger


class TestDryRunSystem(unittest.TestCase):
    """Тесты для DryRunSystem"""
    
    def setUp(self):
        """Настройка тестов"""
        self.logger = Mock(spec=StructuredLogger)
        self.dry_run_system = DryRunSystem(self.logger)
    
    def test_initialization(self):
        """Тест инициализации системы"""
        self.assertIsNotNone(self.dry_run_system)
        self.assertIsNotNone(self.dry_run_system.command_patterns)
        self.assertIsNotNone(self.dry_run_system.dangerous_commands)
        self.assertEqual(self.dry_run_system.logger, self.logger)
    
    def test_simulate_execution_success(self):
        """Тест успешной симуляции выполнения"""
        commands = [
            "apt update",
            "apt install -y nginx",
            "systemctl start nginx"
        ]
        
        result = self.dry_run_system.simulate_execution(commands)
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.simulated_commands), 3)
        self.assertIsNotNone(result.execution_summary)
        self.assertIsNotNone(result.risk_summary)
        self.assertIsNotNone(result.validation_result)
    
    def test_simulate_execution_with_context(self):
        """Тест симуляции с контекстом"""
        commands = ["apt update"]
        context = {
            "server_os": "ubuntu",
            "user": "root",
            "task_type": "package_install"
        }
        
        result = self.dry_run_system.simulate_execution(commands, context)
        
        self.assertTrue(result.success)
        self.assertIn("timestamp", result.metadata)
        self.assertEqual(result.metadata.get("commands_count"), 1)
    
    def test_analyze_command_safe(self):
        """Тест анализа безопасной команды"""
        command = "apt update"
        analysis = self.dry_run_system._analyze_command(command, 0)
        
        self.assertEqual(analysis.command, command)
        self.assertEqual(analysis.risk_level, RiskLevel.LOW)
        self.assertFalse(analysis.requires_confirmation)
        self.assertGreater(analysis.estimated_duration, 0)
    
    def test_analyze_command_dangerous(self):
        """Тест анализа опасной команды"""
        command = "rm -rf /"
        analysis = self.dry_run_system._analyze_command(command, 0)
        
        self.assertEqual(analysis.command, command)
        self.assertEqual(analysis.risk_level, RiskLevel.CRITICAL)
        self.assertTrue(analysis.requires_confirmation)
        self.assertGreater(len(analysis.potential_issues), 0)
    
    def test_analyze_command_types(self):
        """Тест определения типов команд"""
        test_cases = [
            ("apt install nginx", CommandType.INSTALL),
            ("systemctl start nginx", CommandType.START_SERVICE),
            ("systemctl stop nginx", CommandType.STOP_SERVICE),
            ("touch /tmp/test", CommandType.CREATE_FILE),
            ("rm /tmp/test", CommandType.DELETE_FILE),
            ("useradd testuser", CommandType.CREATE_USER),
            ("iptables -L", CommandType.NETWORK),
            ("reboot", CommandType.SYSTEM)
        ]
        
        for command, expected_type in test_cases:
            with self.subTest(command=command):
                analysis = self.dry_run_system._analyze_command(command, 0)
                self.assertEqual(analysis.command_type, expected_type)
    
    def test_risk_levels(self):
        """Тест определения уровней риска"""
        test_cases = [
            ("apt update", RiskLevel.LOW),
            ("rm -rf /tmp/test", RiskLevel.MEDIUM),
            ("chmod 777 /var/www", RiskLevel.HIGH),
            ("rm -rf /", RiskLevel.CRITICAL)
        ]
        
        for command, expected_risk in test_cases:
            with self.subTest(command=command):
                analysis = self.dry_run_system._analyze_command(command, 0)
                self.assertEqual(analysis.risk_level, expected_risk)
    
    def test_simulate_command_execution(self):
        """Тест симуляции выполнения команды"""
        command = "apt update"
        analysis = self.dry_run_system._analyze_command(command, 0)
        
        result = self.dry_run_system._simulate_command_execution(command, analysis)
        
        self.assertEqual(result.command, command)
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("[DRY-RUN]", result.stdout)
        self.assertTrue(result.metadata.get("dry_run"))
    
    def test_simulate_command_execution_failed(self):
        """Тест симуляции неудачного выполнения команды"""
        command = "rm -rf /"
        analysis = self.dry_run_system._analyze_command(command, 0)
        
        result = self.dry_run_system._simulate_command_execution(command, analysis)
        
        self.assertEqual(result.command, command)
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("[DRY-RUN]", result.stderr)
    
    def test_validate_plan_valid(self):
        """Тест валидации валидного плана"""
        commands_analysis = [
            self.dry_run_system._analyze_command("apt update", 0),
            self.dry_run_system._analyze_command("apt install nginx", 1)
        ]
        
        result = self.dry_run_system._validate_plan(commands_analysis)
        
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        self.assertGreater(result.estimated_duration, 0)
    
    def test_validate_plan_with_critical_commands(self):
        """Тест валидации плана с критическими командами"""
        commands_analysis = [
            self.dry_run_system._analyze_command("apt update", 0),
            self.dry_run_system._analyze_command("rm -rf /", 1)
        ]
        
        result = self.dry_run_system._validate_plan(commands_analysis)
        
        self.assertFalse(result.valid)
        self.assertGreater(len(result.issues), 0)
        self.assertIn("критических команд", result.issues[0])
    
    def test_generate_execution_summary(self):
        """Тест генерации сводки выполнения"""
        commands = ["apt update", "apt install nginx"]
        result = self.dry_run_system.simulate_execution(commands)
        
        summary = result.execution_summary
        
        self.assertEqual(summary["total_commands"], 2)
        self.assertGreaterEqual(summary["successful_commands"], 0)
        self.assertGreaterEqual(summary["success_rate"], 0)
        self.assertIn("command_types", summary)
    
    def test_generate_risk_summary(self):
        """Тест генерации сводки рисков"""
        commands = ["apt update", "rm -rf /tmp/test", "chmod 777 /var/www"]
        result = self.dry_run_system.simulate_execution(commands)
        
        risk_summary = result.risk_summary
        
        self.assertIn("overall_risk", risk_summary)
        self.assertIn("risk_percentage", risk_summary)
        self.assertIn("risk_breakdown", risk_summary)
        self.assertIn("requires_confirmation", risk_summary)
    
    def test_generate_recommendations(self):
        """Тест генерации рекомендаций"""
        commands = ["apt update", "rm -rf /", "systemctl start nginx"]
        result = self.dry_run_system.simulate_execution(commands)
        
        recommendations = result.recommendations
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        # Проверяем, что есть рекомендации для критических команд
        critical_recs = [rec for rec in recommendations if "критическ" in rec.lower()]
        self.assertGreater(len(critical_recs), 0)
    
    def test_generate_text_report(self):
        """Тест генерации текстового отчета"""
        commands = ["apt update", "apt install nginx"]
        result = self.dry_run_system.simulate_execution(commands)
        
        report = self.dry_run_system.generate_dry_run_report(result, "text")
        
        self.assertIsInstance(report, str)
        self.assertIn("ОТЧЕТ О DRY-RUN ВЫПОЛНЕНИИ", report)
        self.assertIn("СВОДКА ВЫПОЛНЕНИЯ", report)
        self.assertIn("СВОДКА РИСКОВ", report)
        self.assertIn("КОНЕЦ ОТЧЕТА", report)
    
    def test_generate_json_report(self):
        """Тест генерации JSON отчета"""
        commands = ["apt update", "apt install nginx"]
        result = self.dry_run_system.simulate_execution(commands)
        
        report = self.dry_run_system.generate_dry_run_report(result, "json")
        
        self.assertIsInstance(report, str)
        # Проверяем, что это валидный JSON
        json_data = json.loads(report)
        self.assertIn("dry_run_result", json_data)
        self.assertIn("simulated_commands", json_data)
    
    def test_generate_markdown_report(self):
        """Тест генерации Markdown отчета"""
        commands = ["apt update", "apt install nginx"]
        result = self.dry_run_system.simulate_execution(commands)
        
        report = self.dry_run_system.generate_dry_run_report(result, "markdown")
        
        self.assertIsInstance(report, str)
        self.assertIn("# Отчет о Dry-Run Выполнении", report)
        self.assertIn("## Сводка Выполнения", report)
        self.assertIn("## Сводка Рисков", report)
    
    def test_identify_potential_issues(self):
        """Тест идентификации потенциальных проблем"""
        # Тест критической команды
        issues = self.dry_run_system._identify_potential_issues(
            "rm -rf /", CommandType.DELETE_FILE, RiskLevel.CRITICAL
        )
        self.assertGreater(len(issues), 0)
        self.assertIn("крический ущерб", issues[0])
        
        # Тест команды удаления файла
        issues = self.dry_run_system._identify_potential_issues(
            "rm /tmp/test", CommandType.DELETE_FILE, RiskLevel.MEDIUM
        )
        self.assertIn("потеря данных", issues[0])
    
    def test_identify_dependencies(self):
        """Тест идентификации зависимостей"""
        # Тест установки пакета
        deps = self.dry_run_system._identify_dependencies(
            "apt install nginx", CommandType.INSTALL
        )
        self.assertIn("Доступ к репозиторию пакетов", deps)
        self.assertIn("Свободное место на диске", deps)
        
        # Тест запуска сервиса
        deps = self.dry_run_system._identify_dependencies(
            "systemctl start nginx", CommandType.START_SERVICE
        )
        self.assertIn("Сервис должен быть установлен", deps)
    
    def test_identify_side_effects(self):
        """Тест идентификации побочных эффектов"""
        # Тест установки пакета
        effects = self.dry_run_system._identify_side_effects(
            "apt install nginx", CommandType.INSTALL
        )
        self.assertIn("Увеличение использования дискового пространства", effects)
        
        # Тест запуска сервиса
        effects = self.dry_run_system._identify_side_effects(
            "systemctl start nginx", CommandType.START_SERVICE
        )
        self.assertIn("Использование системных ресурсов", effects)
    
    def test_estimate_duration(self):
        """Тест оценки времени выполнения"""
        # Тест установки пакета
        duration = self.dry_run_system._estimate_duration(
            "apt install nginx", CommandType.INSTALL
        )
        self.assertGreater(duration, 1.0)
        
        # Тест системной команды
        duration = self.dry_run_system._estimate_duration(
            "reboot", CommandType.SYSTEM
        )
        self.assertGreater(duration, 5.0)
    
    def test_get_risk_score(self):
        """Тест получения числового значения риска"""
        self.assertEqual(self.dry_run_system._get_risk_score(RiskLevel.LOW), 1)
        self.assertEqual(self.dry_run_system._get_risk_score(RiskLevel.MEDIUM), 2)
        self.assertEqual(self.dry_run_system._get_risk_score(RiskLevel.HIGH), 3)
        self.assertEqual(self.dry_run_system._get_risk_score(RiskLevel.CRITICAL), 4)
    
    def test_error_handling(self):
        """Тест обработки ошибок"""
        # Тест с пустым списком команд
        result = self.dry_run_system.simulate_execution([])
        self.assertTrue(result.success)
        self.assertEqual(len(result.simulated_commands), 0)
        
        # Тест с некорректным контекстом
        result = self.dry_run_system.simulate_execution(["apt update"], {"invalid": "context"})
        self.assertTrue(result.success)
    
    def test_logger_integration(self):
        """Тест интеграции с логгером"""
        commands = ["apt update"]
        
        with patch.object(self.logger, 'info') as mock_info:
            self.dry_run_system.simulate_execution(commands)
            mock_info.assert_called()
    
    def test_metadata_generation(self):
        """Тест генерации метаданных"""
        commands = ["apt update", "apt install nginx"]
        result = self.dry_run_system.simulate_execution(commands)
        
        metadata = result.metadata
        
        self.assertIn("timestamp", metadata)
        self.assertIn("commands_count", metadata)
        self.assertIn("simulation_duration", metadata)
        self.assertEqual(metadata["commands_count"], 2)


class TestCommandAnalysis(unittest.TestCase):
    """Тесты для CommandAnalysis"""
    
    def test_command_analysis_creation(self):
        """Тест создания анализа команды"""
        analysis = CommandAnalysis(
            command="apt update",
            command_type=CommandType.INSTALL,
            risk_level=RiskLevel.LOW,
            potential_issues=["test issue"],
            dependencies=["test dependency"],
            side_effects=["test effect"],
            estimated_duration=5.0,
            requires_confirmation=False,
            metadata={"test": "value"}
        )
        
        self.assertEqual(analysis.command, "apt update")
        self.assertEqual(analysis.command_type, CommandType.INSTALL)
        self.assertEqual(analysis.risk_level, RiskLevel.LOW)
        self.assertEqual(len(analysis.potential_issues), 1)
        self.assertEqual(len(analysis.dependencies), 1)
        self.assertEqual(len(analysis.side_effects), 1)
        self.assertEqual(analysis.estimated_duration, 5.0)
        self.assertFalse(analysis.requires_confirmation)
        self.assertEqual(analysis.metadata["test"], "value")


class TestPlanValidationResult(unittest.TestCase):
    """Тесты для PlanValidationResult"""
    
    def test_plan_validation_result_creation(self):
        """Тест создания результата валидации плана"""
        result = PlanValidationResult(
            valid=True,
            issues=["test issue"],
            warnings=["test warning"],
            risk_assessment={"test": "assessment"},
            estimated_duration=10.0,
            commands_analysis=[],
            recommendations=["test recommendation"]
        )
        
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(len(result.warnings), 1)
        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.estimated_duration, 10.0)


class TestDryRunResult(unittest.TestCase):
    """Тесты для DryRunResult"""
    
    def test_dry_run_result_creation(self):
        """Тест создания результата dry-run"""
        result = DryRunResult(
            success=True,
            simulated_commands=[],
            validation_result=None,
            execution_summary={"test": "summary"},
            risk_summary={"test": "risk"},
            recommendations=["test recommendation"],
            metadata={"test": "metadata"}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(len(result.simulated_commands), 0)
        self.assertIsNone(result.validation_result)
        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.metadata["test"], "metadata")


if __name__ == "__main__":
    unittest.main()
