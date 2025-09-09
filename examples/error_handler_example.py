#!/usr/bin/env python3
"""
Пример использования Error Handler

Этот пример демонстрирует:
- Создание и настройку Error Handler
- Обработку ошибок шагов
- Генерацию отчетов для планировщика
- Сбор снимков состояния сервера
- Анализ паттернов ошибок
"""

import sys
import os
import time
from datetime import datetime, timedelta

# Добавляем путь к модулям проекта
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.agent_config import AgentConfig
from agents.error_handler import ErrorHandler, ErrorReportType, ServerSnapshotType
from models.planning_model import Task, TaskStep, StepStatus, Priority
from utils.error_tracker import ErrorRecord, ErrorSeverity
from connectors.ssh_connector import SSHConnector


def create_mock_task() -> Task:
    """Создание тестовой задачи"""
    task = Task(
        title="Установка и настройка PostgreSQL",
        description="Установить PostgreSQL и настроить базу данных"
    )
    
    # Добавляем шаги
    step1 = TaskStep(
        title="Обновление системы",
        description="Обновить пакеты системы",
        priority=Priority.HIGH
    )
    
    step2 = TaskStep(
        title="Установка PostgreSQL",
        description="Установить PostgreSQL сервер",
        priority=Priority.HIGH,
        dependencies=[step1.step_id]
    )
    
    step3 = TaskStep(
        title="Настройка PostgreSQL",
        description="Настроить конфигурацию PostgreSQL",
        priority=Priority.MEDIUM,
        dependencies=[step2.step_id]
    )
    
    task.add_step(step1)
    task.add_step(step2)
    task.add_step(step3)
    
    return task


def create_mock_ssh_connector() -> SSHConnector:
    """Создание мок SSH коннектора"""
    # В реальном использовании здесь был бы настоящий SSH коннектор
    return None


def simulate_errors(error_handler: ErrorHandler, task: Task):
    """Симуляция ошибок для демонстрации"""
    print("\n=== Симуляция ошибок ===")
    
    # Симулируем ошибки для первого шага
    step1 = task.steps[0]
    
    # Записываем несколько ошибок
    for i in range(3):
        error_handler.error_tracker.record_error(
            step_id=step1.step_id,
            command=f"apt update",
            error_message=f"Permission denied: unable to update package lists (attempt {i+1})",
            exit_code=1,
            metadata={"attempt": i+1}
        )
        time.sleep(0.1)
    
    print(f"Записано 3 ошибки для шага {step1.step_id}")
    
    # Симулируем ошибки для второго шага
    step2 = task.steps[1]
    
    for i in range(5):  # Превышаем порог
        error_handler.error_tracker.record_error(
            step_id=step2.step_id,
            command=f"apt install postgresql",
            error_message=f"Package 'postgresql' not found in repository (attempt {i+1})",
            exit_code=1,
            metadata={"attempt": i+1}
        )
        time.sleep(0.1)
    
    print(f"Записано 5 ошибок для шага {step2.step_id} (превышен порог)")


def demonstrate_error_handling():
    """Демонстрация обработки ошибок"""
    print("=== Демонстрация Error Handler ===\n")
    
    # Создаем конфигурацию
    try:
        config = AgentConfig.from_yaml("../config/agent_config.yaml")
        print("✓ Конфигурация загружена")
    except Exception as e:
        print(f"✗ Ошибка загрузки конфигурации: {e}")
        return
    
    # Создаем Error Handler
    ssh_connector = create_mock_ssh_connector()
    error_handler = ErrorHandler(config, ssh_connector)
    print("✓ Error Handler создан")
    
    # Создаем тестовую задачу
    task = create_mock_task()
    print(f"✓ Тестовая задача создана: {task.title}")
    
    # Регистрируем колбэки
    def planner_callback(report):
        print(f"\n📋 ОТЧЕТ ДЛЯ ПЛАНИРОВЩИКА:")
        print(f"   ID: {report.report_id}")
        print(f"   Заголовок: {report.title}")
        print(f"   Сводка: {report.summary}")
        print(f"   Рекомендации: {len(report.recommendations)}")
        for i, rec in enumerate(report.recommendations[:3], 1):
            print(f"     {i}. {rec}")
    
    def human_escalation_callback(report):
        print(f"\n🚨 КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ:")
        print(f"   ID: {report.report_id}")
        print(f"   Заголовок: {report.title}")
        print(f"   Сводка: {report.summary}")
        print(f"   Снимков сервера: {len(report.server_snapshots)}")
    
    error_handler.register_planner_callback(planner_callback)
    error_handler.register_human_escalation_callback(human_escalation_callback)
    print("✓ Колбэки зарегистрированы")
    
    # Симулируем ошибки
    simulate_errors(error_handler, task)
    
    # Обрабатываем ошибки шагов
    print("\n=== Обработка ошибок шагов ===")
    
    for step in task.steps:
        error_count = error_handler.error_tracker.get_step_error_count(step.step_id)
        if error_count > 0:
            print(f"\nОбработка ошибок для шага: {step.title}")
            print(f"Количество ошибок: {error_count}")
            
            # Обрабатываем ошибку шага
            error_details = {
                "step_title": step.title,
                "error_count": error_count,
                "timestamp": datetime.now().isoformat()
            }
            
            report = error_handler.handle_step_error(step.step_id, task, error_details)
            if report:
                print(f"✓ Создан отчет: {report.report_id}")
            else:
                print("  Порог эскалации не достигнут")
    
    # Демонстрируем сбор снимков сервера
    print("\n=== Сбор снимков сервера ===")
    
    snapshot_types = [
        ServerSnapshotType.SYSTEM_INFO,
        ServerSnapshotType.SERVICE_STATUS,
        ServerSnapshotType.DISK_USAGE
    ]
    
    for snapshot_type in snapshot_types:
        snapshot = error_handler.take_server_snapshot(snapshot_type)
        print(f"✓ Снимок {snapshot_type.value}: {snapshot.snapshot_id}")
        print(f"  Данные: {len(str(snapshot.data))} символов")
    
    # Анализируем паттерны ошибок
    print("\n=== Анализ паттернов ошибок ===")
    
    patterns = error_handler.analyze_error_patterns(time_window_hours=1)
    print(f"Найдено паттернов: {len(patterns)}")
    
    for pattern in patterns:
        print(f"\nПаттерн: {pattern.pattern_name}")
        print(f"  Частота: {pattern.frequency}")
        print(f"  Затронутые шаги: {len(pattern.affected_steps)}")
        print(f"  Решения: {len(pattern.suggested_solutions)}")
        for solution in pattern.suggested_solutions[:2]:
            print(f"    - {solution}")
    
    # Генерируем итоговый отчет по задаче
    print("\n=== Итоговый отчет по задаче ===")
    
    execution_results = {
        "total_duration": 300.5,
        "steps_completed": 1,
        "steps_failed": 2,
        "total_commands": 15,
        "successful_commands": 5,
        "failed_commands": 10
    }
    
    final_report = error_handler.handle_task_completion(task, execution_results)
    print(f"✓ Итоговый отчет создан: {final_report.report_id}")
    print(f"  Тип: {final_report.report_type.value}")
    print(f"  Заголовок: {final_report.title}")
    print(f"  Рекомендации: {len(final_report.recommendations)}")
    print(f"  Снимков сервера: {len(final_report.server_snapshots)}")
    
    # Показываем статистику
    print("\n=== Статистика Error Handler ===")
    
    stats = error_handler.get_handler_stats()
    print(f"Отчетов создано: {stats['reports_generated']}")
    print(f"Снимков сделано: {stats['snapshots_taken']}")
    print(f"Паттернов найдено: {stats['patterns_identified']}")
    print(f"Эскалаций отправлено: {stats['escalations_sent']}")
    print(f"Рекомендаций сгенерировано: {stats['recommendations_generated']}")
    
    # Показываем сводку по ошибкам
    print("\n=== Сводка по ошибкам ===")
    
    error_summary = error_handler.get_error_summary()
    print(f"Всего ошибок: {error_summary['total_errors']}")
    print(f"Всего попыток: {error_summary['total_attempts']}")
    print(f"Процент успеха: {error_summary['success_rate']:.1f}%")
    print(f"Отслеживаемых шагов: {error_summary['steps_tracked']}")
    
    # Показываем недавние отчеты
    print("\n=== Недавние отчеты ===")
    
    recent_reports = error_handler.get_recent_reports(hours=1)
    print(f"Отчетов за последний час: {len(recent_reports)}")
    
    for report in recent_reports:
        print(f"  - {report.report_id}: {report.title}")
    
    print("\n=== Демонстрация завершена ===")


def demonstrate_server_snapshots():
    """Демонстрация сбора снимков сервера"""
    print("\n=== Демонстрация снимков сервера ===")
    
    try:
        config = AgentConfig.from_yaml("../config/agent_config.yaml")
        error_handler = ErrorHandler(config, None)  # Без SSH коннектора
        
        # Создаем различные типы снимков
        snapshot_types = [
            ServerSnapshotType.SYSTEM_INFO,
            ServerSnapshotType.PROCESS_LIST,
            ServerSnapshotType.DISK_USAGE,
            ServerSnapshotType.MEMORY_USAGE,
            ServerSnapshotType.NETWORK_STATUS,
            ServerSnapshotType.SERVICE_STATUS,
            ServerSnapshotType.LOG_ANALYSIS
        ]
        
        for snapshot_type in snapshot_types:
            print(f"\nСоздание снимка: {snapshot_type.value}")
            snapshot = error_handler.take_server_snapshot(snapshot_type)
            print(f"✓ Снимок создан: {snapshot.snapshot_id}")
            print(f"  Тип: {snapshot.snapshot_type.value}")
            print(f"  Время: {snapshot.timestamp}")
            print(f"  Размер данных: {len(str(snapshot.data))} символов")
            
            # Показываем пример данных
            if snapshot.data and "error" not in snapshot.data:
                first_key = list(snapshot.data.keys())[0]
                print(f"  Пример данных ({first_key}): {str(snapshot.data[first_key])[:100]}...")
            else:
                print(f"  Данные: {snapshot.data}")
        
        print(f"\n✓ Всего снимков создано: {len(error_handler.server_snapshots)}")
        
    except Exception as e:
        print(f"✗ Ошибка демонстрации снимков: {e}")


def demonstrate_error_patterns():
    """Демонстрация анализа паттернов ошибок"""
    print("\n=== Демонстрация анализа паттернов ===")
    
    try:
        config = AgentConfig.from_yaml("../config/agent_config.yaml")
        error_handler = ErrorHandler(config, None)
        
        # Создаем различные типы ошибок для анализа
        error_scenarios = [
            {
                "step_id": "step_1",
                "command": "apt update",
                "error_message": "Permission denied: unable to update package lists",
                "count": 3
            },
            {
                "step_id": "step_2", 
                "command": "apt install postgresql",
                "error_message": "Package 'postgresql' not found in repository",
                "count": 4
            },
            {
                "step_id": "step_3",
                "command": "systemctl start postgresql",
                "error_message": "Failed to start postgresql.service: Unit not found",
                "count": 2
            },
            {
                "step_id": "step_4",
                "command": "sudo apt update",
                "error_message": "Permission denied: unable to update package lists",
                "count": 2
            }
        ]
        
        # Записываем ошибки
        for scenario in error_scenarios:
            for i in range(scenario["count"]):
                error_handler.error_tracker.record_error(
                    step_id=scenario["step_id"],
                    command=scenario["command"],
                    error_message=scenario["error_message"],
                    exit_code=1,
                    metadata={"scenario": scenario["step_id"], "attempt": i+1}
                )
        
        print(f"Записано ошибок: {sum(s['count'] for s in error_scenarios)}")
        
        # Анализируем паттерны
        patterns = error_handler.analyze_error_patterns(time_window_hours=1)
        print(f"\nНайдено паттернов: {len(patterns)}")
        
        for i, pattern in enumerate(patterns, 1):
            print(f"\nПаттерн {i}: {pattern.pattern_name}")
            print(f"  Описание: {pattern.description}")
            print(f"  Частота: {pattern.frequency}")
            print(f"  Серьезность: {pattern.severity}")
            print(f"  Затронутые шаги: {pattern.affected_steps}")
            print(f"  Общие команды: {pattern.common_commands}")
            print(f"  Решения ({len(pattern.suggested_solutions)}):")
            for solution in pattern.suggested_solutions:
                print(f"    - {solution}")
        
        # Показываем статистику по паттернам
        print(f"\nСтатистика паттернов:")
        print(f"  Всего паттернов: {len(error_handler.error_patterns)}")
        print(f"  Паттернов за час: {len(patterns)}")
        
    except Exception as e:
        print(f"✗ Ошибка демонстрации паттернов: {e}")


if __name__ == "__main__":
    print("🚀 Запуск демонстрации Error Handler")
    print("=" * 50)
    
    try:
        # Основная демонстрация
        demonstrate_error_handling()
        
        # Дополнительные демонстрации
        demonstrate_server_snapshots()
        demonstrate_error_patterns()
        
        print("\n✅ Все демонстрации завершены успешно!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Демонстрация прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка демонстрации: {e}")
        import traceback
        traceback.print_exc()
