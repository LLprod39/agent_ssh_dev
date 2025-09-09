#!/usr/bin/env python3
"""
Пример использования CLI интерфейса SSH Agent.

Этот скрипт демонстрирует различные способы использования CLI.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

def run_command(command: str, description: str = ""):
    """Выполнить команду и показать результат."""
    print(f"\n{'='*60}")
    print(f"Команда: {command}")
    if description:
        print(f"Описание: {description}")
    print('='*60)
    
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"Код возврата: {result.returncode}")
        
    except Exception as e:
        print(f"Ошибка выполнения команды: {e}")


def main():
    """Основная функция демонстрации CLI."""
    print("SSH Agent CLI - Примеры использования")
    print("="*60)
    
    # 1. Инициализация конфигурации
    print("\n1. Инициализация конфигурации")
    run_command(
        "python ssh-agent init",
        "Создание файлов конфигурации по умолчанию"
    )
    
    # 2. Валидация конфигурации
    print("\n2. Валидация конфигурации")
    run_command(
        "python ssh-agent config validate",
        "Проверка корректности конфигурации"
    )
    
    # 3. Показ статуса
    print("\n3. Показ статуса агента")
    run_command(
        "python ssh-agent status",
        "Отображение статуса и статистики агента"
    )
    
    # 4. Показ конфигурации
    print("\n4. Показ конфигурации")
    run_command(
        "python ssh-agent config show",
        "Отображение текущей конфигурации"
    )
    
    # 5. Предварительный просмотр задачи
    print("\n5. Предварительный просмотр задачи")
    run_command(
        "python ssh-agent execute 'Установить nginx на сервере' --dry-run",
        "Показ плана выполнения без фактического выполнения"
    )
    
    # 6. Показ истории (если есть)
    print("\n6. Показ истории выполнения")
    run_command(
        "python ssh-agent history --limit 5",
        "Отображение последних 5 выполнений"
    )
    
    # 7. Справка
    print("\n7. Справка по командам")
    run_command(
        "python ssh-agent --help",
        "Показ общей справки"
    )
    
    # 8. Справка по конкретной команде
    print("\n8. Справка по команде execute")
    run_command(
        "python ssh-agent execute --help",
        "Показ справки по команде execute"
    )
    
    print("\n" + "="*60)
    print("Демонстрация завершена!")
    print("="*60)
    
    print("\nДополнительные примеры:")
    print("- python ssh-agent interactive  # Интерактивный режим")
    print("- python ssh-agent execute 'задача' --verbose  # Подробный вывод")
    print("- python ssh-agent cleanup --days 3  # Очистка данных")
    print("- python ssh-agent config edit  # Информация о редактировании")


if __name__ == "__main__":
    main()
