"""
Пример использования Subtask Agent для планирования подзадач
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.subtask_agent import SubtaskAgent, SubtaskPlanningContext
from src.agents.task_master_integration import TaskMasterIntegration
from src.config.agent_config import AgentConfig
from src.models.planning_model import TaskStep, Priority
from src.utils.command_generator import LinuxCommandGenerator
from src.utils.health_checker import HealthChecker


def main():
    """Основная функция примера"""
    print("=== Пример использования Subtask Agent ===\n")
    
    try:
        # Загружаем конфигурацию
        config_path = project_root / "examples" / "test_config.yaml"
        if not config_path.exists():
            print(f"Файл конфигурации не найден: {config_path}")
            print("Создайте файл конфигурации или используйте пример")
            return
        
        config = AgentConfig.from_yaml(str(config_path))
        print("✓ Конфигурация загружена")
        
        # Создаем Task Master интеграцию
        task_master = TaskMasterIntegration(config.taskmaster, project_root)
        print("✓ Task Master интеграция создана")
        
        # Создаем Subtask Agent
        subtask_agent = SubtaskAgent(config, task_master)
        print("✓ Subtask Agent создан")
        
        # Создаем пример основного шага
        main_step = TaskStep(
            title="Установка и настройка Nginx",
            description="Установить веб-сервер Nginx, настроить его и убедиться что он работает корректно",
            priority=Priority.HIGH,
            estimated_duration=15
        )
        
        print(f"\nОсновной шаг: {main_step.title}")
        print(f"Описание: {main_step.description}")
        
        # Создаем контекст планирования
        context = SubtaskPlanningContext(
            step=main_step,
            server_info={
                "os": "linux",
                "arch": "x86_64",
                "distribution": "ubuntu",
                "version": "20.04"
            },
            os_type="ubuntu",
            installed_services=["ssh", "systemd"],
            available_tools=["apt", "systemctl", "curl", "wget", "netstat"],
            constraints=[
                "Не использовать опасные команды",
                "Все команды должны быть идемпотентными",
                "Добавить проверки работоспособности"
            ],
            previous_subtasks=[],
            environment={
                "user": "ubuntu",
                "home": "/home/ubuntu"
            }
        )
        
        print("\nКонтекст планирования:")
        print(f"- ОС: {context.os_type}")
        print(f"- Установленные сервисы: {', '.join(context.installed_services)}")
        print(f"- Доступные инструменты: {', '.join(context.available_tools)}")
        print(f"- Ограничения: {len(context.constraints)}")
        
        # Планируем подзадачи
        print("\n--- Планирование подзадач ---")
        planning_result = subtask_agent.plan_subtasks(main_step, context)
        
        if planning_result.success:
            print(f"✓ Планирование завершено успешно за {planning_result.planning_duration:.2f}s")
            print(f"✓ Создано {len(planning_result.subtasks)} подзадач")
            
            # Показываем детали подзадач
            print("\n--- Детали подзадач ---")
            for i, subtask in enumerate(planning_result.subtasks, 1):
                print(f"\n{i}. {subtask.title}")
                print(f"   Описание: {subtask.description}")
                print(f"   Команды ({len(subtask.commands)}):")
                for j, cmd in enumerate(subtask.commands, 1):
                    print(f"     {j}) {cmd}")
                
                print(f"   Health-check ({len(subtask.health_checks)}):")
                for j, check in enumerate(subtask.health_checks, 1):
                    print(f"     {j}) {check}")
                
                if subtask.rollback_commands:
                    print(f"   Rollback ({len(subtask.rollback_commands)}):")
                    for j, rollback in enumerate(subtask.rollback_commands, 1):
                        print(f"     {j}) {rollback}")
                
                if subtask.dependencies:
                    print(f"   Зависимости: {', '.join(subtask.dependencies)}")
                
                print(f"   Таймаут: {subtask.timeout}s")
            
            # Показываем метаданные
            print(f"\n--- Метаданные ---")
            print(f"Task Master использован: {planning_result.metadata.get('task_master_used', False)}")
            print(f"Валидация: {planning_result.metadata.get('validation_result', {}).get('valid', 'неизвестно')}")
            
            if planning_result.llm_usage:
                print(f"Использование LLM: {planning_result.llm_usage}")
            
        else:
            print(f"✗ Ошибка планирования: {planning_result.error_message}")
            return
        
        # Демонстрируем генератор команд
        print("\n--- Демонстрация генератора команд ---")
        command_generator = LinuxCommandGenerator()
        
        # Генерируем команды для установки Nginx
        nginx_commands = command_generator.generate_nginx_setup_commands()
        print("Команды для установки Nginx:")
        for i, cmd in enumerate(nginx_commands, 1):
            print(f"  {i}) {cmd}")
        
        # Демонстрируем health-check систему
        print("\n--- Демонстрация health-check системы ---")
        health_checker = HealthChecker()
        
        # Проверяем доступные шаблоны команд
        templates = command_generator.get_available_templates("ubuntu")
        print("Доступные шаблоны команд:")
        for category, template_names in templates.items():
            print(f"  {category}: {', '.join(template_names)}")
        
        # Проверяем безопасность команд
        test_commands = [
            "sudo apt update",
            "rm -rf /",
            "systemctl start nginx",
            "dd if=/dev/zero of=/dev/sda"
        ]
        
        print("\nПроверка безопасности команд:")
        for cmd in test_commands:
            safety = command_generator.validate_command_safety(cmd)
            status = "✓ Безопасно" if safety["is_safe"] else "✗ Опасно"
            print(f"  {status}: {cmd}")
            if safety["dangerous_patterns"]:
                print(f"    Опасные паттерны: {', '.join(safety['dangerous_patterns'])}")
        
        # Показываем статус подзадач
        print("\n--- Статус подзадач ---")
        status = subtask_agent.get_subtask_status(planning_result.subtasks)
        print(f"Всего подзадач: {status['subtasks_count']}")
        print(f"Всего команд: {status['total_commands']}")
        print(f"Всего health-check: {status['total_health_checks']}")
        
        print("\n✓ Пример завершен успешно!")
        
    except Exception as e:
        print(f"✗ Ошибка выполнения примера: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
