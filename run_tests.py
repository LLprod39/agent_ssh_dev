#!/usr/bin/env python3
"""
Скрипт для запуска тестов SSH Agent

Поддерживает различные режимы тестирования:
- unit: Unit тесты
- integration: Интеграционные тесты
- error_scenarios: Тесты сценариев ошибок
- all: Все тесты
- coverage: Тесты с покрытием кода
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(command, description):
    """Запускает команду и выводит результат"""
    print(f"\n{'='*60}")
    print(f"Запуск: {description}")
    print(f"Команда: {' '.join(command)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=False)
        print(f"✅ {description} - УСПЕШНО")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ОШИБКА (код: {e.returncode})")
        return False


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Запуск тестов SSH Agent")
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "error_scenarios", "all", "coverage"],
        help="Тип тестов для запуска"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Параллельный запуск тестов"
    )
    parser.add_argument(
        "--stop-on-first-failure", "-x",
        action="store_true",
        help="Остановиться на первой ошибке"
    )
    
    args = parser.parse_args()
    
    # Базовые опции pytest
    base_options = ["-v" if args.verbose else "-q"]
    
    if args.stop_on_first_failure:
        base_options.append("-x")
    
    if args.parallel:
        base_options.extend(["-n", "auto"])
    
    # Определяем команды для разных типов тестов
    commands = {
        "unit": ["python", "-m", "pytest"] + base_options + [
            "-m", "unit",
            "tests/test_agents/",
            "tests/test_connectors/",
            "tests/test_models/",
            "tests/test_utils/"
        ],
        
        "integration": ["python", "-m", "pytest"] + base_options + [
            "-m", "integration",
            "tests/test_integration/"
        ],
        
        "error_scenarios": ["python", "-m", "pytest"] + base_options + [
            "-m", "error_scenarios",
            "tests/test_error_scenarios/"
        ],
        
        "all": ["python", "-m", "pytest"] + base_options + [
            "tests/"
        ],
        
        "coverage": ["python", "-m", "pytest"] + base_options + [
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=xml",
            "--cov-fail-under=80",
            "tests/"
        ]
    }
    
    # Запускаем тесты
    command = commands[args.test_type]
    success = run_command(command, f"Тесты типа: {args.test_type}")
    
    if success:
        print(f"\n🎉 Все тесты типа '{args.test_type}' прошли успешно!")
        
        if args.test_type == "coverage":
            print("\n📊 Отчет о покрытии кода:")
            print("- HTML отчет: htmlcov/index.html")
            print("- XML отчет: coverage.xml")
    else:
        print(f"\n💥 Тесты типа '{args.test_type}' завершились с ошибками!")
        sys.exit(1)


if __name__ == "__main__":
    main()
