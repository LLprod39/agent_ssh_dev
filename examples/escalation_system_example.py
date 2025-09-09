#!/usr/bin/env python3
"""
Пример использования системы эскалации - Шаг 4.2

Этот пример демонстрирует:
- Отправку логов планировщику при превышении порога
- Механизм пересмотра планов
- Систему эскалации к человеку-оператору
"""
import sys
import os
import time
from datetime import datetime

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.agent_config import AgentConfig
from src.agents.error_handler import ErrorHandler
from src.agents.escalation_system import EscalationSystem, EscalationType, EscalationStatus
from src.agents.human_operator_system import HumanOperatorSystem, NotificationMethod
from src.agents.task_agent import TaskAgent
from src.agents.subtask_agent import SubtaskAgent
from src.models.planning_model import Task, TaskStep, StepStatus, Priority
from src.utils.logger import StructuredLogger


def create_test_task() -> Task:
    """Создание тестовой задачи"""
    task = Task(
        title="Установка PostgreSQL",
        description="Установка и настройка PostgreSQL на сервере"
    )
    
    # Добавляем шаги
    step1 = TaskStep(
        title="Обновление системы",
        description="Обновление пакетов системы",
        priority=Priority.HIGH,
        estimated_duration=10
    )
    
    step2 = TaskStep(
        title="Установка PostgreSQL",
        description="Установка PostgreSQL сервера",
        priority=Priority.HIGH,
        estimated_duration=15,
        dependencies=[step1.step_id]
    )
    
    step3 = TaskStep(
        title="Настройка PostgreSQL",
        description="Настройка конфигурации PostgreSQL",
        priority=Priority.MEDIUM,
        estimated_duration=20,
        dependencies=[step2.step_id]
    )
    
    task.add_step(step1)
    task.add_step(step2)
    task.add_step(step3)
    
    return task


def simulate_errors(error_handler: ErrorHandler, step_id: str, error_count: int):
    """Симуляция ошибок для тестирования эскалации"""
    logger = StructuredLogger("ErrorSimulator")
    
    logger.info(f"Симуляция {error_count} ошибок для шага {step_id}")
    
    for i in range(error_count):
        # Симулируем различные типы ошибок
        error_types = [
            "permission denied",
            "command not found",
            "connection refused",
            "syntax error",
            "file not found"
        ]
        
        error_type = error_types[i % len(error_types)]
        command = f"test_command_{i+1}"
        error_message = f"Error {i+1}: {error_type} - command failed"
        
        # Записываем ошибку
        error_handler.error_tracker.record_error(
            step_id=step_id,
            command=command,
            error_message=error_message,
            exit_code=1,
            autocorrection_applied=False
        )
        
        time.sleep(0.1)  # Небольшая задержка


def test_planner_notification():
    """Тест уведомления планировщика"""
    print("\n" + "="*60)
    print("ТЕСТ: Уведомление планировщика")
    print("="*60)
    
    # Создаем конфигурацию
    config_data = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "max_tokens": 4000,
            "temperature": 0.7,
            "timeout": 60
        },
        "error_handler": {
            "error_threshold_per_step": 3,
            "human_escalation_threshold": 5,
            "max_retention_days": 7,
            "escalation_cooldown_minutes": 5
        }
    }
    config = AgentConfig(**config_data)
    
    # Создаем компоненты
    error_handler = ErrorHandler(config)
    task_agent = TaskAgent(config)
    subtask_agent = SubtaskAgent(config)
    escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)
    
    # Устанавливаем систему эскалации
    error_handler.set_escalation_system(escalation_system)
    
    # Создаем тестовую задачу
    task = create_test_task()
    step_id = task.steps[0].step_id
    
    print(f"Тестируем шаг: {task.steps[0].title}")
    print(f"Порог для планировщика: {config.error_handler.error_threshold_per_step}")
    
    # Симулируем ошибки до порога планировщика
    simulate_errors(error_handler, step_id, config.error_handler.error_threshold_per_step)
    
    # Обрабатываем ошибку
    error_details = {
        "recent_errors": [
            {
                "command": "apt update",
                "error_message": "permission denied",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
    
    escalation_request = escalation_system.handle_escalation(step_id, task, config.error_handler.error_threshold_per_step, error_details)
    
    if escalation_request:
        print(f"✅ Эскалация создана: {escalation_request.escalation_id}")
        print(f"   Тип: {escalation_request.escalation_type.value}")
        print(f"   Статус: {escalation_request.status.value}")
        print(f"   Причина: {escalation_request.reason}")
    else:
        print("❌ Эскалация не создана")
    
    # Показываем статистику
    stats = escalation_system.get_escalation_stats()
    print(f"\nСтатистика эскалаций:")
    print(f"  Всего эскалаций: {stats['total_escalations']}")
    print(f"  Уведомления планировщику: {stats['planner_notifications']}")


def test_plan_revision():
    """Тест пересмотра плана"""
    print("\n" + "="*60)
    print("ТЕСТ: Пересмотр плана")
    print("="*60)
    
    # Создаем конфигурацию
    config_data = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "max_tokens": 4000,
            "temperature": 0.7,
            "timeout": 60
        },
        "error_handler": {
            "error_threshold_per_step": 3,
            "human_escalation_threshold": 5,
            "max_retention_days": 7,
            "escalation_cooldown_minutes": 5
        }
    }
    config = AgentConfig(**config_data)
    
    # Создаем компоненты
    error_handler = ErrorHandler(config)
    task_agent = TaskAgent(config)
    subtask_agent = SubtaskAgent(config)
    escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)
    
    # Устанавливаем систему эскалации
    error_handler.set_escalation_system(escalation_system)
    
    # Создаем тестовую задачу
    task = create_test_task()
    step_id = task.steps[1].step_id
    
    print(f"Тестируем шаг: {task.steps[1].title}")
    print(f"Порог для пересмотра плана: {config.error_handler.error_threshold_per_step + 1}")
    
    # Симулируем ошибки до порога пересмотра плана
    error_count = config.error_handler.error_threshold_per_step + 1
    simulate_errors(error_handler, step_id, error_count)
    
    # Обрабатываем ошибку
    error_details = {
        "recent_errors": [
            {
                "command": "apt install postgresql",
                "error_message": "package not found",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
    
    escalation_request = escalation_system.handle_escalation(step_id, task, error_count, error_details)
    
    if escalation_request:
        print(f"✅ Эскалация создана: {escalation_request.escalation_id}")
        print(f"   Тип: {escalation_request.escalation_type.value}")
        print(f"   Статус: {escalation_request.status.value}")
        print(f"   Причина: {escalation_request.reason}")
        
        # Проверяем запрос на пересмотр плана
        revision_requests = escalation_system.plan_revision_requests
        if revision_requests:
            revision_request = list(revision_requests.values())[0]
            print(f"\n📋 Запрос на пересмотр плана:")
            print(f"   ID: {revision_request.revision_id}")
            print(f"   Приоритет: {revision_request.priority}")
            print(f"   Предложенные изменения: {len(revision_request.suggested_changes)}")
            for i, change in enumerate(revision_request.suggested_changes[:3], 1):
                print(f"     {i}. {change}")
    else:
        print("❌ Эскалация не создана")
    
    # Показываем статистику
    stats = escalation_system.get_escalation_stats()
    print(f"\nСтатистика эскалаций:")
    print(f"  Всего эскалаций: {stats['total_escalations']}")
    print(f"  Пересмотры планов: {stats['plan_revisions']}")


def test_human_escalation():
    """Тест эскалации к человеку"""
    print("\n" + "="*60)
    print("ТЕСТ: Эскалация к человеку")
    print("="*60)
    
    # Создаем конфигурацию
    config_data = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "max_tokens": 4000,
            "temperature": 0.7,
            "timeout": 60
        },
        "error_handler": {
            "error_threshold_per_step": 3,
            "human_escalation_threshold": 5,
            "max_retention_days": 7,
            "escalation_cooldown_minutes": 5
        }
    }
    config = AgentConfig(**config_data)
    
    # Создаем компоненты
    error_handler = ErrorHandler(config)
    task_agent = TaskAgent(config)
    subtask_agent = SubtaskAgent(config)
    escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)
    
    # Создаем систему оператора
    operator_config = {
        "email_notifications": {
            "enabled": False  # Отключаем email для теста
        },
        "webhook_notifications": {
            "enabled": False  # Отключаем webhook для теста
        },
        "console_notifications": {
            "enabled": True  # Включаем консольные уведомления
        }
    }
    
    human_operator_system = HumanOperatorSystem(operator_config)
    
    # Регистрируем колбэк для эскалации к человеку
    def handle_human_escalation(escalation_request):
        print(f"🚨 ПОЛУЧЕНА ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ!")
        print(f"   ID: {escalation_request.escalation_id}")
        print(f"   Тип: {escalation_request.escalation_type.value}")
        print(f"   Причина: {escalation_request.reason}")
        
        # Обрабатываем эскалацию через систему оператора
        notification = human_operator_system.handle_escalation(escalation_request)
        print(f"   Уведомление создано: {notification.notification_id}")
        print(f"   Приоритет: {notification.priority}")
        print(f"   Методы уведомления: {[m.value for m in notification.notification_methods]}")
    
    escalation_system.register_human_escalation_callback(handle_human_escalation)
    
    # Устанавливаем систему эскалации
    error_handler.set_escalation_system(escalation_system)
    
    # Создаем тестовую задачу
    task = create_test_task()
    step_id = task.steps[2].step_id
    
    print(f"Тестируем шаг: {task.steps[2].title}")
    print(f"Порог для эскалации к человеку: {config.error_handler.human_escalation_threshold}")
    
    # Симулируем ошибки до порога эскалации к человеку
    error_count = config.error_handler.human_escalation_threshold
    simulate_errors(error_handler, step_id, error_count)
    
    # Обрабатываем ошибку
    error_details = {
        "recent_errors": [
            {
                "command": "systemctl start postgresql",
                "error_message": "service failed to start",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
    
    escalation_request = escalation_system.handle_escalation(step_id, task, error_count, error_details)
    
    if escalation_request:
        print(f"✅ Эскалация создана: {escalation_request.escalation_id}")
        print(f"   Тип: {escalation_request.escalation_type.value}")
        print(f"   Статус: {escalation_request.status.value}")
        print(f"   Причина: {escalation_request.reason}")
    else:
        print("❌ Эскалация не создана")
    
    # Показываем статистику
    stats = escalation_system.get_escalation_stats()
    print(f"\nСтатистика эскалаций:")
    print(f"  Всего эскалаций: {stats['total_escalations']}")
    print(f"  Эскалации к человеку: {stats['human_escalations']}")
    
    operator_stats = human_operator_system.get_operator_stats()
    print(f"\nСтатистика оператора:")
    print(f"  Всего уведомлений: {operator_stats['total_notifications']}")
    print(f"  Ожидающие уведомления: {operator_stats['pending_notifications']}")


def test_emergency_stop():
    """Тест экстренной остановки"""
    print("\n" + "="*60)
    print("ТЕСТ: Экстренная остановка")
    print("="*60)
    
    # Создаем конфигурацию
    config_data = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "max_tokens": 4000,
            "temperature": 0.7,
            "timeout": 60
        },
        "error_handler": {
            "error_threshold_per_step": 3,
            "human_escalation_threshold": 5,
            "max_retention_days": 7,
            "escalation_cooldown_minutes": 5
        }
    }
    config = AgentConfig(**config_data)
    
    # Создаем компоненты
    error_handler = ErrorHandler(config)
    task_agent = TaskAgent(config)
    subtask_agent = SubtaskAgent(config)
    escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)
    
    # Создаем систему оператора
    operator_config = {
        "console_notifications": {"enabled": True}
    }
    
    human_operator_system = HumanOperatorSystem(operator_config)
    
    # Регистрируем колбэк для экстренной остановки
    def handle_emergency_stop(escalation_request):
        print(f"🚨🚨🚨 ЭКСТРЕННАЯ ОСТАНОВКА! 🚨🚨🚨")
        print(f"   ID: {escalation_request.escalation_id}")
        print(f"   Тип: {escalation_request.escalation_type.value}")
        print(f"   Причина: {escalation_request.reason}")
        print(f"   КРИТИЧЕСКАЯ СИТУАЦИЯ - ТРЕБУЕТСЯ НЕМЕДЛЕННОЕ ВМЕШАТЕЛЬСТВО!")
        
        # Обрабатываем эскалацию через систему оператора
        notification = human_operator_system.handle_escalation(escalation_request)
        print(f"   Уведомление создано: {notification.notification_id}")
        print(f"   Приоритет: {notification.priority}")
    
    escalation_system.register_human_escalation_callback(handle_emergency_stop)
    
    # Устанавливаем систему эскалации
    error_handler.set_escalation_system(escalation_system)
    
    # Создаем тестовую задачу
    task = create_test_task()
    step_id = task.steps[0].step_id
    
    print(f"Тестируем шаг: {task.steps[0].title}")
    print(f"Порог для экстренной остановки: {config.error_handler.human_escalation_threshold + 2}")
    
    # Симулируем ошибки до порога экстренной остановки
    error_count = config.error_handler.human_escalation_threshold + 2
    simulate_errors(error_handler, step_id, error_count)
    
    # Обрабатываем ошибку
    error_details = {
        "recent_errors": [
            {
                "command": "rm -rf /",
                "error_message": "permission denied - critical system protection",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
    
    escalation_request = escalation_system.handle_escalation(step_id, task, error_count, error_details)
    
    if escalation_request:
        print(f"✅ Эскалация создана: {escalation_request.escalation_id}")
        print(f"   Тип: {escalation_request.escalation_type.value}")
        print(f"   Статус: {escalation_request.status.value}")
        print(f"   Причина: {escalation_request.reason}")
    else:
        print("❌ Эскалация не создана")
    
    # Показываем статистику
    stats = escalation_system.get_escalation_stats()
    print(f"\nСтатистика эскалаций:")
    print(f"  Всего эскалаций: {stats['total_escalations']}")
    print(f"  Экстренные остановки: {stats['emergency_stops']}")


def test_escalation_resolution():
    """Тест разрешения эскалации"""
    print("\n" + "="*60)
    print("ТЕСТ: Разрешение эскалации")
    print("="*60)
    
    # Создаем конфигурацию
    config_data = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "max_tokens": 4000,
            "temperature": 0.7,
            "timeout": 60
        },
        "error_handler": {
            "error_threshold_per_step": 3,
            "human_escalation_threshold": 5,
            "max_retention_days": 7,
            "escalation_cooldown_minutes": 5
        }
    }
    config = AgentConfig(**config_data)
    
    # Создаем компоненты
    error_handler = ErrorHandler(config)
    task_agent = TaskAgent(config)
    subtask_agent = SubtaskAgent(config)
    escalation_system = EscalationSystem(config, error_handler, task_agent, subtask_agent)
    
    # Устанавливаем систему эскалации
    error_handler.set_escalation_system(escalation_system)
    
    # Создаем тестовую задачу
    task = create_test_task()
    step_id = task.steps[0].step_id
    
    # Симулируем ошибки
    error_count = config.error_handler.error_threshold_per_step
    simulate_errors(error_handler, step_id, error_count)
    
    # Обрабатываем ошибку
    error_details = {
        "recent_errors": [
            {
                "command": "apt update",
                "error_message": "permission denied",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
    
    escalation_request = escalation_system.handle_escalation(step_id, task, error_count, error_details)
    
    if escalation_request:
        print(f"✅ Эскалация создана: {escalation_request.escalation_id}")
        print(f"   Статус: {escalation_request.status.value}")
        
        # Разрешаем эскалацию
        resolution = "Проблема решена: добавлены права sudo для пользователя"
        success = escalation_system.resolve_escalation(escalation_request.escalation_id, resolution)
        
        if success:
            print(f"✅ Эскалация разрешена")
            print(f"   Решение: {resolution}")
            
            # Проверяем статус
            status = escalation_system.get_escalation_status(escalation_request.escalation_id)
            if status:
                print(f"   Финальный статус: {status['status']}")
                print(f"   Время разрешения: {status['resolved_at']}")
        else:
            print("❌ Не удалось разрешить эскалацию")
    else:
        print("❌ Эскалация не создана")
    
    # Показываем статистику
    stats = escalation_system.get_escalation_stats()
    print(f"\nСтатистика эскалаций:")
    print(f"  Всего эскалаций: {stats['total_escalations']}")
    print(f"  Разрешенные эскалации: {stats['resolved_escalations']}")


def main():
    """Главная функция"""
    print("🚀 ДЕМОНСТРАЦИЯ СИСТЕМЫ ЭСКАЛАЦИИ - ШАГ 4.2")
    print("="*80)
    
    try:
        # Тест 1: Уведомление планировщика
        test_planner_notification()
        
        # Тест 2: Пересмотр плана
        test_plan_revision()
        
        # Тест 3: Эскалация к человеку
        test_human_escalation()
        
        # Тест 4: Экстренная остановка
        test_emergency_stop()
        
        # Тест 5: Разрешение эскалации
        test_escalation_resolution()
        
        print("\n" + "="*80)
        print("✅ ВСЕ ТЕСТЫ СИСТЕМЫ ЭСКАЛАЦИИ ЗАВЕРШЕНЫ УСПЕШНО!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
