"""
Пример использования системы обратной связи с пользователем

Демонстрирует:
- Настройку системы обратной связи
- Интеграцию с выполнением задач
- Получение уведомлений и отчетов
- Экспорт временной шкалы
"""
import time
import json
from pathlib import Path
from datetime import datetime

# Добавляем путь к модулям
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.user_feedback_system import UserFeedbackSystem, FeedbackConfig
from src.models.planning_model import Task, TaskStep, TaskStatus, StepStatus, Priority
from src.utils.logger import setup_logging


def create_sample_task() -> Task:
    """Создание примерной задачи для демонстрации"""
    task = Task(
        task_id="demo_task_001",
        title="Установка и настройка веб-сервера",
        description="Установка Nginx, настройка SSL и создание базовой конфигурации",
        priority=Priority.HIGH
    )
    
    # Добавляем шаги
    steps = [
        TaskStep(
            step_id="step_001",
            title="Обновление системы",
            description="Обновление пакетов системы",
            priority=Priority.MEDIUM,
            estimated_duration=5
        ),
        TaskStep(
            step_id="step_002", 
            title="Установка Nginx",
            description="Установка веб-сервера Nginx",
            priority=Priority.HIGH,
            estimated_duration=10
        ),
        TaskStep(
            step_id="step_003",
            title="Настройка SSL",
            description="Настройка SSL сертификата",
            priority=Priority.HIGH,
            estimated_duration=15
        ),
        TaskStep(
            step_id="step_004",
            title="Создание конфигурации",
            description="Создание базовой конфигурации сайта",
            priority=Priority.MEDIUM,
            estimated_duration=10
        )
    ]
    
    for step in steps:
        task.add_step(step)
    
    return task


def simulate_task_execution(feedback_system: UserFeedbackSystem, task: Task):
    """Симуляция выполнения задачи с обратной связью"""
    print("🚀 Начинаем выполнение задачи...")
    
    # Начало задачи
    task.mark_started()
    feedback_system.on_task_started(task)
    
    execution_results = {
        "successful_commands": 0,
        "failed_commands": 0,
        "autocorrections_applied": 0
    }
    
    # Выполняем шаги
    for i, step in enumerate(task.steps):
        print(f"\n📋 Выполняем шаг {i+1}: {step.title}")
        
        # Начало шага
        step.mark_started()
        feedback_system.on_step_started(task, step)
        
        # Симулируем выполнение команд
        commands = [
            f"apt update",
            f"apt install nginx -y" if "nginx" in step.title.lower() else f"echo 'Выполняем {step.title}'",
            f"systemctl enable nginx" if "nginx" in step.title.lower() else f"echo 'Настройка завершена'"
        ]
        
        step_success = True
        for j, command in enumerate(commands):
            print(f"  🔧 Выполняем команду: {command}")
            
            # Симулируем выполнение команды
            success = j != 1 or "nginx" not in step.title.lower()  # Симулируем ошибку для второго шага
            duration = 2.5 + (j * 0.5)
            
            if success:
                execution_results["successful_commands"] += 1
                output = f"Команда выполнена успешно"
                error = ""
                exit_code = 0
            else:
                execution_results["failed_commands"] += 1
                output = ""
                error = f"Ошибка выполнения команды: {command}"
                exit_code = 1
                step_success = False
            
            # Логируем выполнение команды
            feedback_system.on_command_executed(
                task_id=task.task_id,
                step_id=step.step_id,
                command=command,
                success=success,
                duration=duration,
                output=output,
                error=error,
                exit_code=exit_code
            )
            
            time.sleep(0.5)  # Небольшая задержка для демонстрации
        
        # Симулируем автокоррекцию для провального шага
        if not step_success and "nginx" in step.title.lower():
            print("  🔧 Применяем автокоррекцию...")
            feedback_system.on_autocorrection_applied(
                task_id=task.task_id,
                step_id=step.step_id,
                original_command="apt install nginx -y",
                corrected_command="apt install nginx -y --fix-missing",
                correction_type="package_fix",
                success=True
            )
            execution_results["autocorrections_applied"] += 1
            step_success = True
        
        # Завершение шага
        if step_success:
            step.mark_completed()
            feedback_system.on_step_completed(task, step, step.get_duration() or 0)
            print(f"  ✅ Шаг завершен успешно")
        else:
            step.mark_failed()
            feedback_system.on_step_failed(
                task=task,
                step=step,
                error_message="Не удалось выполнить команду",
                retry_count=1,
                autocorrection_applied=False
            )
            print(f"  ❌ Шаг провален")
        
        # Обновляем прогресс
        completed_steps = len([s for s in task.steps if s.status == StepStatus.COMPLETED])
        feedback_system.on_task_progress(task, completed_steps, step)
        
        time.sleep(1)  # Пауза между шагами
    
    # Завершение задачи
    if task.is_completed():
        task.mark_completed()
        feedback_system.on_task_completed(task, execution_results)
        print("\n🎉 Задача выполнена успешно!")
    else:
        task.mark_failed()
        feedback_system.on_task_failed(task, "Некоторые шаги провалились", execution_results)
        print("\n💥 Задача провалена!")


def demonstrate_reports(feedback_system: UserFeedbackSystem, task: Task):
    """Демонстрация генерации отчетов"""
    print("\n📊 Генерируем отчеты...")
    
    # Генерируем сводный отчет
    execution_results = {
        "successful_commands": 8,
        "failed_commands": 1,
        "autocorrections_applied": 1
    }
    
    report = feedback_system.generate_task_report(task, execution_results)
    print(f"  📄 Создан отчет: {report.report_id}")
    
    # Экспортируем отчет
    exported_files = feedback_system.report_generator.export_report(report)
    print(f"  📁 Отчет экспортирован в файлы: {list(exported_files.keys())}")


def demonstrate_timeline(feedback_system: UserFeedbackSystem, task: Task):
    """Демонстрация временной шкалы"""
    print("\n⏰ Экспортируем временную шкалу...")
    
    # Экспортируем временную шкалу
    timeline_file = feedback_system.export_task_timeline(task.task_id, "json")
    print(f"  📈 Временная шкала экспортирована: {timeline_file}")
    
    # Получаем временную шкалу
    timeline = feedback_system.get_task_timeline(task.task_id)
    print(f"  📊 Событий в временной шкале: {len(timeline)}")


def demonstrate_notifications(feedback_system: UserFeedbackSystem):
    """Демонстрация уведомлений"""
    print("\n🔔 История уведомлений:")
    
    # Получаем историю уведомлений
    notifications = feedback_system.get_notification_history(hours=1)
    
    for notification in notifications[:5]:  # Показываем последние 5
        print(f"  📢 {notification['title']} ({notification['timestamp']})")


def main():
    """Главная функция демонстрации"""
    print("🎯 Демонстрация системы обратной связи с пользователем")
    print("=" * 60)
    
    # Настраиваем логирование
    setup_logging()
    
    # Создаем конфигурацию
    config = FeedbackConfig(
        notifications={
            "enabled": True,
            "console": {"enabled": True},
            "log": {"enabled": True},
            "email": {"enabled": False},
            "webhook": {"enabled": False},
            "file": {"enabled": True, "file_path": "demo_notifications.log"}
        },
        reports={
            "enabled": True,
            "output_dir": "demo_reports",
            "formats": ["json", "html", "markdown"],
            "include_timeline": True,
            "include_performance": True,
            "include_error_analysis": True
        },
        timeline={
            "enabled": True,
            "auto_create_segments": True,
            "max_events_per_task": 1000,
            "enable_performance_analysis": True,
            "export_dir": "demo_timeline"
        },
        enabled=True
    )
    
    # Инициализируем систему обратной связи
    feedback_system = UserFeedbackSystem(config)
    
    # Создаем примерную задачу
    task = create_sample_task()
    
    # Симулируем выполнение задачи
    simulate_task_execution(feedback_system, task)
    
    # Демонстрируем отчеты
    demonstrate_reports(feedback_system, task)
    
    # Демонстрируем временную шкалу
    demonstrate_timeline(feedback_system, task)
    
    # Демонстрируем уведомления
    demonstrate_notifications(feedback_system)
    
    # Показываем статус системы
    print("\n📈 Статус системы обратной связи:")
    status = feedback_system.get_system_status()
    print(f"  🔔 Уведомлений отправлено: {status['notifications']['notifications_sent']}")
    print(f"  📄 Отчетов создано: {status['reports']['total_reports']}")
    print(f"  ⏰ Событий в временной шкале: {status['timeline']['total_events']}")
    
    print("\n✅ Демонстрация завершена!")
    print("\n📁 Созданные файлы:")
    print("  - demo_notifications.log - файл уведомлений")
    print("  - demo_reports/ - директория с отчетами")
    print("  - demo_timeline/ - директория с временными шкалами")


if __name__ == "__main__":
    main()
