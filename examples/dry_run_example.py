#!/usr/bin/env python3
"""
Пример использования Dry-Run системы

Этот пример демонстрирует:
- Предварительный просмотр выполнения команд
- Валидацию планов перед выполнением
- Анализ рисков и потенциальных проблем
- Генерацию отчетов о планируемых изменениях
"""

import sys
import os
import json
from pathlib import Path

# Добавляем путь к модулям проекта
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from src.utils.dry_run_system import DryRunSystem, DryRunResult
from src.utils.logger import StructuredLogger
from src.agents.subtask_agent import Subtask
from src.models.execution_context import ExecutionContext
from src.models.execution_model import ExecutionModel
from src.config.agent_config import AgentConfig
from src.connectors.ssh_connector import SSHConnector


def create_sample_subtask() -> Subtask:
    """Создание примера подзадачи для тестирования"""
    return Subtask(
        subtask_id="install_nginx_example",
        title="Установка и настройка Nginx",
        description="Установка веб-сервера Nginx с базовой конфигурацией",
        commands=[
            "apt update",
            "apt install -y nginx",
            "systemctl start nginx",
            "systemctl enable nginx",
            "ufw allow 'Nginx Full'"
        ],
        health_checks=[
            "systemctl is-active nginx",
            "curl -I http://localhost",
            "nginx -t"
        ],
        rollback_commands=[
            "systemctl stop nginx",
            "systemctl disable nginx",
            "apt remove -y nginx"
        ],
        expected_output="Nginx установлен и запущен",
        timeout=300,
        metadata={
            "category": "web_server",
            "priority": "high"
        }
    )


def create_dangerous_subtask() -> Subtask:
    """Создание подзадачи с опасными командами для демонстрации анализа рисков"""
    return Subtask(
        subtask_id="dangerous_commands_example",
        title="Пример опасных команд",
        description="Подзадача с командами разного уровня риска",
        commands=[
            "apt update",  # Безопасная
            "rm -rf /tmp/test",  # Средний риск
            "chmod 777 /var/www",  # Высокий риск
            "rm -rf /",  # Критический риск
            "systemctl stop nginx"  # Средний риск
        ],
        health_checks=[
            "ls -la /var/www",
            "systemctl status nginx"
        ],
        rollback_commands=[
            "chmod 755 /var/www",
            "systemctl start nginx"
        ],
        expected_output="Демонстрация анализа рисков",
        timeout=60,
        metadata={
            "category": "demo",
            "priority": "low"
        }
    )


def demo_basic_dry_run():
    """Демонстрация базового dry-run режима"""
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ БАЗОВОГО DRY-RUN РЕЖИМА")
    print("=" * 60)
    
    # Создаем систему dry-run
    logger = StructuredLogger("DryRunDemo")
    dry_run_system = DryRunSystem(logger)
    
    # Пример команд для симуляции
    commands = [
        "apt update",
        "apt install -y nginx",
        "systemctl start nginx",
        "systemctl enable nginx",
        "ufw allow 'Nginx Full'"
    ]
    
    print(f"Симуляция выполнения {len(commands)} команд:")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    print()
    
    # Выполняем симуляцию
    context = {
        "task_type": "web_server_setup",
        "server_os": "ubuntu",
        "user": "root"
    }
    
    result = dry_run_system.simulate_execution(commands, context)
    
    # Выводим результаты
    print("РЕЗУЛЬТАТЫ СИМУЛЯЦИИ:")
    print(f"  Успешно: {result.success}")
    print(f"  Команд выполнено: {len(result.simulated_commands)}")
    print(f"  Общий уровень риска: {result.risk_summary.get('overall_risk', 'unknown').upper()}")
    print(f"  Требуется подтверждение: {'Да' if result.risk_summary.get('requires_confirmation', False) else 'Нет'}")
    print()
    
    # Выводим детали команд
    print("ДЕТАЛИ КОМАНД:")
    for i, cmd_result in enumerate(result.simulated_commands, 1):
        status = "✅" if cmd_result.success else "❌"
        risk = cmd_result.metadata.get('risk_level', 'unknown')
        print(f"  {i}. {status} {cmd_result.command}")
        print(f"     Риск: {risk.upper()}, Время: {cmd_result.duration:.1f}с")
        if cmd_result.stdout:
            print(f"     Вывод: {cmd_result.stdout}")
        if cmd_result.stderr:
            print(f"     Ошибка: {cmd_result.stderr}")
        print()
    
    # Выводим рекомендации
    if result.recommendations:
        print("РЕКОМЕНДАЦИИ:")
        for rec in result.recommendations:
            print(f"  • {rec}")
        print()


def demo_risk_analysis():
    """Демонстрация анализа рисков"""
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ АНАЛИЗА РИСКОВ")
    print("=" * 60)
    
    logger = StructuredLogger("RiskAnalysisDemo")
    dry_run_system = DryRunSystem(logger)
    
    # Команды с разными уровнями риска
    dangerous_commands = [
        "apt update",  # Безопасная
        "rm -rf /tmp/test",  # Средний риск
        "chmod 777 /var/www",  # Высокий риск
        "rm -rf /",  # Критический риск
        "systemctl stop nginx"  # Средний риск
    ]
    
    print("Анализ команд с разными уровнями риска:")
    for i, cmd in enumerate(dangerous_commands, 1):
        print(f"  {i}. {cmd}")
    print()
    
    # Выполняем симуляцию
    result = dry_run_system.simulate_execution(dangerous_commands)
    
    # Выводим анализ рисков
    risk_summary = result.risk_summary
    print("АНАЛИЗ РИСКОВ:")
    print(f"  Общий уровень риска: {risk_summary.get('overall_risk', 'unknown').upper()}")
    print(f"  Процент риска: {risk_summary.get('risk_percentage', 0):.1f}%")
    print(f"  Требуется подтверждение: {'Да' if risk_summary.get('requires_confirmation', False) else 'Нет'}")
    print()
    
    # Детализация по уровням риска
    risk_breakdown = risk_summary.get('risk_breakdown', {})
    print("РАСПРЕДЕЛЕНИЕ РИСКОВ:")
    for level, count in risk_breakdown.items():
        if count > 0:
            print(f"  {level.upper()}: {count} команд")
    print()
    
    # Выводим валидацию плана
    if result.validation_result:
        validation = result.validation_result
        print("ВАЛИДАЦИЯ ПЛАНА:")
        print(f"  План валиден: {'Да' if validation.valid else 'Нет'}")
        
        if validation.issues:
            print("  ПРОБЛЕМЫ:")
            for issue in validation.issues:
                print(f"    ❌ {issue}")
        
        if validation.warnings:
            print("  ПРЕДУПРЕЖДЕНИЯ:")
            for warning in validation.warnings:
                print(f"    ⚠️  {warning}")
        print()


def demo_report_generation():
    """Демонстрация генерации отчетов"""
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ ГЕНЕРАЦИИ ОТЧЕТОВ")
    print("=" * 60)
    
    logger = StructuredLogger("ReportDemo")
    dry_run_system = DryRunSystem(logger)
    
    # Команды для отчета
    commands = [
        "apt update",
        "apt install -y nginx",
        "systemctl start nginx",
        "systemctl enable nginx"
    ]
    
    # Выполняем симуляцию
    result = dry_run_system.simulate_execution(commands)
    
    # Генерируем отчеты в разных форматах
    print("Генерация отчетов в разных форматах...")
    print()
    
    # Текстовый отчет
    print("ТЕКСТОВЫЙ ОТЧЕТ:")
    print("-" * 40)
    text_report = dry_run_system.generate_dry_run_report(result, "text")
    print(text_report[:500] + "..." if len(text_report) > 500 else text_report)
    print()
    
    # JSON отчет
    print("JSON ОТЧЕТ:")
    print("-" * 40)
    json_report = dry_run_system.generate_dry_run_report(result, "json")
    json_data = json.loads(json_report)
    print(f"Структура JSON отчета:")
    print(f"  - dry_run_result: {list(json_data.get('dry_run_result', {}).keys())}")
    print(f"  - simulated_commands: {len(json_data.get('simulated_commands', []))} команд")
    print()
    
    # Markdown отчет
    print("MARKDOWN ОТЧЕТ:")
    print("-" * 40)
    markdown_report = dry_run_system.generate_dry_run_report(result, "markdown")
    print(markdown_report[:300] + "..." if len(markdown_report) > 300 else markdown_report)
    print()


def demo_execution_model_integration():
    """Демонстрация интеграции с Execution Model"""
    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ ИНТЕГРАЦИИ С EXECUTION MODEL")
    print("=" * 60)
    
    try:
        # Создаем конфигурацию
        config = AgentConfig.from_yaml("config/agent_config.yaml")
        
        # Создаем SSH коннектор (мок)
        ssh_connector = SSHConnector({
            "host": "localhost",
            "port": 22,
            "username": "test",
            "auth_method": "key"
        })
        
        # Создаем Execution Model
        execution_model = ExecutionModel(config, ssh_connector)
        
        # Создаем подзадачу
        subtask = create_sample_subtask()
        
        # Создаем контекст выполнения
        context = ExecutionContext(
            subtask=subtask,
            ssh_connection=ssh_connector,
            server_info={
                "os": "ubuntu",
                "version": "20.04",
                "arch": "x86_64"
            }
        )
        
        print(f"Тестирование подзадачи: {subtask.title}")
        print(f"Команд: {len(subtask.commands)}")
        print()
        
        # Предварительный просмотр
        print("1. ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР:")
        preview_result = execution_model.preview_execution(context)
        print(f"   Успешно: {preview_result.success}")
        print(f"   Риск: {preview_result.risk_summary.get('overall_risk', 'unknown').upper()}")
        print()
        
        # Валидация плана
        print("2. ВАЛИДАЦИЯ ПЛАНА:")
        validation_result = execution_model.validate_plan(context)
        print(f"   Валиден: {validation_result['valid']}")
        print(f"   Проблем: {len(validation_result['issues'])}")
        print(f"   Предупреждений: {len(validation_result['warnings'])}")
        print()
        
        # Краткая сводка
        print("3. КРАТКАЯ СВОДКА:")
        summary = execution_model.get_dry_run_summary(context)
        print(f"   ID: {summary['subtask_id']}")
        print(f"   Название: {summary['subtask_title']}")
        print(f"   Оценочное время: {summary['estimated_duration']:.1f}с")
        print(f"   Требуется подтверждение: {summary['requires_confirmation']}")
        print()
        
        # Генерация отчета
        print("4. ГЕНЕРАЦИЯ ОТЧЕТА:")
        report = execution_model.generate_execution_report(context, "text")
        print(f"   Длина отчета: {len(report)} символов")
        print("   Первые строки отчета:")
        for line in report.split('\n')[:5]:
            print(f"     {line}")
        print()
        
    except Exception as e:
        print(f"Ошибка при демонстрации интеграции: {e}")
        print("Убедитесь, что файл конфигурации существует и корректно настроен")


def main():
    """Главная функция демонстрации"""
    print("ДЕМОНСТРАЦИЯ DRY-RUN СИСТЕМЫ")
    print("=" * 60)
    print()
    
    try:
        # Демонстрация базового dry-run
        demo_basic_dry_run()
        
        # Демонстрация анализа рисков
        demo_risk_analysis()
        
        # Демонстрация генерации отчетов
        demo_report_generation()
        
        # Демонстрация интеграции с Execution Model
        demo_execution_model_integration()
        
        print("=" * 60)
        print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 60)
        
    except Exception as e:
        print(f"Ошибка при выполнении демонстрации: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
