#!/usr/bin/env python3
"""
Пример использования системы автокоррекции

Этот пример демонстрирует:
- Различные стратегии автокоррекции
- Обработку типичных ошибок
- Интеграцию с Execution Model
- Статистику исправлений
"""

import sys
import os
import time
from typing import Dict, Any

# Добавляем путь к src для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from src.utils.autocorrection import AutocorrectionEngine, CorrectionStrategy
    from src.models.execution_model import CommandResult, ExecutionStatus, ExecutionContext
    from src.agents.subtask_agent import Subtask
    from src.utils.logger import StructuredLogger
except ImportError:
    # Альтернативный способ импорта
    from utils.autocorrection import AutocorrectionEngine, CorrectionStrategy
    from models.execution_model import CommandResult, ExecutionStatus, ExecutionContext
    from agents.subtask_agent import Subtask
    from utils.logger import StructuredLogger


class MockSSHConnection:
    """Мок SSH соединения для тестирования"""
    
    def __init__(self, responses: Dict[str, tuple]):
        """
        Инициализация мок соединения
        
        Args:
            responses: Словарь команд и их ответов (stdout, stderr, exit_code)
        """
        self.responses = responses
        self.logger = StructuredLogger("MockSSHConnection")
    
    def execute_command(self, command: str, timeout: int = 30) -> tuple:
        """Выполнение команды с мок ответом"""
        self.logger.debug("Выполнение команды", command=command)
        
        # Имитируем задержку
        time.sleep(0.1)
        
        # Ищем ответ для команды
        for cmd_pattern, response in self.responses.items():
            if cmd_pattern in command:
                return response
        
        # Если команда не найдена, возвращаем успешный результат
        return ("Команда выполнена успешно", "", 0)


def create_test_context(responses: Dict[str, tuple]) -> ExecutionContext:
    """Создание тестового контекста"""
    mock_ssh = MockSSHConnection(responses)
    
    # Создаем тестовую подзадачу
    subtask = Subtask(
        subtask_id="test_001",
        title="Тестовая подзадача",
        description="Тестирование системы автокоррекции",
        commands=["test_command"],
        health_checks=[],
        rollback_commands=[]
    )
    
    return ExecutionContext(
        subtask=subtask,
        ssh_connection=mock_ssh,
        server_info={"os": "ubuntu", "version": "20.04"},
        environment={"PATH": "/usr/bin:/bin"}
    )


def test_syntax_correction():
    """Тест исправления синтаксических ошибок"""
    print("\n=== Тест исправления синтаксических ошибок ===")
    
    # Создаем движок автокоррекции
    engine = AutocorrectionEngine(max_attempts=3)
    
    # Тестовые команды с синтаксическими ошибками
    test_cases = [
        "ls  -la   /tmp",  # Двойные пробелы
        "grep 'pattern' file.txt",  # Неправильные кавычки
        "find /home -name '*.txt'",  # Обычная команда
    ]
    
    for command in test_cases:
        print(f"\nИсходная команда: {command}")
        
        # Создаем результат с ошибкой
        result = CommandResult(
            command=command,
            success=False,
            exit_code=1,
            stderr="syntax error",
            status=ExecutionStatus.FAILED,
            error_message="syntax error"
        )
        
        # Создаем контекст
        context = create_test_context({})
        
        # Применяем автокоррекцию
        correction_result = engine.correct_command(result, context)
        
        if correction_result.success:
            print(f"✅ Исправлено: {correction_result.final_command}")
            print(f"   Стратегия: {correction_result.attempts[0].strategy.value}")
        else:
            print("❌ Исправление не удалось")


def test_permission_correction():
    """Тест исправления ошибок прав доступа"""
    print("\n=== Тест исправления ошибок прав доступа ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    
    test_cases = [
        "apt install nginx",
        "systemctl start nginx",
        "mkdir /var/log/test",
        "chmod 755 /tmp/test"
    ]
    
    for command in test_cases:
        print(f"\nИсходная команда: {command}")
        
        result = CommandResult(
            command=command,
            success=False,
            exit_code=1,
            stderr="permission denied",
            status=ExecutionStatus.FAILED,
            error_message="permission denied"
        )
        
        context = create_test_context({})
        correction_result = engine.correct_command(result, context)
        
        if correction_result.success:
            print(f"✅ Исправлено: {correction_result.final_command}")
            print(f"   Стратегия: {correction_result.attempts[0].strategy.value}")
        else:
            print("❌ Исправление не удалось")


def test_network_correction():
    """Тест исправления сетевых ошибок"""
    print("\n=== Тест исправления сетевых ошибок ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    
    test_cases = [
        "curl -O https://example.com/file.txt",
        "wget https://example.com/file.txt",
        "ping google.com"
    ]
    
    for command in test_cases:
        print(f"\nИсходная команда: {command}")
        
        result = CommandResult(
            command=command,
            success=False,
            exit_code=1,
            stderr="connection refused",
            status=ExecutionStatus.FAILED,
            error_message="connection refused"
        )
        
        context = create_test_context({})
        correction_result = engine.correct_command(result, context)
        
        if correction_result.success:
            print(f"✅ Исправлено: {correction_result.final_command}")
            print(f"   Стратегия: {correction_result.attempts[0].strategy.value}")
        else:
            print("❌ Исправление не удалось")


def test_service_correction():
    """Тест исправления ошибок сервисов"""
    print("\n=== Тест исправления ошибок сервисов ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    
    test_cases = [
        "systemctl start nginx",
        "systemctl enable docker",
        "service apache2 restart"
    ]
    
    for command in test_cases:
        print(f"\nИсходная команда: {command}")
        
        result = CommandResult(
            command=command,
            success=False,
            exit_code=1,
            stderr="service not found",
            status=ExecutionStatus.FAILED,
            error_message="service not found"
        )
        
        context = create_test_context({})
        correction_result = engine.correct_command(result, context)
        
        if correction_result.success:
            print(f"✅ Исправлено: {correction_result.final_command}")
            print(f"   Стратегия: {correction_result.attempts[0].strategy.value}")
        else:
            print("❌ Исправление не удалось")


def test_package_correction():
    """Тест исправления ошибок пакетов"""
    print("\n=== Тест исправления ошибок пакетов ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    
    test_cases = [
        "apt install nginx",
        "apt install docker.io",
        "apt remove apache2"
    ]
    
    for command in test_cases:
        print(f"\nИсходная команда: {command}")
        
        result = CommandResult(
            command=command,
            success=False,
            exit_code=1,
            stderr="package not found",
            status=ExecutionStatus.FAILED,
            error_message="package not found"
        )
        
        context = create_test_context({})
        correction_result = engine.correct_command(result, context)
        
        if correction_result.success:
            print(f"✅ Исправлено: {correction_result.final_command}")
            print(f"   Стратегия: {correction_result.attempts[0].strategy.value}")
        else:
            print("❌ Исправление не удалось")


def test_command_substitution():
    """Тест замены команд"""
    print("\n=== Тест замены команд ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    
    test_cases = [
        "service nginx start",
        "chkconfig nginx on",
        "ifconfig eth0",
        "netstat -tulpn"
    ]
    
    for command in test_cases:
        print(f"\nИсходная команда: {command}")
        
        result = CommandResult(
            command=command,
            success=False,
            exit_code=1,
            stderr="command not found",
            status=ExecutionStatus.FAILED,
            error_message="command not found"
        )
        
        context = create_test_context({})
        correction_result = engine.correct_command(result, context)
        
        if correction_result.success:
            print(f"✅ Исправлено: {correction_result.final_command}")
            print(f"   Стратегия: {correction_result.attempts[0].strategy.value}")
        else:
            print("❌ Исправление не удалось")


def test_multiple_attempts():
    """Тест множественных попыток исправления"""
    print("\n=== Тест множественных попыток исправления ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    
    # Команда, которая требует нескольких исправлений
    command = "apt install nginx"
    
    print(f"Исходная команда: {command}")
    
    result = CommandResult(
        command=command,
        success=False,
        exit_code=1,
        stderr="permission denied",
        status=ExecutionStatus.FAILED,
        error_message="permission denied"
    )
    
    context = create_test_context({})
    correction_result = engine.correct_command(result, context)
    
    if correction_result.success:
        print(f"✅ Исправлено: {correction_result.final_command}")
        print(f"   Количество попыток: {correction_result.total_attempts}")
        print("   Стратегии исправления:")
        for i, attempt in enumerate(correction_result.attempts, 1):
            print(f"     {i}. {attempt.strategy.value}: {attempt.corrected_command}")
    else:
        print("❌ Исправление не удалось")
        print(f"   Количество попыток: {correction_result.total_attempts}")


def test_autocorrection_stats():
    """Тест статистики автокоррекции"""
    print("\n=== Статистика автокоррекции ===")
    
    engine = AutocorrectionEngine(max_attempts=3)
    stats = engine.get_correction_stats()
    
    print("Статистика движка автокоррекции:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


def main():
    """Основная функция для запуска всех тестов"""
    print("🚀 Запуск тестов системы автокоррекции")
    print("=" * 50)
    
    try:
        # Запускаем все тесты
        test_syntax_correction()
        test_permission_correction()
        test_network_correction()
        test_service_correction()
        test_package_correction()
        test_command_substitution()
        test_multiple_attempts()
        test_autocorrection_stats()
        
        print("\n" + "=" * 50)
        print("✅ Все тесты завершены успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
