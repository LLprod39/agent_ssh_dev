"""
Пример использования Task Agent для планирования задач
"""
import sys
import os
from pathlib import Path
from unittest.mock import patch

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.task_agent import TaskAgent, TaskPlanningContext
from src.config.agent_config import AgentConfig
from src.agents.task_master_integration import TaskMasterIntegration
from src.utils.logger import setup_logging


def main():
    """Основная функция примера"""
    
    # Настройка логирования
    setup_logging({
        'level': 'INFO',
        'log_file': 'logs/task_agent_example.log',
        'error_file': 'logs/task_agent_errors.log',
        'max_file_size': '10 MB',
        'retention_days': 7,
        'compression': True
    })
    
    print("=== Пример использования Task Agent ===\n")
    
    try:
        # Загрузка конфигурации
        config_path = project_root / "examples" / "test_config.yaml"
        if not config_path.exists():
            print(f"❌ Файл конфигурации не найден: {config_path}")
            return
        
        config = AgentConfig.from_yaml(str(config_path))
        print("✅ Конфигурация загружена")
        
        # Инициализация Task Master (опционально)
        task_master = None
        if config.taskmaster.enabled:
            try:
                task_master = TaskMasterIntegration(config.taskmaster, project_root)
                print("✅ Task Master инициализирован")
            except Exception as e:
                print(f"⚠️ Task Master недоступен: {e}")
                print("Продолжаем без Task Master...")
        
        # Создание Task Agent с принудительным мок-режимом
        from src.models.llm_interface import MockLLMInterface
        mock_interface = MockLLMInterface()
        
        with patch('src.agents.task_agent.LLMInterfaceFactory.create_interface') as mock_factory:
            mock_factory.return_value = mock_interface
            
            task_agent = TaskAgent(config, task_master)
            task_agent.llm_interface = mock_interface
            print("✅ Task Agent создан (мок-режим)")
            
            # Пример 1: Простая задача
            print("\n--- Пример 1: Установка nginx ---")
            simple_task = "Установить и настроить nginx на Ubuntu сервере"
            
            result = task_agent.plan_task(simple_task)
        
        if result.success:
            print(f"✅ Задача спланирована: {result.task.title}")
            print(f"📊 Количество шагов: {len(result.task.steps)}")
            print(f"⏱️ Время планирования: {result.planning_duration:.2f}s")
            
            print("\n📋 План выполнения:")
            for i, step in enumerate(result.task.steps, 1):
                print(f"  {i}. {step.title}")
                print(f"     Описание: {step.description}")
                print(f"     Приоритет: {step.priority.value}")
                print(f"     Время: {step.estimated_duration} мин" if step.estimated_duration else "     Время: не указано")
                if step.dependencies:
                    print(f"     Зависимости: {', '.join(step.dependencies)}")
                print()
        else:
            print(f"❌ Ошибка планирования: {result.error_message}")
        
        # Пример 2: Сложная задача с контекстом
        print("\n--- Пример 2: Настройка веб-сервера с SSL ---")
        
        context = TaskPlanningContext(
            server_info={
                "os": "ubuntu",
                "version": "20.04",
                "architecture": "x86_64",
                "memory": "4GB",
                "disk": "50GB"
            },
            user_requirements="Настроить веб-сервер с SSL сертификатом и автоматическим обновлением",
            constraints=[
                "Не перезагружать сервер",
                "Использовать только официальные репозитории",
                "Минимальное время простоя"
            ],
            available_tools=[
                "apt", "systemctl", "certbot", "nginx", "ufw", "curl", "openssl"
            ],
            previous_tasks=[
                {
                    "task_id": "prev_1",
                    "title": "Базовая настройка сервера",
                    "status": "completed"
                }
            ],
            environment={
                "production": True,
                "domain": "example.com",
                "email": "admin@example.com"
            }
        )
        
        complex_task = """
        Настроить полноценный веб-сервер с:
        1. Nginx как веб-сервер
        2. SSL сертификат от Let's Encrypt
        3. Автоматическое обновление сертификатов
        4. Настройка файрвола
        5. Мониторинг работоспособности
        """
        
        result = task_agent.plan_task(complex_task, context)
        
        if result.success:
            print(f"✅ Сложная задача спланирована: {result.task.title}")
            print(f"📊 Количество шагов: {len(result.task.steps)}")
            print(f"⏱️ Общее время: {result.task.total_estimated_duration} мин")
            
            print("\n📋 Детальный план:")
            for i, step in enumerate(result.task.steps, 1):
                print(f"  {i}. {step.title}")
                print(f"     📝 {step.description}")
                print(f"     🎯 Приоритет: {step.priority.value}")
                print(f"     ⏰ Время: {step.estimated_duration} мин" if step.estimated_duration else "     ⏰ Время: не указано")
                if step.dependencies:
                    print(f"     🔗 Зависимости: {', '.join(step.dependencies)}")
                print()
            
            # Показываем прогресс
            progress = result.task.get_progress()
            print(f"📈 Прогресс: {progress['progress_percentage']:.1f}% "
                  f"({progress['completed_steps']}/{progress['total_steps']} шагов)")
        
        # Пример 3: Демонстрация валидации
        print("\n--- Пример 3: Валидация плана ---")
        
        # Создаем задачу с проблемами
        problematic_task = Task(title="Проблемная задача", description="Задача с ошибками")
        
        # Добавляем шаги с циклическими зависимостями
        from src.models.planning_model import TaskStep
        step1 = TaskStep(title="Шаг 1", step_id="step_1", dependencies=["step_2"])
        step2 = TaskStep(title="Шаг 2", step_id="step_2", dependencies=["step_1"])
        
        problematic_task.add_step(step1)
        problematic_task.add_step(step2)
        
        validation_result = task_agent._validate_plan(problematic_task)
        
        print(f"🔍 Результат валидации: {'✅ Валиден' if validation_result['valid'] else '❌ Невалиден'}")
        if not validation_result['valid']:
            print("🚨 Проблемы:")
            for issue in validation_result['issues']:
                print(f"   - {issue}")
        
        # Пример 4: Обновление статуса шагов
        print("\n--- Пример 4: Управление статусом ---")
        
        if result.success and result.task.steps:
            # Берем первый шаг для демонстрации
            first_step = result.task.steps[0]
            print(f"📋 Шаг: {first_step.title}")
            print(f"📊 Статус: {first_step.status.value}")
            
            # Обновляем статус
            task_agent.update_step_status(result.task, first_step.step_id, 
                                        task_agent._get_step_status_enum("EXECUTING"))
            print(f"🔄 Статус обновлен: {first_step.status.value}")
            
            # Показываем статус задачи
            task_status = task_agent.get_task_status(result.task)
            print(f"📈 Статус задачи: {task_status['status']}")
        
        print("\n=== Пример завершен ===")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения примера: {e}")
        import traceback
        traceback.print_exc()


def demonstrate_task_master_integration():
    """Демонстрация интеграции с Task Master"""
    print("\n--- Демонстрация Task Master ---")
    
    try:
        # Создаем простую конфигурацию
        from src.config.agent_config import TaskmasterConfig
        taskmaster_config = TaskmasterConfig(
            enabled=True,
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        task_master = TaskMasterIntegration(taskmaster_config, project_root)
        
        # Проверяем статус
        status = task_master.get_taskmaster_status()
        print(f"📊 Статус Task Master:")
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        # Улучшаем промт
        test_prompt = "Создай план установки Docker на Ubuntu"
        result = task_master.improve_prompt(test_prompt)
        
        if result.success:
            print("✅ Промт улучшен через Task Master")
            if "improved_prompt" in result.data:
                print(f"📝 Улучшенный промт: {result.data['improved_prompt'][:100]}...")
        else:
            print(f"❌ Ошибка улучшения промта: {result.error}")
            
    except Exception as e:
        print(f"⚠️ Task Master недоступен: {e}")


if __name__ == "__main__":
    main()
    
    # Дополнительная демонстрация Task Master
    demonstrate_task_master_integration()
