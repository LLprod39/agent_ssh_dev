"""
Пример использования TaskMasterIntegration

Этот пример демонстрирует основные возможности интеграции с Task Master:
- Улучшение промтов
- Парсинг PRD документов
- Генерация задач из PRD
- Валидация и форматирование промтов
"""

import sys
import os
from pathlib import Path

# Добавляем путь к корню проекта для импорта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.task_master_integration import TaskMasterIntegration
from src.config.agent_config import TaskmasterConfig, AgentConfig


def main():
    """Основная функция примера"""
    print("=== Пример использования TaskMasterIntegration ===\n")
    
    # Создаем конфигурацию Task Master
    taskmaster_config = TaskmasterConfig(
        enabled=True,
        model="gpt-4",
        temperature=0.7,
        max_tokens=1000
    )
    
    # Инициализируем интеграцию
    project_root = Path(__file__).parent.parent
    integration = TaskMasterIntegration(taskmaster_config, project_root)
    
    # Проверяем статус Task Master
    print("1. Проверка статуса Task Master:")
    status = integration.get_taskmaster_status()
    print(f"   Включен: {status['enabled']}")
    print(f"   Статус установки: {status['installation_status']}")
    print(f"   Директория существует: {status['taskmaster_dir_exists']}")
    print(f"   PRD файл существует: {status['prd_file_exists']}")
    if 'version' in status:
        print(f"   Версия: {status['version']}")
    print()
    
    # Пример улучшения промта
    print("2. Улучшение промта:")
    original_prompt = """
    Создай план для установки PostgreSQL на Ubuntu сервере.
    Нужно установить базу данных, настроить пользователей и создать базу для приложения.
    """
    
    context = {
        "task_type": "database_setup",
        "os": "ubuntu",
        "complexity": "medium"
    }
    
    result = integration.improve_prompt(original_prompt, context)
    if result.success:
        print("   ✅ Промт успешно улучшен")
        if isinstance(result.data, dict) and "improved_prompt" in result.data:
            print(f"   Улучшенный промт: {result.data['improved_prompt'][:200]}...")
        else:
            print(f"   Результат: {result.data}")
    else:
        print(f"   ❌ Ошибка улучшения промта: {result.error}")
    print()
    
    # Пример валидации промта
    print("3. Валидация промта:")
    test_prompt = "Установи PostgreSQL и создай базу данных myapp"
    
    validation_result = integration.validate_prompt(test_prompt, "planning")
    if validation_result.success:
        print("   ✅ Промт валидирован")
        if isinstance(validation_result.data, dict):
            print(f"   Валидный: {validation_result.data.get('valid', 'unknown')}")
            if 'score' in validation_result.data:
                print(f"   Оценка: {validation_result.data['score']}")
    else:
        print(f"   ❌ Ошибка валидации: {validation_result.error}")
    print()
    
    # Пример форматирования промта
    print("4. Форматирование промта:")
    unformatted_prompt = "install postgresql create database myapp setup users"
    
    format_result = integration.format_prompt(unformatted_prompt, "structured")
    if format_result.success:
        print("   ✅ Промт отформатирован")
        if isinstance(format_result.data, dict) and "formatted_prompt" in format_result.data:
            print(f"   Отформатированный промт: {format_result.data['formatted_prompt']}")
    else:
        print(f"   ❌ Ошибка форматирования: {format_result.error}")
    print()
    
    # Пример парсинга PRD (если файл существует)
    print("5. Парсинг PRD:")
    prd_result = integration.parse_prd()
    if prd_result.success:
        print("   ✅ PRD успешно распарсен")
        if isinstance(prd_result.data, dict):
            print(f"   Ключи в данных: {list(prd_result.data.keys())}")
    else:
        print(f"   ❌ Ошибка парсинга PRD: {prd_result.error}")
    print()
    
    # Пример генерации задач из PRD
    print("6. Генерация задач из PRD:")
    tasks_result = integration.generate_tasks_from_prd(num_tasks=3)
    if tasks_result.success:
        print("   ✅ Задачи успешно сгенерированы")
        if isinstance(tasks_result.data, dict):
            print(f"   Ключи в данных: {list(tasks_result.data.keys())}")
    else:
        print(f"   ❌ Ошибка генерации задач: {tasks_result.error}")
    print()
    
    # Пример создания кастомного PRD
    print("7. Создание кастомного PRD:")
    custom_prd_content = """
# Кастомный PRD для тестирования

## Обзор
Это тестовый PRD документ для демонстрации функциональности.

## Основные функции
- Функция 1: Тестирование
- Функция 2: Демонстрация

## Пользовательский опыт
- Простота использования
- Интуитивный интерфейс

## Техническая архитектура
- Модульная структура
- API интеграция

## План разработки
- Этап 1: Базовая функциональность
- Этап 2: Расширенные возможности

## Риски и митигация
- Риск 1: Технические сложности
  - Митигация: Поэтапная разработка
"""
    
    create_result = integration.create_custom_prd(custom_prd_content, "test_prd.txt")
    if create_result:
        print("   ✅ Кастомный PRD создан")
        
        # Пытаемся распарсить созданный PRD
        parse_custom_result = integration.parse_prd("test_prd.txt")
        if parse_custom_result.success:
            print("   ✅ Кастомный PRD успешно распарсен")
        else:
            print(f"   ❌ Ошибка парсинга кастомного PRD: {parse_custom_result.error}")
    else:
        print("   ❌ Ошибка создания кастомного PRD")
    print()
    
    print("=== Пример завершен ===")


def demonstrate_disabled_taskmaster():
    """Демонстрация работы с отключенным Task Master"""
    print("\n=== Демонстрация отключенного Task Master ===")
    
    # Создаем отключенную конфигурацию
    disabled_config = TaskmasterConfig(
        enabled=False,
        model="gpt-4",
        temperature=0.7,
        max_tokens=1000
    )
    
    project_root = Path(__file__).parent.parent
    integration = TaskMasterIntegration(disabled_config, project_root)
    
    # Тестируем улучшение промта с отключенным Task Master
    result = integration.improve_prompt("Тестовый промт")
    if result.success:
        print("✅ Промт обработан (Task Master отключен)")
        print(f"   Результат: {result.data}")
    else:
        print(f"❌ Ошибка: {result.error}")
    
    # Тестируем парсинг PRD с отключенным Task Master
    prd_result = integration.parse_prd()
    if not prd_result.success:
        print("✅ Парсинг PRD корректно отключен")
        print(f"   Сообщение: {prd_result.error}")
    
    print("=== Демонстрация завершена ===")


if __name__ == "__main__":
    try:
        main()
        demonstrate_disabled_taskmaster()
    except Exception as e:
        print(f"Ошибка выполнения примера: {e}")
        import traceback
        traceback.print_exc()
