"""
Тесты для Formatter
"""
import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from src.utils.formatter import (
    OutputFormatter, LogFormatter, ConfigFormatter, FileFormatter, TimeFormatter
)


class TestOutputFormatter:
    """Тесты для OutputFormatter"""
    
    def test_format_json_simple(self):
        """Тест форматирования простого JSON"""
        data = {"key": "value", "number": 123}
        result = OutputFormatter.format_json(data)
        
        assert isinstance(result, str)
        assert '"key": "value"' in result
        assert '"number": 123' in result
    
    def test_format_json_with_indent(self):
        """Тест форматирования JSON с отступом"""
        data = {"key": "value", "nested": {"inner": "data"}}
        result = OutputFormatter.format_json(data, indent=4)
        
        assert "    " in result  # Проверяем наличие отступов
        assert '"key": "value"' in result
    
    def test_format_json_with_ascii(self):
        """Тест форматирования JSON с ASCII"""
        data = {"русский": "текст", "unicode": "символы"}
        result = OutputFormatter.format_json(data, ensure_ascii=True)
        
        assert "\\u" in result  # Unicode символы должны быть экранированы
    
    def test_format_json_with_datetime(self):
        """Тест форматирования JSON с datetime"""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        data = {"timestamp": dt}
        result = OutputFormatter.format_json(data)
        
        assert "2023-01-01 12:00:00" in result
    
    def test_format_yaml_simple(self):
        """Тест форматирования простого YAML"""
        data = {"key": "value", "number": 123}
        result = OutputFormatter.format_yaml(data)
        
        assert isinstance(result, str)
        assert "key: value" in result
        assert "number: 123" in result
    
    def test_format_yaml_with_indent(self):
        """Тест форматирования YAML с отступом"""
        data = {"key": "value", "nested": {"inner": "data"}}
        result = OutputFormatter.format_yaml(data, indent=4)
        
        assert "    " in result  # Проверяем наличие отступов
    
    def test_format_table_empty_data(self):
        """Тест форматирования пустой таблицы"""
        result = OutputFormatter.format_table([])
        assert result == "Нет данных для отображения"
    
    def test_format_table_with_headers(self):
        """Тест форматирования таблицы с заголовками"""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]
        headers = ["name", "age"]
        result = OutputFormatter.format_table(data, headers)
        
        assert "name" in result
        assert "age" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "30" in result
        assert "25" in result
        assert "|" in result  # Проверяем наличие разделителей
    
    def test_format_table_without_headers(self):
        """Тест форматирования таблицы без заголовков"""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]
        result = OutputFormatter.format_table(data)
        
        assert "name" in result
        assert "age" in result
        assert "Alice" in result
        assert "Bob" in result
    
    def test_format_command_result_success(self):
        """Тест форматирования успешного результата команды"""
        result = {
            "command": "ls -la",
            "exit_code": 0,
            "success": True,
            "duration": 1.5,
            "stdout": "file1.txt\nfile2.txt",
            "stderr": ""
        }
        
        formatted = OutputFormatter.format_command_result(result)
        
        assert "Команда: ls -la" in formatted
        assert "Код выхода: 0" in formatted
        assert "Успешно: Да" in formatted
        assert "Время выполнения: 1.50с" in formatted
        assert "Вывод:" in formatted
        assert "file1.txt" in formatted
    
    def test_format_command_result_failure(self):
        """Тест форматирования неудачного результата команды"""
        result = {
            "command": "invalid_command",
            "exit_code": 1,
            "success": False,
            "duration": 0.5,
            "stdout": "",
            "stderr": "command not found"
        }
        
        formatted = OutputFormatter.format_command_result(result)
        
        assert "Команда: invalid_command" in formatted
        assert "Код выхода: 1" in formatted
        assert "Успешно: Нет" in formatted
        assert "Время выполнения: 0.50с" in formatted
        assert "Ошибки:" in formatted
        assert "command not found" in formatted
    
    def test_format_command_result_minimal(self):
        """Тест форматирования минимального результата команды"""
        result = {
            "command": "echo test",
            "exit_code": 0,
            "success": True
        }
        
        formatted = OutputFormatter.format_command_result(result)
        
        assert "Команда: echo test" in formatted
        assert "Код выхода: 0" in formatted
        assert "Успешно: Да" in formatted
        assert "Время выполнения:" not in formatted
        assert "Вывод:" not in formatted
        assert "Ошибки:" not in formatted
    
    def test_format_task_progress(self):
        """Тест форматирования прогресса задачи"""
        result = OutputFormatter.format_task_progress(3, 10, "Установка пакетов")
        
        assert "Шаг 3/10" in result
        assert "Установка пакетов" in result
        assert "30.0%" in result
        assert "█" in result  # Проверяем наличие прогресс-бара
        assert "░" in result
    
    def test_format_task_progress_zero_total(self):
        """Тест форматирования прогресса с нулевым общим количеством"""
        result = OutputFormatter.format_task_progress(0, 0, "Тест")
        
        assert "Шаг 0/0" in result
        assert "0.0%" in result


class TestLogFormatter:
    """Тесты для LogFormatter"""
    
    def test_format_log_entry_simple(self):
        """Тест форматирования простой записи лога"""
        result = LogFormatter.format_log_entry("info", "Test message")
        
        assert "[INFO]: Test message" in result
        assert "2023-" in result or "2024-" in result  # Проверяем наличие даты
    
    def test_format_log_entry_with_kwargs(self):
        """Тест форматирования записи лога с дополнительными параметрами"""
        result = LogFormatter.format_log_entry("error", "Test error", user="admin", code=500)
        
        assert "[ERROR]: Test error" in result
        assert "user=admin" in result
        assert "code=500" in result
    
    def test_format_log_entry_empty_kwargs(self):
        """Тест форматирования записи лога без дополнительных параметров"""
        result = LogFormatter.format_log_entry("debug", "Debug message")
        
        assert "[DEBUG]: Debug message" in result
        assert "|" not in result  # Не должно быть разделителей
    
    def test_format_error_report_complete(self):
        """Тест форматирования полного отчета об ошибках"""
        error_report = {
            "step_id": "step_1",
            "error_count": 2,
            "timestamp": "2023-01-01 12:00:00",
            "commands_executed": ["apt update", "apt install nginx"],
            "error_details": [
                {
                    "command": "apt install nginx",
                    "exit_code": 1,
                    "stderr": "Package not found"
                }
            ],
            "suggestions": ["Проверить репозитории", "Обновить список пакетов"]
        }
        
        result = LogFormatter.format_error_report(error_report)
        
        assert "ОТЧЕТ ОБ ОШИБКАХ" in result
        assert "ID шага: step_1" in result
        assert "Количество ошибок: 2" in result
        assert "Время: 2023-01-01 12:00:00" in result
        assert "Выполненные команды:" in result
        assert "1. apt update" in result
        assert "2. apt install nginx" in result
        assert "Детали ошибок:" in result
        assert "Команда: apt install nginx" in result
        assert "Код выхода: 1" in result
        assert "Ошибка: Package not found" in result
        assert "Предложения по исправлению:" in result
        assert "1. Проверить репозитории" in result
        assert "2. Обновить список пакетов" in result
    
    def test_format_error_report_minimal(self):
        """Тест форматирования минимального отчета об ошибках"""
        error_report = {
            "step_id": "step_1",
            "error_count": 1
        }
        
        result = LogFormatter.format_error_report(error_report)
        
        assert "ОТЧЕТ ОБ ОШИБКАХ" in result
        assert "ID шага: step_1" in result
        assert "Количество ошибок: 1" in result
        assert "Выполненные команды:" not in result
        assert "Детали ошибок:" not in result
        assert "Предложения по исправлению:" not in result


class TestConfigFormatter:
    """Тесты для ConfigFormatter"""
    
    def test_format_config_summary_complete(self):
        """Тест форматирования полного описания конфигурации"""
        config = {
            "server": {
                "host": "example.com",
                "port": 22,
                "username": "admin",
                "os_type": "ubuntu",
                "auth_method": "key"
            },
            "llm": {
                "model": "gpt-4",
                "base_url": "https://api.openai.com/v1"
            },
            "agents": {
                "taskmaster": {"enabled": True},
                "executor": {
                    "auto_correction_enabled": True,
                    "dry_run_mode": False
                }
            }
        }
        
        result = ConfigFormatter.format_config_summary(config)
        
        assert "КОНФИГУРАЦИЯ СИСТЕМЫ" in result
        assert "Сервер: example.com:22" in result
        assert "Пользователь: admin" in result
        assert "ОС: ubuntu" in result
        assert "Метод аутентификации: key" in result
        assert "LLM модель: gpt-4" in result
        assert "API URL: https://api.openai.com/v1" in result
        assert "Task Master: Включен" in result
        assert "Автокоррекция: Включена" in result
        assert "Dry-run режим: Отключен" in result
    
    def test_format_config_summary_partial(self):
        """Тест форматирования частичной конфигурации"""
        config = {
            "server": {
                "host": "localhost"
            }
        }
        
        result = ConfigFormatter.format_config_summary(config)
        
        assert "КОНФИГУРАЦИЯ СИСТЕМЫ" in result
        assert "Сервер: localhost:22" in result  # Порт по умолчанию
        assert "Пользователь: N/A" in result
        assert "ОС: N/A" in result
        assert "LLM модель: N/A" in result
    
    def test_format_config_summary_empty(self):
        """Тест форматирования пустой конфигурации"""
        config = {}
        
        result = ConfigFormatter.format_config_summary(config)
        
        assert "КОНФИГУРАЦИЯ СИСТЕМЫ" in result
        assert "Сервер: N/A:22" in result
        assert "LLM модель: N/A" in result
    
    def test_format_validation_errors_empty(self):
        """Тест форматирования пустого списка ошибок"""
        result = ConfigFormatter.format_validation_errors([])
        assert result == "Валидация прошла успешно"
    
    def test_format_validation_errors_with_errors(self):
        """Тест форматирования списка ошибок"""
        errors = [
            "Отсутствует обязательное поле 'host'",
            "Неверный формат порта",
            "Недоступен API ключ"
        ]
        
        result = ConfigFormatter.format_validation_errors(errors)
        
        assert "ОШИБКИ ВАЛИДАЦИИ" in result
        assert "1. Отсутствует обязательное поле 'host'" in result
        assert "2. Неверный формат порта" in result
        assert "3. Недоступен API ключ" in result


class TestFileFormatter:
    """Тесты для FileFormatter"""
    
    def test_format_file_size_bytes(self):
        """Тест форматирования размера в байтах"""
        assert FileFormatter.format_file_size(512) == "512 B"
        assert FileFormatter.format_file_size(1023) == "1023 B"
    
    def test_format_file_size_kb(self):
        """Тест форматирования размера в килобайтах"""
        assert FileFormatter.format_file_size(1024) == "1.0 KB"
        assert FileFormatter.format_file_size(1536) == "1.5 KB"
        assert FileFormatter.format_file_size(1024 * 1024 - 1) == "1024.0 KB"
    
    def test_format_file_size_mb(self):
        """Тест форматирования размера в мегабайтах"""
        assert FileFormatter.format_file_size(1024 * 1024) == "1.0 MB"
        assert FileFormatter.format_file_size(1024 * 1024 * 1.5) == "1.5 MB"
        assert FileFormatter.format_file_size(1024 * 1024 * 1024 - 1) == "1024.0 MB"
    
    def test_format_file_size_gb(self):
        """Тест форматирования размера в гигабайтах"""
        assert FileFormatter.format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert FileFormatter.format_file_size(1024 * 1024 * 1024 * 2.5) == "2.5 GB"
    
    def test_format_file_info_existing_file(self):
        """Тест форматирования информации о существующем файле"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            
            result = FileFormatter.format_file_info(f.name)
            
            assert "Файл:" in result
            assert f.name.split('/')[-1] in result  # Имя файла
            assert "Размер:" in result
            assert "Изменен:" in result
            assert "Путь:" in result
            assert "test content" not in result  # Содержимое не должно отображаться
            
            os.unlink(f.name)
    
    def test_format_file_info_nonexistent_file(self):
        """Тест форматирования информации о несуществующем файле"""
        result = FileFormatter.format_file_info("nonexistent_file.txt")
        
        assert "Файл не существует: nonexistent_file.txt" in result
    
    def test_format_file_info_path_object(self):
        """Тест форматирования информации о файле с Path объектом"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            f.flush()
            
            path = Path(f.name)
            result = FileFormatter.format_file_info(path)
            
            assert "Файл:" in result
            assert path.name in result
            
            os.unlink(f.name)


class TestTimeFormatter:
    """Тесты для TimeFormatter"""
    
    def test_format_duration_seconds(self):
        """Тест форматирования длительности в секундах"""
        assert TimeFormatter.format_duration(30.5) == "30.50с"
        assert TimeFormatter.format_duration(59.99) == "59.99с"
    
    def test_format_duration_minutes(self):
        """Тест форматирования длительности в минутах"""
        assert TimeFormatter.format_duration(60) == "1м 0.0с"
        assert TimeFormatter.format_duration(90) == "1м 30.0с"
        assert TimeFormatter.format_duration(3599.9) == "59м 59.9с"
    
    def test_format_duration_hours(self):
        """Тест форматирования длительности в часах"""
        assert TimeFormatter.format_duration(3600) == "1ч 0м 0.0с"
        assert TimeFormatter.format_duration(3661) == "1ч 1м 1.0с"
        assert TimeFormatter.format_duration(7200) == "2ч 0м 0.0с"
    
    def test_format_timestamp_datetime(self):
        """Тест форматирования datetime объекта"""
        dt = datetime(2023, 1, 1, 12, 30, 45)
        result = TimeFormatter.format_timestamp(dt)
        
        assert result == "2023-01-01 12:30:45"
    
    def test_format_timestamp_float(self):
        """Тест форматирования float timestamp"""
        timestamp = 1672571445.0  # 2023-01-01 12:30:45
        result = TimeFormatter.format_timestamp(timestamp)
        
        assert result == "2023-01-01 12:30:45"
    
    def test_format_timestamp_int(self):
        """Тест форматирования int timestamp"""
        timestamp = 1672571445  # 2023-01-01 12:30:45
        result = TimeFormatter.format_timestamp(timestamp)
        
        assert result == "2023-01-01 12:30:45"


if __name__ == "__main__":
    pytest.main([__file__])
