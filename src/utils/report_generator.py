"""
Генератор детальных отчетов о выполнении задач

Этот модуль отвечает за:
- Создание детальных отчетов о выполнении задач
- Форматирование отчетов в различных форматах
- Анализ производительности и статистики
- Экспорт отчетов в файлы
"""
import json
import csv
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time

from ..utils.logger import StructuredLogger
from ..models.planning_model import Task, TaskStep, TaskStatus, StepStatus


class ReportFormat(Enum):
    """Формат отчета"""
    JSON = "json"
    HTML = "html"
    CSV = "csv"
    TEXT = "text"
    MARKDOWN = "markdown"


class ReportType(Enum):
    """Тип отчета"""
    TASK_SUMMARY = "task_summary"
    STEP_DETAILS = "step_details"
    ERROR_ANALYSIS = "error_analysis"
    PERFORMANCE = "performance"
    TIMELINE = "timeline"
    FULL_REPORT = "full_report"


@dataclass
class ReportSection:
    """Секция отчета"""
    
    section_id: str
    title: str
    content: str
    order: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetailedReport:
    """Детальный отчет"""
    
    report_id: str
    report_type: ReportType
    task_id: str
    title: str
    created_at: datetime
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "task_id": self.task_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "sections": [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "content": section.content,
                    "order": section.order,
                    "metadata": section.metadata
                }
                for section in sorted(self.sections, key=lambda x: x.order)
            ],
            "metadata": self.metadata,
            "file_path": self.file_path
        }


class ReportGenerator:
    """
    Генератор детальных отчетов
    
    Основные возможности:
    - Создание отчетов различных типов
    - Экспорт в различные форматы
    - Анализ производительности
    - Создание временной шкалы выполнения
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация генератора отчетов
        
        Args:
            config: Конфигурация генератора отчетов
        """
        self.config = config
        self.logger = StructuredLogger("ReportGenerator")
        
        # Настройки экспорта
        self.export_config = {
            "output_dir": config.get("output_dir", "reports"),
            "formats": config.get("formats", ["json", "html"]),
            "include_timeline": config.get("include_timeline", True),
            "include_performance": config.get("include_performance", True),
            "include_error_analysis": config.get("include_error_analysis", True)
        }
        
        # Создаем директорию для отчетов
        Path(self.export_config["output_dir"]).mkdir(parents=True, exist_ok=True)
        
        # Хранилище отчетов
        self.reports: Dict[str, DetailedReport] = {}
        
        self.logger.info(
            "Генератор отчетов инициализирован",
            output_dir=self.export_config["output_dir"],
            formats=self.export_config["formats"]
        )
    
    def generate_task_summary_report(self, task: Task, execution_results: Dict[str, Any]) -> DetailedReport:
        """Генерация сводного отчета по задаче"""
        report_id = f"task_summary_{task.task_id}_{int(time.time() * 1000)}"
        
        report = DetailedReport(
            report_id=report_id,
            report_type=ReportType.TASK_SUMMARY,
            task_id=task.task_id,
            title=f"Сводный отчет по задаче: {task.title}",
            created_at=datetime.now(),
            metadata={
                "task_status": task.status.value,
                "total_steps": len(task.steps),
                "execution_duration": task.get_duration()
            }
        )
        
        # Основная информация о задаче
        report.sections.append(ReportSection(
            section_id="task_overview",
            title="Обзор задачи",
            content=self._generate_task_overview(task),
            order=1
        ))
        
        # Статистика выполнения
        report.sections.append(ReportSection(
            section_id="execution_stats",
            title="Статистика выполнения",
            content=self._generate_execution_stats(task, execution_results),
            order=2
        ))
        
        # Сводка по шагам
        report.sections.append(ReportSection(
            section_id="steps_summary",
            title="Сводка по шагам",
            content=self._generate_steps_summary(task),
            order=3
        ))
        
        # Анализ ошибок
        if self.export_config["include_error_analysis"]:
            report.sections.append(ReportSection(
                section_id="error_analysis",
                title="Анализ ошибок",
                content=self._generate_error_analysis(task, execution_results),
                order=4
            ))
        
        # Рекомендации
        report.sections.append(ReportSection(
            section_id="recommendations",
            title="Рекомендации",
            content=self._generate_recommendations(task, execution_results),
            order=5
        ))
        
        # Сохраняем отчет
        self.reports[report_id] = report
        
        self.logger.info(
            "Сводный отчет по задаче создан",
            report_id=report_id,
            task_id=task.task_id,
            sections_count=len(report.sections)
        )
        
        return report
    
    def generate_step_details_report(self, task: Task, step_id: str, step_results: List[Dict[str, Any]]) -> DetailedReport:
        """Генерация детального отчета по шагу"""
        step = task.get_step(step_id)
        if not step:
            raise ValueError(f"Шаг {step_id} не найден в задаче {task.task_id}")
        
        report_id = f"step_details_{step_id}_{int(time.time() * 1000)}"
        
        report = DetailedReport(
            report_id=report_id,
            report_type=ReportType.STEP_DETAILS,
            task_id=task.task_id,
            title=f"Детальный отчет по шагу: {step.title}",
            created_at=datetime.now(),
            metadata={
                "step_id": step_id,
                "step_status": step.status.value,
                "error_count": step.error_count,
                "execution_attempts": len(step_results)
            }
        )
        
        # Информация о шаге
        report.sections.append(ReportSection(
            section_id="step_overview",
            title="Обзор шага",
            content=self._generate_step_overview(step),
            order=1
        ))
        
        # Детали выполнения
        report.sections.append(ReportSection(
            section_id="execution_details",
            title="Детали выполнения",
            content=self._generate_step_execution_details(step_results),
            order=2
        ))
        
        # Анализ ошибок шага
        if step.error_count > 0:
            report.sections.append(ReportSection(
                section_id="step_error_analysis",
                title="Анализ ошибок шага",
                content=self._generate_step_error_analysis(step, step_results),
                order=3
            ))
        
        # Рекомендации по шагу
        report.sections.append(ReportSection(
            section_id="step_recommendations",
            title="Рекомендации по шагу",
            content=self._generate_step_recommendations(step, step_results),
            order=4
        ))
        
        # Сохраняем отчет
        self.reports[report_id] = report
        
        self.logger.info(
            "Детальный отчет по шагу создан",
            report_id=report_id,
            step_id=step_id,
            sections_count=len(report.sections)
        )
        
        return report
    
    def generate_timeline_report(self, task: Task, execution_timeline: List[Dict[str, Any]]) -> DetailedReport:
        """Генерация отчета временной шкалы"""
        report_id = f"timeline_{task.task_id}_{int(time.time() * 1000)}"
        
        report = DetailedReport(
            report_id=report_id,
            report_type=ReportType.TIMELINE,
            task_id=task.task_id,
            title=f"Временная шкала выполнения: {task.title}",
            created_at=datetime.now(),
            metadata={
                "timeline_events": len(execution_timeline),
                "task_duration": task.get_duration()
            }
        )
        
        # Временная шкала
        report.sections.append(ReportSection(
            section_id="timeline",
            title="Временная шкала выполнения",
            content=self._generate_timeline_content(execution_timeline),
            order=1
        ))
        
        # Анализ временных интервалов
        report.sections.append(ReportSection(
            section_id="time_analysis",
            title="Анализ временных интервалов",
            content=self._generate_time_analysis(execution_timeline),
            order=2
        ))
        
        # Сохраняем отчет
        self.reports[report_id] = report
        
        self.logger.info(
            "Отчет временной шкалы создан",
            report_id=report_id,
            task_id=task.task_id,
            events_count=len(execution_timeline)
        )
        
        return report
    
    def generate_performance_report(self, task: Task, performance_metrics: Dict[str, Any]) -> DetailedReport:
        """Генерация отчета производительности"""
        report_id = f"performance_{task.task_id}_{int(time.time() * 1000)}"
        
        report = DetailedReport(
            report_id=report_id,
            report_type=ReportType.PERFORMANCE,
            task_id=task.task_id,
            title=f"Отчет производительности: {task.title}",
            created_at=datetime.now(),
            metadata=performance_metrics
        )
        
        # Общие метрики производительности
        report.sections.append(ReportSection(
            section_id="performance_overview",
            title="Обзор производительности",
            content=self._generate_performance_overview(performance_metrics),
            order=1
        ))
        
        # Детальные метрики
        report.sections.append(ReportSection(
            section_id="detailed_metrics",
            title="Детальные метрики",
            content=self._generate_detailed_metrics(performance_metrics),
            order=2
        ))
        
        # Рекомендации по оптимизации
        report.sections.append(ReportSection(
            section_id="optimization_recommendations",
            title="Рекомендации по оптимизации",
            content=self._generate_optimization_recommendations(performance_metrics),
            order=3
        ))
        
        # Сохраняем отчет
        self.reports[report_id] = report
        
        self.logger.info(
            "Отчет производительности создан",
            report_id=report_id,
            task_id=task.task_id
        )
        
        return report
    
    def export_report(self, report: DetailedReport, formats: Optional[List[ReportFormat]] = None) -> Dict[str, str]:
        """Экспорт отчета в различные форматы"""
        if formats is None:
            formats = [ReportFormat(fmt) for fmt in self.export_config["formats"]]
        
        exported_files = {}
        
        for format_type in formats:
            try:
                file_path = self._export_to_format(report, format_type)
                exported_files[format_type.value] = file_path
                
                self.logger.info(
                    "Отчет экспортирован",
                    report_id=report.report_id,
                    format=format_type.value,
                    file_path=file_path
                )
                
            except Exception as e:
                self.logger.error(
                    f"Ошибка экспорта в {format_type.value}",
                    error=str(e),
                    report_id=report.report_id
                )
        
        return exported_files
    
    def _generate_task_overview(self, task: Task) -> str:
        """Генерация обзора задачи"""
        progress = task.get_progress()
        
        return f"""
# Обзор задачи

**ID задачи:** {task.task_id}
**Название:** {task.title}
**Описание:** {task.description}
**Статус:** {task.status.value}
**Приоритет:** {task.priority.value}

## Прогресс выполнения
- Всего шагов: {progress['total_steps']}
- Выполнено: {progress['completed_steps']}
- Провалено: {progress['failed_steps']}
- Ожидает: {progress['pending_steps']}
- Прогресс: {progress['progress_percentage']:.1f}%

## Временные рамки
- Создана: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Начата: {task.started_at.strftime('%Y-%m-%d %H:%M:%S') if task.started_at else 'Не начата'}
- Завершена: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else 'Не завершена'}
- Длительность: {task.get_duration():.2f} минут" if task.get_duration() else 'Не завершена'
"""
    
    def _generate_execution_stats(self, task: Task, execution_results: Dict[str, Any]) -> str:
        """Генерация статистики выполнения"""
        total_errors = sum(step.error_count for step in task.steps)
        total_attempts = sum(len(step.subtasks) for step in task.steps)
        
        return f"""
# Статистика выполнения

## Общие показатели
- Общее время выполнения: {task.get_duration():.2f} минут" if task.get_duration() else 'Не завершено'
- Общее количество ошибок: {total_errors}
- Общее количество попыток: {total_attempts}
- Успешность: {((total_attempts - total_errors) / total_attempts * 100):.1f}%" if total_attempts > 0 else 'Нет данных'

## Статистика по шагам
- Шагов с ошибками: {len([step for step in task.steps if step.error_count > 0])}
- Шагов без ошибок: {len([step for step in task.steps if step.error_count == 0])}
- Среднее количество ошибок на шаг: {total_errors / len(task.steps):.2f}" if task.steps else '0'

## Результаты выполнения
- Успешных команд: {execution_results.get('successful_commands', 0)}
- Проваленных команд: {execution_results.get('failed_commands', 0)}
- Применено автокоррекций: {execution_results.get('autocorrections_applied', 0)}
"""
    
    def _generate_steps_summary(self, task: Task) -> str:
        """Генерация сводки по шагам"""
        content = "# Сводка по шагам\n\n"
        
        for i, step in enumerate(task.steps, 1):
            duration = step.get_duration()
            duration_str = f"{duration:.2f} мин" if duration else "Не завершен"
            
            content += f"""
## Шаг {i}: {step.title}

- **ID:** {step.step_id}
- **Статус:** {step.status.value}
- **Приоритет:** {step.priority.value}
- **Ошибок:** {step.error_count}
- **Длительность:** {duration_str}
- **Описание:** {step.description}

"""
        
        return content
    
    def _generate_error_analysis(self, task: Task, execution_results: Dict[str, Any]) -> str:
        """Генерация анализа ошибок"""
        failed_steps = [step for step in task.steps if step.error_count > 0]
        
        if not failed_steps:
            return "# Анализ ошибок\n\nОшибок не обнаружено.\n"
        
        content = "# Анализ ошибок\n\n"
        
        # Общая статистика ошибок
        total_errors = sum(step.error_count for step in failed_steps)
        content += f"## Общая статистика\n- Шагов с ошибками: {len(failed_steps)}\n- Общее количество ошибок: {total_errors}\n\n"
        
        # Детали по каждому шагу с ошибками
        content += "## Детали ошибок по шагам\n\n"
        for step in failed_steps:
            content += f"### {step.title}\n- Количество ошибок: {step.error_count}\n- Статус: {step.status.value}\n\n"
        
        return content
    
    def _generate_recommendations(self, task: Task, execution_results: Dict[str, Any]) -> str:
        """Генерация рекомендаций"""
        recommendations = []
        
        # Анализируем ошибки
        failed_steps = [step for step in task.steps if step.error_count > 0]
        if failed_steps:
            recommendations.append("• Рассмотрите возможность разбиения шагов с ошибками на более мелкие подзадачи")
            recommendations.append("• Добавьте дополнительные проверки перед выполнением команд")
        
        # Анализируем производительность
        if task.get_duration() and task.get_duration() > 60:  # Более часа
            recommendations.append("• Рассмотрите возможность оптимизации команд для ускорения выполнения")
        
        # Анализируем автокоррекцию
        autocorrections = execution_results.get('autocorrections_applied', 0)
        if autocorrections > 0:
            recommendations.append(f"• Применено {autocorrections} автокоррекций - рассмотрите улучшение планирования команд")
        
        if not recommendations:
            recommendations.append("• Задача выполнена успешно, особых рекомендаций нет")
        
        content = "# Рекомендации\n\n"
        for rec in recommendations:
            content += f"{rec}\n"
        
        return content
    
    def _generate_step_overview(self, step: TaskStep) -> str:
        """Генерация обзора шага"""
        duration = step.get_duration()
        duration_str = f"{duration:.2f} мин" if duration else "Не завершен"
        
        return f"""
# Обзор шага

**ID шага:** {step.step_id}
**Название:** {step.title}
**Описание:** {step.description}
**Статус:** {step.status.value}
**Приоритет:** {step.priority.value}
**Количество ошибок:** {step.error_count}
**Длительность:** {duration_str}

## Временные рамки
- Создан: {step.created_at.strftime('%Y-%m-%d %H:%M:%S')}
- Начат: {step.started_at.strftime('%Y-%m-%d %H:%M:%S') if step.started_at else 'Не начат'}
- Завершен: {step.completed_at.strftime('%Y-%m-%d %H:%M:%S') if step.completed_at else 'Не завершен'}

## Подзадачи
- Количество подзадач: {len(step.subtasks)}
"""
    
    def _generate_step_execution_details(self, step_results: List[Dict[str, Any]]) -> str:
        """Генерация деталей выполнения шага"""
        content = "# Детали выполнения\n\n"
        
        for i, result in enumerate(step_results, 1):
            content += f"""
## Попытка {i}

- **Команда:** {result.get('command', 'Не указана')}
- **Успех:** {'Да' if result.get('success', False) else 'Нет'}
- **Код выхода:** {result.get('exit_code', 'Не указан')}
- **Длительность:** {result.get('duration', 0):.2f} сек
- **Автокоррекция:** {'Да' if result.get('autocorrection_applied', False) else 'Нет'}

### Вывод
```
{result.get('stdout', '')}
```

### Ошибки
```
{result.get('stderr', '')}
```

"""
        
        return content
    
    def _generate_step_error_analysis(self, step: TaskStep, step_results: List[Dict[str, Any]]) -> str:
        """Генерация анализа ошибок шага"""
        content = "# Анализ ошибок шага\n\n"
        
        failed_attempts = [result for result in step_results if not result.get('success', False)]
        
        if not failed_attempts:
            return content + "Ошибок не обнаружено.\n"
        
        content += f"## Общая статистика\n- Количество попыток: {len(step_results)}\n- Провальных попыток: {len(failed_attempts)}\n- Успешность: {((len(step_results) - len(failed_attempts)) / len(step_results) * 100):.1f}%\n\n"
        
        content += "## Анализ ошибок\n\n"
        for i, attempt in enumerate(failed_attempts, 1):
            content += f"### Провальная попытка {i}\n"
            content += f"- **Команда:** {attempt.get('command', 'Не указана')}\n"
            content += f"- **Код выхода:** {attempt.get('exit_code', 'Не указан')}\n"
            content += f"- **Ошибка:** {attempt.get('stderr', 'Не указана')}\n\n"
        
        return content
    
    def _generate_step_recommendations(self, step: TaskStep, step_results: List[Dict[str, Any]]) -> str:
        """Генерация рекомендаций по шагу"""
        recommendations = []
        
        if step.error_count > 0:
            recommendations.append("• Проверьте синтаксис команд и их параметры")
            recommendations.append("• Убедитесь в наличии необходимых прав доступа")
            recommendations.append("• Проверьте доступность требуемых ресурсов")
        
        if len(step_results) > 3:
            recommendations.append("• Рассмотрите разбиение шага на более мелкие подзадачи")
        
        autocorrections = sum(1 for result in step_results if result.get('autocorrection_applied', False))
        if autocorrections > 0:
            recommendations.append(f"• Применено {autocorrections} автокоррекций - улучшите планирование команд")
        
        if not recommendations:
            recommendations.append("• Шаг выполнен успешно, особых рекомендаций нет")
        
        content = "# Рекомендации по шагу\n\n"
        for rec in recommendations:
            content += f"{rec}\n"
        
        return content
    
    def _generate_timeline_content(self, execution_timeline: List[Dict[str, Any]]) -> str:
        """Генерация содержимого временной шкалы"""
        content = "# Временная шкала выполнения\n\n"
        
        for event in execution_timeline:
            timestamp = event.get('timestamp', '')
            event_type = event.get('event_type', '')
            description = event.get('description', '')
            
            content += f"**{timestamp}** - {event_type}: {description}\n\n"
        
        return content
    
    def _generate_time_analysis(self, execution_timeline: List[Dict[str, Any]]) -> str:
        """Генерация анализа временных интервалов"""
        content = "# Анализ временных интервалов\n\n"
        
        # Здесь можно добавить более сложный анализ временных интервалов
        content += "Анализ временных интервалов будет добавлен в следующих версиях.\n"
        
        return content
    
    def _generate_performance_overview(self, performance_metrics: Dict[str, Any]) -> str:
        """Генерация обзора производительности"""
        content = "# Обзор производительности\n\n"
        
        content += f"## Основные метрики\n"
        content += f"- Общее время выполнения: {performance_metrics.get('total_duration', 0):.2f} сек\n"
        content += f"- Среднее время на команду: {performance_metrics.get('avg_command_duration', 0):.2f} сек\n"
        content += f"- Количество команд: {performance_metrics.get('total_commands', 0)}\n"
        content += f"- Успешность команд: {performance_metrics.get('command_success_rate', 0):.1f}%\n\n"
        
        return content
    
    def _generate_detailed_metrics(self, performance_metrics: Dict[str, Any]) -> str:
        """Генерация детальных метрик"""
        content = "# Детальные метрики\n\n"
        
        for metric_name, value in performance_metrics.items():
            content += f"- **{metric_name}:** {value}\n"
        
        return content
    
    def _generate_optimization_recommendations(self, performance_metrics: Dict[str, Any]) -> str:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        avg_duration = performance_metrics.get('avg_command_duration', 0)
        if avg_duration > 10:
            recommendations.append("• Команды выполняются медленно - рассмотрите оптимизацию")
        
        success_rate = performance_metrics.get('command_success_rate', 100)
        if success_rate < 90:
            recommendations.append("• Низкая успешность команд - улучшите планирование")
        
        if not recommendations:
            recommendations.append("• Производительность в норме")
        
        content = "# Рекомендации по оптимизации\n\n"
        for rec in recommendations:
            content += f"{rec}\n"
        
        return content
    
    def _export_to_format(self, report: DetailedReport, format_type: ReportFormat) -> str:
        """Экспорт отчета в указанный формат"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report.report_id}_{timestamp}.{format_type.value}"
        file_path = Path(self.export_config["output_dir"]) / filename
        
        if format_type == ReportFormat.JSON:
            self._export_to_json(report, file_path)
        elif format_type == ReportFormat.HTML:
            self._export_to_html(report, file_path)
        elif format_type == ReportFormat.CSV:
            self._export_to_csv(report, file_path)
        elif format_type == ReportFormat.TEXT:
            self._export_to_text(report, file_path)
        elif format_type == ReportFormat.MARKDOWN:
            self._export_to_markdown(report, file_path)
        
        return str(file_path)
    
    def _export_to_json(self, report: DetailedReport, file_path: Path):
        """Экспорт в JSON"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _export_to_html(self, report: DetailedReport, file_path: Path):
        """Экспорт в HTML"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{report.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 1px solid #ccc; }}
        h3 {{ color: #888; }}
        pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
        .metadata {{ background: #e9e9e9; padding: 10px; border-radius: 5px; margin: 10px 0; }}
    </style>
</head>
<body>
    <h1>{report.title}</h1>
    <div class="metadata">
        <p><strong>ID отчета:</strong> {report.report_id}</p>
        <p><strong>Тип отчета:</strong> {report.report_type.value}</p>
        <p><strong>ID задачи:</strong> {report.task_id}</p>
        <p><strong>Создан:</strong> {report.created_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
"""
        
        for section in sorted(report.sections, key=lambda x: x.order):
            html_content += f"<h2>{section.title}</h2>\n"
            html_content += f"<div>{section.content}</div>\n"
        
        html_content += "</body></html>"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _export_to_csv(self, report: DetailedReport, file_path: Path):
        """Экспорт в CSV"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Section', 'Title', 'Content'])
            
            for section in sorted(report.sections, key=lambda x: x.order):
                writer.writerow([
                    section.section_id,
                    section.title,
                    section.content.replace('\n', ' ').replace('\r', ' ')
                ])
    
    def _export_to_text(self, report: DetailedReport, file_path: Path):
        """Экспорт в текстовый формат"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"{report.title}\n")
            f.write("=" * len(report.title) + "\n\n")
            f.write(f"ID отчета: {report.report_id}\n")
            f.write(f"Тип отчета: {report.report_type.value}\n")
            f.write(f"ID задачи: {report.task_id}\n")
            f.write(f"Создан: {report.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for section in sorted(report.sections, key=lambda x: x.order):
                f.write(f"{section.title}\n")
                f.write("-" * len(section.title) + "\n")
                f.write(f"{section.content}\n\n")
    
    def _export_to_markdown(self, report: DetailedReport, file_path: Path):
        """Экспорт в Markdown"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"# {report.title}\n\n")
            f.write(f"**ID отчета:** {report.report_id}\n")
            f.write(f"**Тип отчета:** {report.report_type.value}\n")
            f.write(f"**ID задачи:** {report.task_id}\n")
            f.write(f"**Создан:** {report.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for section in sorted(report.sections, key=lambda x: x.order):
                f.write(f"## {section.title}\n\n")
                f.write(f"{section.content}\n\n")
    
    def get_report(self, report_id: str) -> Optional[DetailedReport]:
        """Получение отчета по ID"""
        return self.reports.get(report_id)
    
    def get_reports_by_task(self, task_id: str) -> List[DetailedReport]:
        """Получение всех отчетов по задаче"""
        return [report for report in self.reports.values() if report.task_id == task_id]
    
    def get_all_reports(self) -> List[DetailedReport]:
        """Получение всех отчетов"""
        return list(self.reports.values())
    
    def cleanup_old_reports(self, days: int = 30):
        """Очистка старых отчетов"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        old_reports = [
            report_id for report_id, report in self.reports.items()
            if report.created_at < cutoff_time
        ]
        
        for report_id in old_reports:
            del self.reports[report_id]
        
        self.logger.info(
            "Старые отчеты очищены",
            removed_count=len(old_reports),
            retention_days=days
        )
