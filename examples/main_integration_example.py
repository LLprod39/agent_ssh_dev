"""
Пример использования главного класса SSHAgent с полной интеграцией компонентов
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к src для импорта
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import SSHAgent
from config.server_config import ServerConfig
from config.agent_config import AgentConfig, LLMConfig


async def main():
    """Основная функция демонстрации интеграции"""
    
    print("=== SSH Agent Integration Example ===\n")
    
    # Создание конфигурации
    print("1. Создание конфигурации...")
    
    server_config = ServerConfig(
        host="localhost",
        username="test_user",
        auth_method="key",
        os_type="ubuntu",
        forbidden_commands=["rm -rf /", "dd if=/dev/zero"],
        installed_services=["docker", "nginx"]
    )
    
    agent_config = AgentConfig(
        llm=LLMConfig(api_key="your-api-key-here")
    )
    
    print("✓ Конфигурация создана")
    
    # Инициализация агента
    print("\n2. Инициализация SSH Agent...")
    
    try:
        agent = SSHAgent()
        print("✓ SSH Agent инициализирован")
    except Exception as e:
        print(f"✗ Ошибка инициализации: {e}")
        return
    
    # Проверка статуса агента
    print("\n3. Проверка статуса агента...")
    
    status = agent.get_agent_status()
    print(f"✓ Статус получен:")
    print(f"  - Задач выполнено: {status['agent_stats']['tasks_executed']}")
    print(f"  - Компонентов инициализировано: {sum(status['components_status'].values())}")
    print(f"  - Текущее выполнение: {'Активно' if status['current_execution']['is_running'] else 'Неактивно'}")
    
    # Демонстрация dry-run режима
    print("\n4. Демонстрация dry-run режима...")
    
    test_task = "Установить и настроить nginx на сервере"
    print(f"Задача: {test_task}")
    
    try:
        result = await agent.execute_task(test_task, dry_run=True)
        
        if result["success"]:
            print("✓ Dry-run выполнен успешно")
            print(f"  - Шагов запланировано: {result['total_steps']}")
            print(f"  - Время выполнения: {result['execution_duration']:.2f}с")
            print(f"  - Прогресс: {result['progress_percentage']:.1f}%")
        else:
            print(f"✗ Dry-run завершен с ошибками: {result.get('error', 'Неизвестная ошибка')}")
            
    except Exception as e:
        print(f"✗ Ошибка выполнения dry-run: {e}")
    
    # Проверка истории выполнения
    print("\n5. Проверка истории выполнения...")
    
    history = agent.get_execution_history(5)
    print(f"✓ История выполнения: {len(history)} записей")
    
    if history:
        latest = history[-1]
        print(f"  - Последняя задача: {latest['task_title']}")
        print(f"  - Статус: {'✓' if latest['success'] else '✗'}")
        print(f"  - Время выполнения: {latest['duration']:.2f}с")
    
    # Демонстрация очистки данных
    print("\n6. Демонстрация очистки данных...")
    
    try:
        agent.cleanup_old_data(7)
        print("✓ Очистка старых данных выполнена")
    except Exception as e:
        print(f"✗ Ошибка очистки данных: {e}")
    
    # Финальный статус
    print("\n7. Финальный статус агента...")
    
    final_status = agent.get_agent_status()
    print(f"✓ Финальная статистика:")
    print(f"  - Задач выполнено: {final_status['agent_stats']['tasks_executed']}")
    print(f"  - Задач завершено: {final_status['agent_stats']['tasks_completed']}")
    print(f"  - Задач провалено: {final_status['agent_stats']['tasks_failed']}")
    print(f"  - Общее время выполнения: {final_status['agent_stats']['total_execution_time']:.2f}с")
    print(f"  - Эскалаций: {final_status['agent_stats']['escalations']}")
    
    print("\n=== Интеграция завершена ===")


def demonstrate_component_coordination():
    """Демонстрация координации компонентов"""
    
    print("\n=== Демонстрация координации компонентов ===\n")
    
    try:
        # Создание агента
        agent = SSHAgent()
        
        # Проверка компонентов
        components = agent.get_agent_status()['components_status']
        
        print("Статус компонентов:")
        for component_name, is_available in components.items():
            status = "✓ Доступен" if is_available else "✗ Недоступен"
            print(f"  - {component_name}: {status}")
        
        # Проверка системы управления состоянием
        print(f"\nСистема управления состоянием:")
        print(f"  - Текущее выполнение: {'Активно' if agent.current_execution_state else 'Неактивно'}")
        print(f"  - История выполнения: {len(agent.execution_history)} записей")
        
        # Проверка статистики
        stats = agent.agent_stats
        print(f"\nСтатистика агента:")
        print(f"  - Задач выполнено: {stats['tasks_executed']}")
        print(f"  - Общее время выполнения: {stats['total_execution_time']:.2f}с")
        print(f"  - Эскалаций: {stats['escalations']}")
        
        print("\n✓ Координация компонентов работает корректно")
        
    except Exception as e:
        print(f"✗ Ошибка координации компонентов: {e}")


def demonstrate_error_handling():
    """Демонстрация обработки ошибок"""
    
    print("\n=== Демонстрация обработки ошибок ===\n")
    
    try:
        agent = SSHAgent()
        
        # Проверка обработчика ошибок
        if agent.error_handler:
            print("✓ Обработчик ошибок инициализирован")
            
            # Получение статистики обработчика ошибок
            handler_stats = agent.error_handler.get_handler_stats()
            print(f"  - Отчетов сгенерировано: {handler_stats['reports_generated']}")
            print(f"  - Снимков создано: {handler_stats['snapshots_taken']}")
            print(f"  - Паттернов выявлено: {handler_stats['patterns_identified']}")
            print(f"  - Эскалаций отправлено: {handler_stats['escalations_sent']}")
            
            # Проверка колбэков
            callbacks = handler_stats['callbacks_registered']
            print(f"  - Колбэков планировщика: {callbacks['planner_callbacks']}")
            print(f"  - Колбэков эскалации: {callbacks['human_escalation_callbacks']}")
            
        else:
            print("✗ Обработчик ошибок не инициализирован")
        
        print("\n✓ Система обработки ошибок работает корректно")
        
    except Exception as e:
        print(f"✗ Ошибка системы обработки ошибок: {e}")


if __name__ == "__main__":
    print("Запуск примера интеграции SSH Agent...")
    
    # Демонстрация координации компонентов
    demonstrate_component_coordination()
    
    # Демонстрация обработки ошибок
    demonstrate_error_handling()
    
    # Основная демонстрация
    print("\nЗапуск основной демонстрации...")
    asyncio.run(main())
