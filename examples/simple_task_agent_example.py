"""
Простой пример использования Task Agent
"""
import sys
from pathlib import Path
from unittest.mock import patch

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.task_agent import TaskAgent, TaskPlanningContext
from src.config.agent_config import AgentConfig
from src.models.llm_interface import MockLLMInterface


def main():
    """Основная функция примера"""
    
    print("=== Простой пример Task Agent ===\n")
    
    try:
        # Загрузка конфигурации
        config_path = project_root / "examples" / "test_config.yaml"
        config = AgentConfig.from_yaml(str(config_path))
        print("✅ Конфигурация загружена")
        
        # Создание мок-интерфейса LLM
        mock_interface = MockLLMInterface()
        
        # Создание Task Agent с мок-интерфейсом
        with patch('src.agents.task_agent.LLMInterfaceFactory.create_interface') as mock_factory:
            mock_factory.return_value = mock_interface
            
            task_agent = TaskAgent(config)
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
                    if step.estimated_duration:
                        print(f"     Время: {step.estimated_duration} мин")
                    if step.dependencies:
                        print(f"     Зависимости: {', '.join(step.dependencies)}")
                    print()
            else:
                print(f"❌ Ошибка планирования: {result.error_message}")
            
            # Пример 2: Задача с контекстом
            print("\n--- Пример 2: Настройка веб-сервера с SSL ---")
            
            context = TaskPlanningContext(
                server_info={
                    "os": "ubuntu",
                    "version": "20.04",
                    "memory": "4GB"
                },
                user_requirements="Настроить веб-сервер с SSL сертификатом",
                constraints=["Не перезагружать сервер", "Использовать Let's Encrypt"],
                available_tools=["apt", "systemctl", "certbot", "nginx"],
                previous_tasks=[],
                environment={"domain": "example.com", "production": True}
            )
            
            complex_task = "Настроить nginx с SSL сертификатом от Let's Encrypt"
            result = task_agent.plan_task(complex_task, context)
            
            if result.success:
                print(f"✅ Сложная задача спланирована: {result.task.title}")
                print(f"📊 Количество шагов: {len(result.task.steps)}")
                if result.task.total_estimated_duration:
                    print(f"⏱️ Общее время: {result.task.total_estimated_duration} мин")
                
                print("\n📋 Детальный план:")
                for i, step in enumerate(result.task.steps, 1):
                    print(f"  {i}. {step.title}")
                    print(f"     📝 {step.description}")
                    print(f"     🎯 Приоритет: {step.priority.value}")
                    if step.estimated_duration:
                        print(f"     ⏰ Время: {step.estimated_duration} мин")
                    if step.dependencies:
                        print(f"     🔗 Зависимости: {', '.join(step.dependencies)}")
                    print()
                
                # Показываем прогресс
                progress = result.task.get_progress()
                print(f"📈 Прогресс: {progress['progress_percentage']:.1f}% "
                      f"({progress['completed_steps']}/{progress['total_steps']} шагов)")
            
            # Пример 3: Демонстрация валидации
            print("\n--- Пример 3: Валидация плана ---")
            
            from src.models.planning_model import Task, TaskStep, StepStatus
            
            # Создаем задачу с проблемами
            problematic_task = Task(title="Проблемная задача", description="Задача с ошибками")
            
            # Добавляем шаги с циклическими зависимостями
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
                task_agent.update_step_status(result.task, first_step.step_id, StepStatus.EXECUTING)
                print(f"🔄 Статус обновлен: {first_step.status.value}")
                
                # Показываем статус задачи
                task_status = task_agent.get_task_status(result.task)
                print(f"📈 Статус задачи: {task_status['status']}")
            
            print("\n=== Пример завершен ===")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения примера: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
