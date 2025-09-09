#!/usr/bin/env python3
"""
Скрипт для запуска всех тестов проекта SSH Agent
"""
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, description):
    """Запуск команды с выводом описания"""
    print(f"\n{'='*60}")
    print(f"🚀 {description}")
    print(f"{'='*60}")
    print(f"Выполняется: {command}")
    print("-" * 60)
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=False)
        print(f"✅ {description} - УСПЕШНО")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ОШИБКА (код: {e.returncode})")
        return False


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Запуск тестов SSH Agent")
    parser.add_argument("--unit", action="store_true", help="Запустить только unit тесты")
    parser.add_argument("--integration", action="store_true", help="Запустить только интеграционные тесты")
    parser.add_argument("--coverage", action="store_true", help="Запустить с покрытием кода")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument("--parallel", "-n", type=int, default=4, help="Количество параллельных процессов")
    parser.add_argument("--pattern", "-k", help="Фильтр тестов по паттерну")
    parser.add_argument("--file", help="Запустить тесты из конкретного файла")
    
    args = parser.parse_args()
    
    # Определяем базовую команду pytest
    base_cmd = "python -m pytest"
    
    # Добавляем опции
    if args.verbose:
        base_cmd += " -v"
    
    if args.coverage:
        base_cmd += " --cov=src --cov-report=html --cov-report=term"
    
    if args.parallel > 1:
        base_cmd += f" -n {args.parallel}"
    
    if args.pattern:
        base_cmd += f" -k '{args.pattern}'"
    
    if args.file:
        base_cmd += f" {args.file}"
    
    # Определяем какие тесты запускать
    test_commands = []
    
    if args.unit or not (args.unit or args.integration):
        # Unit тесты
        unit_tests = [
            "tests/test_agents/",
            "tests/test_connectors/",
            "tests/test_models/",
            "tests/test_utils/"
        ]
        
        for test_dir in unit_tests:
            if Path(test_dir).exists():
                test_commands.append((f"{base_cmd} {test_dir}", f"Unit тесты: {test_dir}"))
    
    if args.integration or not (args.unit or args.integration):
        # Интеграционные тесты
        integration_tests = [
            "tests/test_integration/"
        ]
        
        for test_dir in integration_tests:
            if Path(test_dir).exists():
                test_commands.append((f"{base_cmd} {test_dir}", f"Интеграционные тесты: {test_dir}"))
    
    # Если указан конкретный файл, запускаем только его
    if args.file:
        test_commands = [(f"{base_cmd} {args.file}", f"Тесты из файла: {args.file}")]
    
    # Запускаем тесты
    print("🧪 ЗАПУСК ТЕСТОВ SSH AGENT")
    print("=" * 60)
    
    success_count = 0
    total_count = len(test_commands)
    
    for command, description in test_commands:
        if run_command(command, description):
            success_count += 1
    
    # Итоговый отчет
    print(f"\n{'='*60}")
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print(f"{'='*60}")
    print(f"Всего тестовых групп: {total_count}")
    print(f"Успешно: {success_count}")
    print(f"С ошибками: {total_count - success_count}")
    
    if success_count == total_count:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        return 0
    else:
        print("💥 НЕКОТОРЫЕ ТЕСТЫ ЗАВЕРШИЛИСЬ С ОШИБКАМИ!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
