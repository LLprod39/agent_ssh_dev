#!/usr/bin/env python3
"""
Тесты для Error Handler
"""

import unittest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import sys
import os

# Добавляем корневую директорию проекта в путь
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Прямые импорты для избежания проблем с относительными импортами
from src.agents.error_handler import (
    ErrorHandler, ErrorReportType, ServerSnapshotType, 
    ErrorReport, ServerSnapshot, ErrorPattern
)
from src.config.agent_config import AgentConfig, ErrorHandlerConfig, LLMConfig
from src.models.planning_model import Task, TaskStep, StepStatus, Priority
from src.utils.error_tracker import ErrorRecord, ErrorSeverity, EscalationLevel


class TestErrorHandler(unittest.TestCase):
    """Тесты для Error Handler"""
    
    def setUp(self):
        """Настройка тестов"""
        # Создаем мок конфигурацию
        self.config = AgentConfig(
            error_handler=ErrorHandlerConfig(
                error_threshold_per_step=3,
                human_escalation_threshold=5,  # Увеличиваем порог для эскалации к человеку
                max_error_reports=5,
                enable_error_tracking=True,
                max_retention_days=7
            ),
            llm=LLMConfig(api_key="test-key")
        )
        
        # Создаем Error Handler
        self.error_handler = ErrorHandler(self.config, None)
        
        # Создаем тестовую задачу
        self.task = Task(
            title="Тестовая задача",
            description="Описание тестовой задачи"
        )
        
        self.step = TaskStep(
            title="Тестовый шаг",
            description="Описание тестового шага"
        )
        self.task.add_step(self.step)
    
    def test_error_handler_initialization(self):
        """Тест инициализации Error Handler"""
        self.assertIsNotNone(self.error_handler.error_tracker)
        self.assertEqual(self.error_handler.error_handler_config.error_threshold_per_step, 3)
        self.assertEqual(self.error_handler.error_handler_config.human_escalation_threshold, 5)
        self.assertEqual(len(self.error_handler.error_reports), 0)
        self.assertEqual(len(self.error_handler.server_snapshots), 0)
    
    def test_register_callbacks(self):
        """Тест регистрации колбэков"""
        planner_callback = Mock()
        human_callback = Mock()
        
        self.error_handler.register_planner_callback(planner_callback)
        self.error_handler.register_human_escalation_callback(human_callback)
        
        self.assertEqual(len(self.error_handler.planner_callbacks), 1)
        self.assertEqual(len(self.error_handler.human_escalation_callbacks), 1)
    
    def test_handle_step_error_no_escalation(self):
        """Тест обработки ошибки шага без эскалации"""
        # Записываем одну ошибку (ниже порога)
        self.error_handler.error_tracker.record_error(
            step_id=self.step.step_id,
            command="test command",
            error_message="test error",
            exit_code=1
        )
        
        error_details = {"test": "data"}
        report = self.error_handler.handle_step_error(
            self.step.step_id, 
            self.task, 
            error_details
        )
        
        # Не должно быть отчета, так как порог не достигнут
        self.assertIsNone(report)
    
    def test_handle_step_error_planner_escalation(self):
        """Тест эскалации к планировщику"""
        # Записываем ошибки до достижения порога планировщика
        for i in range(3):
            self.error_handler.error_tracker.record_error(
                step_id=self.step.step_id,
                command=f"test command {i}",
                error_message=f"test error {i}",
                exit_code=1
            )
        
        error_details = {"test": "data"}
        report = self.error_handler.handle_step_error(
            self.step.step_id, 
            self.task, 
            error_details
        )
        
        # Должен быть создан отчет для планировщика
        self.assertIsNotNone(report)
        self.assertEqual(report.report_type, ErrorReportType.ESCALATION_REPORT)
        self.assertIn("планировщику", report.title)
        self.assertIn(self.step.step_id, report.details["step_id"])
    
    def test_handle_step_error_human_escalation(self):
        """Тест эскалации к человеку"""
        # Записываем ошибки до достижения порога эскалации к человеку (5 ошибок)
        for i in range(5):
            self.error_handler.error_tracker.record_error(
                step_id=self.step.step_id,
                command=f"test command {i}",
                error_message=f"test error {i}",
                exit_code=1
            )
        
        error_details = {"test": "data"}
        report = self.error_handler.handle_step_error(
            self.step.step_id, 
            self.task, 
            error_details
        )
        
        # Должен быть создан отчет для эскалации к человеку
        self.assertIsNotNone(report)
        self.assertEqual(report.report_type, ErrorReportType.ESCALATION_REPORT)
        self.assertIn("КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ", report.title)
        self.assertIn(self.step.step_id, report.details["step_id"])
    
    def test_take_server_snapshot(self):
        """Тест создания снимка сервера"""
        snapshot = self.error_handler.take_server_snapshot(
            ServerSnapshotType.SYSTEM_INFO
        )
        
        self.assertIsInstance(snapshot, ServerSnapshot)
        self.assertEqual(snapshot.snapshot_type, ServerSnapshotType.SYSTEM_INFO)
        self.assertIsNotNone(snapshot.snapshot_id)
        self.assertIsNotNone(snapshot.timestamp)
        self.assertIn("error", snapshot.data)  # SSH недоступен, должна быть ошибка
    
    def test_analyze_error_patterns(self):
        """Тест анализа паттернов ошибок"""
        # Создаем несколько ошибок одного типа
        for i in range(3):
            self.error_handler.error_tracker.record_error(
                step_id=self.step.step_id,
                command="apt update",
                error_message="Permission denied: unable to update package lists",
                exit_code=1
            )
        
        # Создаем ошибки другого типа
        for i in range(2):
            self.error_handler.error_tracker.record_error(
                step_id=self.step.step_id,
                command="systemctl start service",
                error_message="Failed to start service: Unit not found",
                exit_code=1
            )
        
        patterns = self.error_handler.analyze_error_patterns(time_window_hours=1)
        
        # Должны быть найдены паттерны
        self.assertGreater(len(patterns), 0)
        
        for pattern in patterns:
            self.assertIsInstance(pattern, ErrorPattern)
            self.assertGreater(pattern.frequency, 1)
            self.assertIn(self.step.step_id, pattern.affected_steps)
    
    def test_generate_recommendations(self):
        """Тест генерации рекомендаций"""
        # Создаем ошибки разных типов
        error_records = [
            ErrorRecord(
                error_id="error1",
                step_id=self.step.step_id,
                command="apt update",
                error_message="Permission denied: unable to update package lists",
                severity=ErrorSeverity.HIGH,
                timestamp=datetime.now()
            ),
            ErrorRecord(
                error_id="error2",
                step_id=self.step.step_id,
                command="systemctl start service",
                error_message="Failed to start service: Unit not found",
                severity=ErrorSeverity.MEDIUM,
                timestamp=datetime.now()
            )
        ]
        
        recommendations = self.error_handler.generate_recommendations(
            self.step.step_id, 
            error_records
        )
        
        self.assertGreater(len(recommendations), 0)
        
        # Проверяем, что рекомендации содержат полезную информацию
        recommendations_text = " ".join(recommendations).lower()
        self.assertTrue(
            any(keyword in recommendations_text for keyword in [
                "права", "доступ", "sudo", "проверить", "установить"
            ])
        )
    
    def test_handle_task_completion(self):
        """Тест обработки завершения задачи"""
        # Добавляем ошибки в задачу
        self.error_handler.error_tracker.record_error(
            step_id=self.step.step_id,
            command="test command",
            error_message="test error",
            exit_code=1
        )
        
        execution_results = {
            "total_duration": 100.5,
            "steps_completed": 1,
            "steps_failed": 0,
            "total_commands": 5,
            "successful_commands": 4,
            "failed_commands": 1
        }
        
        report = self.error_handler.handle_task_completion(
            self.task, 
            execution_results
        )
        
        self.assertIsInstance(report, ErrorReport)
        self.assertEqual(report.report_type, ErrorReportType.TASK_SUMMARY)
        self.assertIn(self.task.task_id, report.details["task_id"])
        self.assertIn("execution_results", report.details)
    
    def test_get_error_summary(self):
        """Тест получения сводки по ошибкам"""
        # Добавляем ошибки
        self.error_handler.error_tracker.record_error(
            step_id=self.step.step_id,
            command="test command",
            error_message="test error",
            exit_code=1
        )
        
        # Общая сводка
        summary = self.error_handler.get_error_summary()
        self.assertIn("total_errors", summary)
        self.assertIn("total_attempts", summary)
        self.assertIn("success_rate", summary)
        
        # Сводка по шагу
        step_summary = self.error_handler.get_error_summary(self.step.step_id)
        self.assertIn("step_id", step_summary)
        self.assertIn("error_count", step_summary)
        self.assertIn("attempt_count", step_summary)
    
    def test_get_recent_reports(self):
        """Тест получения недавних отчетов"""
        # Создаем отчет
        report = self.error_handler.handle_task_completion(
            self.task, 
            {"test": "data"}
        )
        
        # Получаем недавние отчеты
        recent_reports = self.error_handler.get_recent_reports(hours=1)
        
        self.assertGreater(len(recent_reports), 0)
        self.assertIn(report, recent_reports)
    
    def test_cleanup_old_data(self):
        """Тест очистки старых данных"""
        # Создаем старый отчет
        old_report = ErrorReport(
            report_id="old_report",
            report_type=ErrorReportType.TASK_SUMMARY,
            timestamp=datetime.now() - timedelta(days=10),
            title="Старый отчет",
            summary="Старая сводка",
            details={}
        )
        self.error_handler.error_reports["old_report"] = old_report
        
        # Создаем старый снимок
        old_snapshot = ServerSnapshot(
            snapshot_id="old_snapshot",
            snapshot_type=ServerSnapshotType.SYSTEM_INFO,
            timestamp=datetime.now() - timedelta(days=10),
            data={}
        )
        self.error_handler.server_snapshots["old_snapshot"] = old_snapshot
        
        # Очищаем старые данные
        self.error_handler.cleanup_old_data(days=7)
        
        # Старые данные должны быть удалены
        self.assertNotIn("old_report", self.error_handler.error_reports)
        self.assertNotIn("old_snapshot", self.error_handler.server_snapshots)
    
    def test_get_handler_stats(self):
        """Тест получения статистики обработчика"""
        stats = self.error_handler.get_handler_stats()
        
        self.assertIn("reports_generated", stats)
        self.assertIn("snapshots_taken", stats)
        self.assertIn("patterns_identified", stats)
        self.assertIn("escalations_sent", stats)
        self.assertIn("error_tracker_stats", stats)
        self.assertIn("reports_count", stats)
        self.assertIn("snapshots_count", stats)
        self.assertIn("patterns_count", stats)
    
    def test_callback_execution(self):
        """Тест выполнения колбэков"""
        planner_callback = Mock()
        human_callback = Mock()
        
        self.error_handler.register_planner_callback(planner_callback)
        self.error_handler.register_human_escalation_callback(human_callback)
        
        # Создаем ошибки для эскалации к планировщику (3 ошибки)
        for i in range(3):
            self.error_handler.error_tracker.record_error(
                step_id=self.step.step_id,
                command=f"test command {i}",
                error_message=f"test error {i}",
                exit_code=1
            )
        
        error_details = {"test": "data"}
        report = self.error_handler.handle_step_error(
            self.step.step_id, 
            self.task, 
            error_details
        )
        
        # Должен быть создан отчет (3 ошибки >= 3 порог планировщика)
        self.assertIsNotNone(report)
        
        # Колбэк планировщика должен быть вызван
        planner_callback.assert_called_once()
        human_callback.assert_not_called()
        
        # Проверяем аргументы колбэка
        call_args = planner_callback.call_args[0][0]
        self.assertIsInstance(call_args, ErrorReport)
        self.assertEqual(call_args.report_id, report.report_id)


class TestErrorReport(unittest.TestCase):
    """Тесты для ErrorReport"""
    
    def test_error_report_creation(self):
        """Тест создания отчета об ошибке"""
        report = ErrorReport(
            report_id="test_report",
            report_type=ErrorReportType.TASK_SUMMARY,
            timestamp=datetime.now(),
            title="Тестовый отчет",
            summary="Тестовая сводка",
            details={"test": "data"}
        )
        
        self.assertEqual(report.report_id, "test_report")
        self.assertEqual(report.report_type, ErrorReportType.TASK_SUMMARY)
        self.assertEqual(report.title, "Тестовый отчет")
        self.assertEqual(report.summary, "Тестовая сводка")
        self.assertEqual(report.details["test"], "data")
    
    def test_error_report_to_dict(self):
        """Тест преобразования отчета в словарь"""
        report = ErrorReport(
            report_id="test_report",
            report_type=ErrorReportType.TASK_SUMMARY,
            timestamp=datetime.now(),
            title="Тестовый отчет",
            summary="Тестовая сводка",
            details={"test": "data"},
            recommendations=["Рекомендация 1", "Рекомендация 2"]
        )
        
        report_dict = report.to_dict()
        
        self.assertEqual(report_dict["report_id"], "test_report")
        self.assertEqual(report_dict["report_type"], "task_summary")
        self.assertEqual(report_dict["title"], "Тестовый отчет")
        self.assertEqual(report_dict["summary"], "Тестовая сводка")
        self.assertEqual(report_dict["details"]["test"], "data")
        self.assertEqual(len(report_dict["recommendations"]), 2)


class TestServerSnapshot(unittest.TestCase):
    """Тесты для ServerSnapshot"""
    
    def test_server_snapshot_creation(self):
        """Тест создания снимка сервера"""
        snapshot = ServerSnapshot(
            snapshot_id="test_snapshot",
            snapshot_type=ServerSnapshotType.SYSTEM_INFO,
            timestamp=datetime.now(),
            data={"hostname": "test-server", "os": "ubuntu"}
        )
        
        self.assertEqual(snapshot.snapshot_id, "test_snapshot")
        self.assertEqual(snapshot.snapshot_type, ServerSnapshotType.SYSTEM_INFO)
        self.assertEqual(snapshot.data["hostname"], "test-server")
        self.assertEqual(snapshot.data["os"], "ubuntu")
    
    def test_server_snapshot_to_dict(self):
        """Тест преобразования снимка в словарь"""
        snapshot = ServerSnapshot(
            snapshot_id="test_snapshot",
            snapshot_type=ServerSnapshotType.SYSTEM_INFO,
            timestamp=datetime.now(),
            data={"hostname": "test-server"}
        )
        
        snapshot_dict = snapshot.to_dict()
        
        self.assertEqual(snapshot_dict["snapshot_id"], "test_snapshot")
        self.assertEqual(snapshot_dict["snapshot_type"], "system_info")
        self.assertEqual(snapshot_dict["data"]["hostname"], "test-server")


class TestErrorPattern(unittest.TestCase):
    """Тесты для ErrorPattern"""
    
    def test_error_pattern_creation(self):
        """Тест создания паттерна ошибок"""
        pattern = ErrorPattern(
            pattern_id="test_pattern",
            pattern_name="Тестовый паттерн",
            description="Описание тестового паттерна",
            frequency=5,
            affected_steps=["step1", "step2"],
            common_commands=["apt update", "apt install"],
            common_error_messages=["Permission denied"],
            suggested_solutions=["Использовать sudo"],
            severity="high",
            first_seen=datetime.now(),
            last_seen=datetime.now()
        )
        
        self.assertEqual(pattern.pattern_id, "test_pattern")
        self.assertEqual(pattern.pattern_name, "Тестовый паттерн")
        self.assertEqual(pattern.frequency, 5)
        self.assertEqual(len(pattern.affected_steps), 2)
        self.assertEqual(len(pattern.common_commands), 2)
        self.assertEqual(len(pattern.suggested_solutions), 1)
        self.assertEqual(pattern.severity, "high")
    
    def test_error_pattern_to_dict(self):
        """Тест преобразования паттерна в словарь"""
        pattern = ErrorPattern(
            pattern_id="test_pattern",
            pattern_name="Тестовый паттерн",
            description="Описание тестового паттерна",
            frequency=5,
            affected_steps=["step1"],
            common_commands=["apt update"],
            common_error_messages=["Permission denied"],
            suggested_solutions=["Использовать sudo"],
            severity="high",
            first_seen=datetime.now(),
            last_seen=datetime.now()
        )
        
        pattern_dict = pattern.to_dict()
        
        self.assertEqual(pattern_dict["pattern_id"], "test_pattern")
        self.assertEqual(pattern_dict["pattern_name"], "Тестовый паттерн")
        self.assertEqual(pattern_dict["frequency"], 5)
        self.assertEqual(len(pattern_dict["affected_steps"]), 1)
        self.assertEqual(len(pattern_dict["common_commands"]), 1)
        self.assertEqual(len(pattern_dict["suggested_solutions"]), 1)
        self.assertEqual(pattern_dict["severity"], "high")


if __name__ == "__main__":
    unittest.main()
