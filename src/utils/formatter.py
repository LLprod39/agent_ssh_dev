"""
Утилиты для форматирования данных
"""
import json
import yaml
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path


class OutputFormatter:
    """Форматтер для вывода данных"""
    
    @staticmethod
    def format_json(data: Any, indent: int = 2, ensure_ascii: bool = False) -> str:
        """
        Форматирование данных в JSON
        
        Args:
            data: Данные для форматирования
            indent: Отступ для форматирования
            ensure_ascii: Использовать ли только ASCII символы
            
        Returns:
            Отформатированная JSON строка
        """
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=str)
    
    @staticmethod
    def format_yaml(data: Any, indent: int = 2) -> str:
        """
        Форматирование данных в YAML
        
        Args:
            data: Данные для форматирования
            indent: Отступ для форматирования
            
        Returns:
            Отформатированная YAML строка
        """
        return yaml.dump(data, indent=indent, default_flow_style=False, allow_unicode=True)
    
    @staticmethod
    def format_table(data: List[Dict[str, Any]], headers: Optional[List[str]] = None) -> str:
        """
        Форматирование данных в таблицу
        
        Args:
            data: Список словарей с данными
            headers: Заголовки колонок (если не указаны, берутся из первого элемента)
            
        Returns:
            Отформатированная таблица
        """
        if not data:
            return "Нет данных для отображения"
        
        if headers is None:
            headers = list(data[0].keys())
        
        # Вычисляем ширину колонок
        col_widths = {}
        for header in headers:
            col_widths[header] = len(str(header))
            for row in data:
                if header in row:
                    col_widths[header] = max(col_widths[header], len(str(row[header])))
        
        # Создаем таблицу
        lines = []
        
        # Заголовок
        header_line = " | ".join(str(header).ljust(col_widths[header]) for header in headers)
        lines.append(header_line)
        lines.append("-" * len(header_line))
        
        # Данные
        for row in data:
            data_line = " | ".join(str(row.get(header, "")).ljust(col_widths[header]) for header in headers)
            lines.append(data_line)
        
        return "\n".join(lines)
    
    @staticmethod
    def format_command_result(result: Dict[str, Any]) -> str:
        """
        Форматирование результата выполнения команды
        
        Args:
            result: Результат выполнения команды
            
        Returns:
            Отформатированная строка
        """
        lines = []
        lines.append(f"Команда: {result.get('command', 'N/A')}")
        lines.append(f"Код выхода: {result.get('exit_code', 'N/A')}")
        lines.append(f"Успешно: {'Да' if result.get('success', False) else 'Нет'}")
        
        if result.get('duration'):
            lines.append(f"Время выполнения: {result['duration']:.2f}с")
        
        if result.get('stdout'):
            lines.append(f"Вывод:\n{result['stdout']}")
        
        if result.get('stderr'):
            lines.append(f"Ошибки:\n{result['stderr']}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_task_progress(current_step: int, total_steps: int, step_name: str) -> str:
        """
        Форматирование прогресса выполнения задачи
        
        Args:
            current_step: Текущий шаг
            total_steps: Общее количество шагов
            step_name: Название текущего шага
            
        Returns:
            Отформатированная строка прогресса
        """
        percentage = (current_step / total_steps) * 100 if total_steps > 0 else 0
        progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        
        return f"[{progress_bar}] {percentage:.1f}% - Шаг {current_step}/{total_steps}: {step_name}"


class LogFormatter:
    """Форматтер для логов"""
    
    @staticmethod
    def format_log_entry(level: str, message: str, **kwargs) -> str:
        """
        Форматирование записи лога
        
        Args:
            level: Уровень лога
            message: Сообщение
            **kwargs: Дополнительные параметры
            
        Returns:
            Отформатированная строка лога
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base_entry = f"[{timestamp}] {level.upper()}: {message}"
        
        if kwargs:
            extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            base_entry += f" | {extra_info}"
        
        return base_entry
    
    @staticmethod
    def format_error_report(error_report: Dict[str, Any]) -> str:
        """
        Форматирование отчета об ошибках
        
        Args:
            error_report: Отчет об ошибках
            
        Returns:
            Отформатированная строка отчета
        """
        lines = []
        lines.append("=" * 50)
        lines.append("ОТЧЕТ ОБ ОШИБКАХ")
        lines.append("=" * 50)
        lines.append(f"ID шага: {error_report.get('step_id', 'N/A')}")
        lines.append(f"Количество ошибок: {error_report.get('error_count', 0)}")
        lines.append(f"Время: {error_report.get('timestamp', 'N/A')}")
        
        if error_report.get('commands_executed'):
            lines.append("\nВыполненные команды:")
            for i, cmd in enumerate(error_report['commands_executed'], 1):
                lines.append(f"  {i}. {cmd}")
        
        if error_report.get('error_details'):
            lines.append("\nДетали ошибок:")
            for i, error in enumerate(error_report['error_details'], 1):
                lines.append(f"  {i}. Команда: {error.get('command', 'N/A')}")
                lines.append(f"     Код выхода: {error.get('exit_code', 'N/A')}")
                if error.get('stderr'):
                    lines.append(f"     Ошибка: {error['stderr']}")
        
        if error_report.get('suggestions'):
            lines.append("\nПредложения по исправлению:")
            for i, suggestion in enumerate(error_report['suggestions'], 1):
                lines.append(f"  {i}. {suggestion}")
        
        lines.append("=" * 50)
        return "\n".join(lines)


class ConfigFormatter:
    """Форматтер для конфигурации"""
    
    @staticmethod
    def format_config_summary(config: Dict[str, Any]) -> str:
        """
        Форматирование краткого описания конфигурации
        
        Args:
            config: Конфигурация
            
        Returns:
            Отформатированная строка
        """
        lines = []
        lines.append("КОНФИГУРАЦИЯ СИСТЕМЫ")
        lines.append("=" * 30)
        
        # Информация о сервере
        if 'server' in config:
            server = config['server']
            lines.append(f"Сервер: {server.get('host', 'N/A')}:{server.get('port', 22)}")
            lines.append(f"Пользователь: {server.get('username', 'N/A')}")
            lines.append(f"ОС: {server.get('os_type', 'N/A')}")
            lines.append(f"Метод аутентификации: {server.get('auth_method', 'N/A')}")
        
        # Информация о LLM
        if 'llm' in config:
            llm = config['llm']
            lines.append(f"LLM модель: {llm.get('model', 'N/A')}")
            lines.append(f"API URL: {llm.get('base_url', 'N/A')}")
        
        # Информация об агентах
        if 'agents' in config:
            agents = config['agents']
            lines.append(f"Task Master: {'Включен' if agents.get('taskmaster', {}).get('enabled', False) else 'Отключен'}")
            lines.append(f"Автокоррекция: {'Включена' if agents.get('executor', {}).get('auto_correction_enabled', False) else 'Отключена'}")
            lines.append(f"Dry-run режим: {'Включен' if agents.get('executor', {}).get('dry_run_mode', False) else 'Отключен'}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_validation_errors(errors: List[str]) -> str:
        """
        Форматирование ошибок валидации
        
        Args:
            errors: Список ошибок
            
        Returns:
            Отформатированная строка
        """
        if not errors:
            return "Валидация прошла успешно"
        
        lines = []
        lines.append("ОШИБКИ ВАЛИДАЦИИ")
        lines.append("=" * 20)
        
        for i, error in enumerate(errors, 1):
            lines.append(f"{i}. {error}")
        
        return "\n".join(lines)


class FileFormatter:
    """Форматтер для файлов"""
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Форматирование размера файла
        
        Args:
            size_bytes: Размер в байтах
            
        Returns:
            Отформатированная строка размера
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.1f} GB"
    
    @staticmethod
    def format_file_info(file_path: Union[str, Path]) -> str:
        """
        Форматирование информации о файле
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Отформатированная строка с информацией о файле
        """
        path = Path(file_path)
        
        if not path.exists():
            return f"Файл не существует: {path}"
        
        stat = path.stat()
        size = FileFormatter.format_file_size(stat.st_size)
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        return f"Файл: {path.name}\nРазмер: {size}\nИзменен: {modified}\nПуть: {path.absolute()}"


class TimeFormatter:
    """Форматтер для времени"""
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Форматирование длительности
        
        Args:
            seconds: Длительность в секундах
            
        Returns:
            Отформатированная строка длительности
        """
        if seconds < 60:
            return f"{seconds:.2f}с"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}м {secs:.1f}с"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}ч {minutes}м {secs:.1f}с"
    
    @staticmethod
    def format_timestamp(timestamp: Union[datetime, float, int]) -> str:
        """
        Форматирование временной метки
        
        Args:
            timestamp: Временная метка
            
        Returns:
            Отформатированная строка времени
        """
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
        else:
            dt = timestamp
        
        return dt.strftime("%Y-%m-%d %H:%M:%S")

