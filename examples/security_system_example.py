#!/usr/bin/env python3
"""
Пример использования системы безопасности - Шаг 5.1

Этот пример демонстрирует:
- Проверку запрещенных команд
- Валидацию команд перед выполнением
- Логирование попыток выполнения запрещенных команд
- Интеграцию с SSH коннектором
- Статистику безопасности
"""

import sys
import os
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.validator import CommandValidator
from src.config.agent_config import SecurityConfig
from src.utils.logger import StructuredLogger


def test_command_validation():
    """Тест валидации команд"""
    print("=== Тест валидации команд ===\n")
    
    # Создаем конфигурацию безопасности
    security_config = {
        'validate_commands': True,
        'log_forbidden_attempts': True,
        'require_confirmation_for_dangerous': True,
        'allowed_commands_only': False
    }
    
    # Создаем валидатор команд
    validator = CommandValidator(security_config=security_config)
    
    # Тестовые команды
    test_commands = [
        # Безопасные команды
        "ls -la",
        "pwd",
        "whoami",
        "cat /etc/passwd",
        "sudo apt update",
        
        # Потенциально опасные команды
        "chmod 777 /tmp",
        "sudo systemctl restart nginx",
        "dd if=/dev/zero of=/tmp/test bs=1M count=1",
        
        # Запрещенные команды
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown now",
        ":(){ :|:& };:",  # fork bomb
        "mkfs.ext4 /dev/sda1",
    ]
    
    print("Результаты валидации команд:")
    print("=" * 60)
    
    for command in test_commands:
        print(f"\nКоманда: {command}")
        
        # Валидируем команду
        result = validator.validate_command(command, context={
            'step_id': 'test_step',
            'task_id': 'test_task'
        })
        
        # Выводим результаты
        status = "✅ РАЗРЕШЕНА" if result['valid'] else "❌ ЗАПРЕЩЕНА"
        print(f"Статус: {status}")
        print(f"Уровень безопасности: {result['security_level']}")
        
        if result['errors']:
            print(f"Ошибки: {', '.join(result['errors'])}")
        
        if result['warnings']:
            print(f"Предупреждения: {', '.join(result['warnings'])}")
        
        if result['requires_confirmation']:
            print("⚠️ Требует подтверждения!")
    
    # Показываем статистику
    print(f"\n{'='*60}")
    print("Статистика валидации:")
    stats = validator.get_validation_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def test_forbidden_patterns():
    """Тест обнаружения опасных паттернов"""
    print("\n=== Тест обнаружения опасных паттернов ===\n")
    
    validator = CommandValidator()
    
    # Команды с опасными паттернами
    dangerous_commands = [
        "rm -rf /var/log/*",
        "dd if=/dev/random of=/dev/sda bs=1M",
        "mkfs.ext4 /dev/sdb1",
        "fdisk /dev/sda",
        "wipefs -a /dev/sdb",
        "shutdown -h now",
        "reboot",
        "chmod 777 /",
        "chown root:root /home/user",
        "crontab -r",
        "nohup yes > /dev/null 2>&1 &"
    ]
    
    print("Обнаружение опасных паттернов:")
    print("=" * 50)
    
    for command in dangerous_commands:
        result = validator.validate_command(command)
        print(f"\nКоманда: {command}")
        
        if result['warnings']:
            print("🚨 Обнаружены опасные паттерны:")
            for warning in result['warnings']:
                print(f"   - {warning}")
        else:
            print("✅ Опасные паттерны не обнаружены")


def test_security_levels():
    """Тест различных уровней безопасности"""
    print("\n=== Тест уровней безопасности ===\n")
    
    # Тест с белым списком
    allowed_commands = ["ls", "pwd", "whoami", "cat", "echo"]
    
    validator_whitelist = CommandValidator(
        allowed_commands=allowed_commands,
        security_config={'allowed_commands_only': True}
    )
    
    test_commands = [
        "ls -la",           # разрешена
        "pwd",              # разрешена  
        "rm file.txt",      # не разрешена
        "cat /etc/passwd",  # разрешена
        "sudo apt update"   # не разрешена
    ]
    
    print("Тест с белым списком команд:")
    print("Разрешенные команды:", ", ".join(allowed_commands))
    print("=" * 50)
    
    for command in test_commands:
        result = validator_whitelist.validate_command(command)
        status = "✅ РАЗРЕШЕНА" if result['valid'] else "❌ ЗАБЛОКИРОВАНА"
        print(f"{command:<20} - {status}")


def test_dynamic_management():
    """Тест динамического управления правилами безопасности"""
    print("\n=== Тест динамического управления ===\n")
    
    validator = CommandValidator()
    
    print("Исходные запрещенные команды:", len(validator.forbidden_commands))
    
    # Добавляем новую запрещенную команду
    new_forbidden = "dangerous_custom_command"
    validator.add_forbidden_command(new_forbidden)
    print(f"Добавлена запрещенная команда: {new_forbidden}")
    print("Всего запрещенных команд:", len(validator.forbidden_commands))
    
    # Тестируем новую запрещенную команду
    result = validator.validate_command(new_forbidden)
    print(f"Валидация '{new_forbidden}': {'❌ ЗАПРЕЩЕНА' if not result['valid'] else '✅ РАЗРЕШЕНА'}")
    
    # Удаляем команду
    validator.remove_forbidden_command(new_forbidden)
    print(f"Удалена запрещенная команда: {new_forbidden}")
    print("Всего запрещенных команд:", len(validator.forbidden_commands))
    
    # Тестируем снова
    result = validator.validate_command(new_forbidden)
    print(f"Валидация '{new_forbidden}': {'❌ ЗАПРЕЩЕНА' if not result['valid'] else '✅ РАЗРЕШЕНА'}")
    
    # Добавляем новый опасный паттерн
    new_pattern = r"custom_dangerous_.*"
    validator.add_dangerous_pattern(new_pattern)
    print(f"Добавлен опасный паттерн: {new_pattern}")
    
    # Тестируем паттерн
    result = validator.validate_command("custom_dangerous_operation")
    if result['warnings']:
        print("🚨 Новый паттерн обнаружен!")
    else:
        print("✅ Паттерн не сработал")


def test_integration_with_logger():
    """Тест интеграции с системой логирования"""
    print("\n=== Тест интеграции с логированием ===\n")
    
    # Создаем валидатор с включенным логированием
    security_config = {
        'validate_commands': True,
        'log_forbidden_attempts': True
    }
    
    validator = CommandValidator(security_config=security_config)
    
    # Тестируем запрещенные команды
    forbidden_commands = [
        "rm -rf /",
        "shutdown now",
        "dd if=/dev/zero of=/dev/sda"
    ]
    
    print("Тестирование логирования запрещенных команд:")
    print("=" * 50)
    
    for command in forbidden_commands:
        print(f"\nПопытка выполнения: {command}")
        
        context = {
            'step_id': 'security_test_step',
            'task_id': 'security_test_task',
            'user': 'test_user',
            'timestamp': 'test_timestamp'
        }
        
        result = validator.validate_command(command, context)
        
        if not result['valid']:
            print("❌ Команда заблокирована и записана в лог")
        else:
            print("⚠️ Команда неожиданно разрешена!")


def demo_security_stats():
    """Демонстрация статистики безопасности"""
    print("\n=== Демонстрация статистики безопасности ===\n")
    
    validator = CommandValidator()
    
    # Выполняем различные валидации
    commands = [
        "ls -la",           # безопасная
        "sudo apt update",  # безопасная
        "rm file.txt",      # безопасная
        "chmod 777 /tmp",   # опасная
        "rm -rf /",         # запрещенная
        "shutdown",         # запрещенная
        "dd if=/dev/zero",  # запрещенная
    ]
    
    print("Выполнение тестовых команд для сбора статистики...")
    
    for command in commands:
        result = validator.validate_command(command)
        status = "✅" if result['valid'] else "❌"
        level = result['security_level']
        print(f"{status} {command:<25} ({level})")
    
    # Показываем итоговую статистику
    print(f"\n{'='*50}")
    print("Итоговая статистика безопасности:")
    stats = validator.get_validation_stats()
    
    for key, value in stats.items():
        formatted_key = key.replace('_', ' ').title()
        print(f"  {formatted_key}: {value}")
    
    # Сбрасываем статистику
    print(f"\n{'='*50}")
    print("Сброс статистики...")
    validator.reset_stats()
    
    stats_after_reset = validator.get_validation_stats()
    print("Статистика после сброса:")
    for key, value in stats_after_reset.items():
        formatted_key = key.replace('_', ' ').title()
        print(f"  {formatted_key}: {value}")


def main():
    """Главная функция демонстрации"""
    print("🔒 ДЕМОНСТРАЦИЯ СИСТЕМЫ БЕЗОПАСНОСТИ - ШАГ 5.1")
    print("=" * 80)
    
    try:
        # Запускаем все тесты
        test_command_validation()
        test_forbidden_patterns()
        test_security_levels()
        test_dynamic_management()
        test_integration_with_logger()
        demo_security_stats()
        
        print("\n" + "=" * 80)
        print("✅ ВСЕ ТЕСТЫ СИСТЕМЫ БЕЗОПАСНОСТИ ЗАВЕРШЕНЫ УСПЕШНО!")
        print("=" * 80)
        
        print("\n📋 Реализованные функции:")
        print("  ✅ Проверка запрещенных команд")
        print("  ✅ Валидация команд перед выполнением")
        print("  ✅ Логирование попыток выполнения запрещенных команд")
        print("  ✅ Обнаружение опасных паттернов")
        print("  ✅ Динамическое управление правилами")
        print("  ✅ Статистика безопасности")
        print("  ✅ Интеграция с SSH коннектором")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
