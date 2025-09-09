#!/usr/bin/env python3
"""
Упрощенный пример использования системы подсчета ошибок

Этот пример демонстрирует основные возможности системы без циклических импортов.
"""

import sys
import os
import time
from datetime import datetime

# Добавляем путь к модулям проекта
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Импортируем только необходимые классы
from src.utils.error_tracker import ErrorTracker, EscalationLevel, ErrorSeverity


def simulate_command_execution(command: str, should_fail: bool = False):
    """Симуляция выполнения команды"""
    time.sleep(0.1)  # Имитация времени выполнения
    
    if should_fail:
        return {
            "command": command,
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Ошибка выполнения команды: {command}",
            "duration": 0.1,
            "error_message": f"Ошибка выполнения команды: {command}"
        }
    else:
        return {
            "command": command,
            "success": True,
            "exit_code": 0,
            "stdout": f"Команда '{command}' выполнена успешно",
            "stderr": "",
            "duration": 0.1,
            "error_message": None
        }


def main():
    """Основная функция примера"""
    print("=== Упрощенный пример системы подсчета ошибок ===\n")
    
    # Создаем систему подсчета ошибок
    error_tracker = ErrorTracker(
        error_threshold=3,  # Порог для эскалации к планировщику
        escalation_threshold=5,  # Порог для эскалации к человеку
        max_retention_days=7
    )
    
    print("1. Инициализация системы подсчета ошибок")
    print(f"   - Порог ошибок для планировщика: {error_tracker.error_threshold}")
    print(f"   - Порог ошибок для человека: {error_tracker.escalation_threshold}")
    print(f"   - Максимальное время хранения: {error_tracker.max_retention_days} дней\n")
    
    # Симулируем выполнение команд для разных шагов
    step_ids = ["step_1", "step_2", "step_3"]
    commands = [
        "sudo apt update",
        "sudo apt install nginx",
        "systemctl start nginx"
    ]
    
    print("2. Симуляция выполнения команд")
    
    # Шаг 1: Успешные команды
    print("\n--- Шаг 1: Успешные команды ---")
    for i, (step_id, command) in enumerate(zip(step_ids, commands)):
        print(f"Выполнение команды: {command}")
        
        result = simulate_command_execution(command, should_fail=False)
        
        # Записываем попытку выполнения
        attempt_id = error_tracker.record_attempt(
            step_id=step_id,
            command=command,
            success=result["success"],
            duration=result["duration"],
            exit_code=result["exit_code"],
            error_message=result["error_message"],
            autocorrection_used=False,
            metadata={"command_type": "main_command"}
        )
        
        print(f"  ✓ Успешно выполнено (попытка ID: {attempt_id})")
        
        # Получаем статистику шага
        stats = error_tracker.get_step_stats(step_id)
        if stats:
            print(f"  Статистика: {stats.successful_attempts}/{stats.total_attempts} успешных попыток")
    
    # Шаг 2: Неудачные команды для демонстрации эскалации
    print("\n--- Шаг 2: Неудачные команды (демонстрация эскалации) ---")
    
    # Симулируем несколько неудачных попыток для step_1
    failed_commands = [
        "sudo apt install nonexistent-package",
        "systemctl start nonexistent-service",
        "curl http://nonexistent-url.com"
    ]
    
    for i, command in enumerate(failed_commands):
        print(f"Выполнение команды: {command}")
        
        result = simulate_command_execution(command, should_fail=True)
        
        # Записываем неудачную попытку
        attempt_id = error_tracker.record_attempt(
            step_id="step_1",
            command=command,
            success=result["success"],
            duration=result["duration"],
            exit_code=result["exit_code"],
            error_message=result["error_message"],
            autocorrection_used=False,
            metadata={"command_type": "main_command"}
        )
        
        print(f"  ✗ Неудачно выполнено (попытка ID: {attempt_id})")
        
        # Проверяем уровень эскалации
        escalation_level = error_tracker.get_escalation_level("step_1")
        print(f"  Уровень эскалации: {escalation_level.value}")
        
        if escalation_level == EscalationLevel.PLANNER_NOTIFICATION:
            print("  ⚠️  ТРЕБУЕТСЯ ЭСКАЛАЦИЯ К ПЛАНИРОВЩИКУ!")
        elif escalation_level == EscalationLevel.HUMAN_ESCALATION:
            print("  🚨 ТРЕБУЕТСЯ ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ!")
    
    # Шаг 3: Демонстрация автокоррекции
    print("\n--- Шаг 3: Демонстрация автокоррекции ---")
    
    # Симулируем автокоррекцию
    original_command = "sudo apt install nginx"
    corrected_command = "sudo apt update && sudo apt install nginx"
    
    print(f"Оригинальная команда: {original_command}")
    print(f"Исправленная команда: {corrected_command}")
    
    # Записываем неудачную попытку оригинальной команды
    error_tracker.record_attempt(
        step_id="step_2",
        command=original_command,
        success=False,
        duration=0.1,
        exit_code=1,
        error_message="Package not found",
        autocorrection_used=False,
        metadata={"command_type": "main_command"}
    )
    
    # Записываем успешную попытку исправленной команды
    error_tracker.record_attempt(
        step_id="step_2",
        command=corrected_command,
        success=True,
        duration=0.2,
        exit_code=0,
        autocorrection_used=True,
        metadata={
            "command_type": "autocorrected_command",
            "original_command": original_command
        }
    )
    
    print("  ✓ Автокоррекция применена успешно")
    
    # Шаг 4: Анализ статистики
    print("\n--- Шаг 4: Анализ статистики ---")
    
    # Глобальная статистика
    global_stats = error_tracker.get_global_stats()
    print("Глобальная статистика:")
    print(f"  - Всего попыток: {global_stats['total_attempts']}")
    print(f"  - Всего ошибок: {global_stats['total_errors']}")
    print(f"  - Процент успеха: {global_stats['success_rate']:.1f}%")
    print(f"  - Эскалаций к планировщику: {global_stats['escalations_to_planner']}")
    print(f"  - Эскалаций к человеку: {global_stats['escalations_to_human']}")
    print(f"  - Автокоррекций применено: {global_stats['autocorrections_applied']}")
    print(f"  - Автокоррекций успешно: {global_stats['autocorrections_successful']}")
    print(f"  - Процент успеха автокоррекции: {global_stats['autocorrection_success_rate']:.1f}%")
    
    # Статистика по шагам
    print("\nСтатистика по шагам:")
    for step_id in step_ids:
        summary = error_tracker.get_error_summary(step_id)
        print(f"  {step_id}:")
        print(f"    - Попыток: {summary['attempt_count']}")
        print(f"    - Ошибок: {summary['error_count']}")
        print(f"    - Процент успеха: {summary['success_rate']:.1f}%")
        print(f"    - Уровень эскалации: {summary['escalation_level']}")
        
        if summary['error_patterns']:
            print(f"    - Паттерны ошибок: {summary['error_patterns']}")
    
    # Шаг 5: Демонстрация очистки старых записей
    print("\n--- Шаг 5: Очистка старых записей ---")
    
    print("Очистка старых записей...")
    error_tracker.cleanup_old_records()
    print("✓ Старые записи очищены")
    
    # Финальная статистика
    final_stats = error_tracker.get_global_stats()
    print(f"Записей после очистки: {final_stats['total_error_records']} ошибок, {final_stats['total_attempt_records']} попыток")
    
    print("\n=== Пример завершен ===")


if __name__ == "__main__":
    main()

