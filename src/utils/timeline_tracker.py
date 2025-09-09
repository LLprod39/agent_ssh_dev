"""
Система отслеживания временной шкалы выполнения задач

Этот модуль отвечает за:
- Создание детальной временной шкалы выполнения задач
- Отслеживание всех событий и их временных меток
- Анализ производительности и задержек
- Экспорт timeline в различные форматы
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time

from ..utils.logger import StructuredLogger
from ..models.planning_model import Task, TaskStep, TaskStatus, StepStatus


class TimelineEventType(Enum):
    """Тип события временной шкалы"""
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    
    STEP_PLANNED = "step_planned"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    COMMAND_RETRY = "command_retry"
    
    AUTOCORRECTION_APPLIED = "autocorrection_applied"
    ERROR_ESCALATION = "error_escalation"
    HUMAN_ESCALATION = "human_escalation"
    
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"


@dataclass
class TimelineEvent:
    """Событие временной шкалы"""
    
    event_id: str
    event_type: TimelineEventType
    timestamp: datetime
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    title: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None  # Длительность события в секундах
    parent_event_id: Optional[str] = None  # ID родительского события
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "task_id": self.task_id,
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata,
            "duration": self.duration,
            "parent_event_id": self.parent_event_id
        }


@dataclass
class TimelineSegment:
    """Сегмент временной шкалы"""
    
    segment_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]  # в секундах
    event_type: TimelineEventType
    title: str
    description: str
    events: List[TimelineEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "segment_id": self.segment_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "event_type": self.event_type.value,
            "title": self.title,
            "description": self.description,
            "events": [event.to_dict() for event in self.events],
            "metadata": self.metadata
        }


class TimelineTracker:
    """
    Система отслеживания временной шкалы выполнения задач
    
    Основные возможности:
    - Отслеживание всех событий выполнения
    - Создание детальной временной шкалы
    - Анализ производительности и задержек
    - Экспорт timeline в различные форматы
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация трекера временной шкалы
        
        Args:
            config: Конфигурация трекера
        """
        self.config = config
        self.logger = StructuredLogger("TimelineTracker")
        
        # Хранилище событий и сегментов
        self.events: Dict[str, TimelineEvent] = {}
        self.segments: Dict[str, TimelineSegment] = {}
        
        # Активные события (для отслеживания длительности)
        self.active_events: Dict[str, TimelineEvent] = {}
        
        # Настройки
        self.auto_create_segments = config.get("auto_create_segments", True)
        self.max_events_per_task = config.get("max_events_per_task", 1000)
        self.enable_performance_analysis = config.get("enable_performance_analysis", True)
        
        self.logger.info(
            "Трекер временной шкалы инициализирован",
            auto_create_segments=self.auto_create_segments,
            max_events_per_task=self.max_events_per_task
        )
    
    def start_task(self, task: Task) -> TimelineEvent:
        """Начало отслеживания задачи"""
        event = self._create_event(
            event_type=TimelineEventType.TASK_STARTED,
            task_id=task.task_id,
            title=f"Задача начата: {task.title}",
            description=f"Начато выполнение задачи '{task.title}'",
            metadata={
                "task_title": task.title,
                "task_description": task.description,
                "total_steps": len(task.steps),
                "priority": task.priority.value
            }
        )
        
        # Создаем сегмент для задачи
        if self.auto_create_segments:
            self._create_task_segment(task)
        
        self.logger.info("Отслеживание задачи начато", task_id=task.task_id, event_id=event.event_id)
        return event
    
    def complete_task(self, task: Task, success: bool) -> TimelineEvent:
        """Завершение отслеживания задачи"""
        event_type = TimelineEventType.TASK_COMPLETED if success else TimelineEventType.TASK_FAILED
        status_text = "завершена" if success else "провалена"
        
        event = self._create_event(
            event_type=event_type,
            task_id=task.task_id,
            title=f"Задача {status_text}: {task.title}",
            description=f"Задача '{task.title}' {status_text}",
            metadata={
                "task_title": task.title,
                "success": success,
                "total_duration": task.get_duration(),
                "completed_steps": len([s for s in task.steps if s.status == StepStatus.COMPLETED]),
                "failed_steps": len([s for s in task.steps if s.status == StepStatus.FAILED])
            }
        )
        
        # Завершаем сегмент задачи
        if self.auto_create_segments:
            self._complete_task_segment(task)
        
        self.logger.info(
            f"Отслеживание задачи завершено ({status_text})",
            task_id=task.task_id,
            event_id=event.event_id
        )
        return event
    
    def start_step(self, task: Task, step: TaskStep) -> TimelineEvent:
        """Начало отслеживания шага"""
        event = self._create_event(
            event_type=TimelineEventType.STEP_STARTED,
            task_id=task.task_id,
            step_id=step.step_id,
            title=f"Шаг начат: {step.title}",
            description=f"Начато выполнение шага '{step.title}'",
            metadata={
                "step_title": step.title,
                "step_description": step.description,
                "step_priority": step.priority.value,
                "estimated_duration": step.estimated_duration
            }
        )
        
        # Создаем сегмент для шага
        if self.auto_create_segments:
            self._create_step_segment(task, step)
        
        self.logger.info("Отслеживание шага начато", task_id=task.task_id, step_id=step.step_id, event_id=event.event_id)
        return event
    
    def complete_step(self, task: Task, step: TaskStep, success: bool) -> TimelineEvent:
        """Завершение отслеживания шага"""
        event_type = TimelineEventType.STEP_COMPLETED if success else TimelineEventType.STEP_FAILED
        status_text = "завершен" if success else "провален"
        
        event = self._create_event(
            event_type=event_type,
            task_id=task.task_id,
            step_id=step.step_id,
            title=f"Шаг {status_text}: {step.title}",
            description=f"Шаг '{step.title}' {status_text}",
            metadata={
                "step_title": step.title,
                "success": success,
                "duration": step.get_duration(),
                "error_count": step.error_count,
                "retry_count": len(step.subtasks)
            }
        )
        
        # Завершаем сегмент шага
        if self.auto_create_segments:
            self._complete_step_segment(task, step)
        
        self.logger.info(
            f"Отслеживание шага завершено ({status_text})",
            task_id=task.task_id,
            step_id=step.step_id,
            event_id=event.event_id
        )
        return event
    
    def log_command_execution(self, task_id: str, step_id: str, command: str, 
                            success: bool, duration: float, output: str = "", 
                            error: str = "", exit_code: int = 0) -> TimelineEvent:
        """Логирование выполнения команды"""
        event_type = TimelineEventType.COMMAND_EXECUTED if success else TimelineEventType.COMMAND_FAILED
        
        event = self._create_event(
            event_type=event_type,
            task_id=task_id,
            step_id=step_id,
            title=f"Команда {'выполнена' if success else 'провалена'}: {command[:50]}...",
            description=f"Команда: {command}",
            duration=duration,
            metadata={
                "command": command,
                "success": success,
                "exit_code": exit_code,
                "output_length": len(output),
                "error_length": len(error),
                "output_preview": output[:200] if output else "",
                "error_preview": error[:200] if error else ""
            }
        )
        
        return event
    
    def log_command_retry(self, task_id: str, step_id: str, command: str, 
                         retry_count: int, reason: str) -> TimelineEvent:
        """Логирование повторной попытки команды"""
        event = self._create_event(
            event_type=TimelineEventType.COMMAND_RETRY,
            task_id=task_id,
            step_id=step_id,
            title=f"Повторная попытка команды: {command[:50]}...",
            description=f"Попытка {retry_count}: {command}",
            metadata={
                "command": command,
                "retry_count": retry_count,
                "reason": reason
            }
        )
        
        return event
    
    def log_autocorrection(self, task_id: str, step_id: str, original_command: str, 
                          corrected_command: str, correction_type: str, success: bool) -> TimelineEvent:
        """Логирование автокоррекции"""
        event = self._create_event(
            event_type=TimelineEventType.AUTOCORRECTION_APPLIED,
            task_id=task_id,
            step_id=step_id,
            title=f"Автокоррекция применена: {correction_type}",
            description=f"Исправлена команда: {original_command} -> {corrected_command}",
            metadata={
                "original_command": original_command,
                "corrected_command": corrected_command,
                "correction_type": correction_type,
                "success": success
            }
        )
        
        return event
    
    def log_error_escalation(self, task_id: str, step_id: str, error_count: int, 
                            threshold: int, reason: str) -> TimelineEvent:
        """Логирование эскалации ошибок"""
        event = self._create_event(
            event_type=TimelineEventType.ERROR_ESCALATION,
            task_id=task_id,
            step_id=step_id,
            title=f"Эскалация ошибок: {error_count}/{threshold}",
            description=f"Превышен порог ошибок: {reason}",
            metadata={
                "error_count": error_count,
                "threshold": threshold,
                "reason": reason
            }
        )
        
        return event
    
    def log_human_escalation(self, task_id: str, step_id: str, reason: str, 
                           error_details: Dict[str, Any]) -> TimelineEvent:
        """Логирование эскалации к человеку"""
        event = self._create_event(
            event_type=TimelineEventType.HUMAN_ESCALATION,
            task_id=task_id,
            step_id=step_id,
            title="КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ К ЧЕЛОВЕКУ",
            description=f"Требуется вмешательство человека: {reason}",
            metadata={
                "reason": reason,
                "error_details": error_details
            }
        )
        
        return event
    
    def log_system_event(self, event_type: str, title: str, description: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> TimelineEvent:
        """Логирование системного события"""
        event = self._create_event(
            event_type=TimelineEventType.SYSTEM_EVENT,
            title=title,
            description=description,
            metadata={
                "system_event_type": event_type,
                **(metadata or {})
            }
        )
        
        return event
    
    def get_task_timeline(self, task_id: str) -> List[TimelineEvent]:
        """Получение временной шкалы задачи"""
        task_events = [
            event for event in self.events.values()
            if event.task_id == task_id
        ]
        
        # Сортируем по времени
        task_events.sort(key=lambda x: x.timestamp)
        
        return task_events
    
    def get_step_timeline(self, task_id: str, step_id: str) -> List[TimelineEvent]:
        """Получение временной шкалы шага"""
        step_events = [
            event for event in self.events.values()
            if event.task_id == task_id and event.step_id == step_id
        ]
        
        # Сортируем по времени
        step_events.sort(key=lambda x: x.timestamp)
        
        return step_events
    
    def get_timeline_segments(self, task_id: str) -> List[TimelineSegment]:
        """Получение сегментов временной шкалы задачи"""
        task_segments = [
            segment for segment in self.segments.values()
            if task_id in segment.metadata.get("task_ids", [])
        ]
        
        # Сортируем по времени начала
        task_segments.sort(key=lambda x: x.start_time)
        
        return task_segments
    
    def analyze_performance(self, task_id: str) -> Dict[str, Any]:
        """Анализ производительности задачи"""
        if not self.enable_performance_analysis:
            return {}
        
        task_events = self.get_task_timeline(task_id)
        if not task_events:
            return {}
        
        # Находим начало и конец задачи
        start_events = [e for e in task_events if e.event_type == TimelineEventType.TASK_STARTED]
        end_events = [e for e in task_events if e.event_type in [TimelineEventType.TASK_COMPLETED, TimelineEventType.TASK_FAILED]]
        
        if not start_events or not end_events:
            return {}
        
        start_time = start_events[0].timestamp
        end_time = end_events[0].timestamp
        total_duration = (end_time - start_time).total_seconds()
        
        # Анализируем команды
        command_events = [e for e in task_events if e.event_type in [TimelineEventType.COMMAND_EXECUTED, TimelineEventType.COMMAND_FAILED]]
        successful_commands = [e for e in command_events if e.event_type == TimelineEventType.COMMAND_EXECUTED]
        failed_commands = [e for e in command_events if e.event_type == TimelineEventType.COMMAND_FAILED]
        
        # Анализируем шаги
        step_events = [e for e in task_events if e.event_type in [TimelineEventType.STEP_STARTED, TimelineEventType.STEP_COMPLETED, TimelineEventType.STEP_FAILED]]
        step_starts = [e for e in step_events if e.event_type == TimelineEventType.STEP_STARTED]
        step_completions = [e for e in step_events if e.event_type == TimelineEventType.STEP_COMPLETED]
        step_failures = [e for e in step_events if e.event_type == TimelineEventType.STEP_FAILED]
        
        # Вычисляем метрики
        analysis = {
            "total_duration": total_duration,
            "total_events": len(task_events),
            "command_stats": {
                "total_commands": len(command_events),
                "successful_commands": len(successful_commands),
                "failed_commands": len(failed_commands),
                "success_rate": len(successful_commands) / len(command_events) * 100 if command_events else 0
            },
            "step_stats": {
                "total_steps": len(step_starts),
                "completed_steps": len(step_completions),
                "failed_steps": len(step_failures),
                "success_rate": len(step_completions) / len(step_starts) * 100 if step_starts else 0
            },
            "timeline_stats": {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "events_per_minute": len(task_events) / (total_duration / 60) if total_duration > 0 else 0
            }
        }
        
        # Анализируем задержки между событиями
        if len(task_events) > 1:
            delays = []
            for i in range(1, len(task_events)):
                delay = (task_events[i].timestamp - task_events[i-1].timestamp).total_seconds()
                delays.append(delay)
            
            analysis["delay_stats"] = {
                "avg_delay": sum(delays) / len(delays) if delays else 0,
                "max_delay": max(delays) if delays else 0,
                "min_delay": min(delays) if delays else 0
            }
        
        return analysis
    
    def export_timeline(self, task_id: str, format_type: str = "json") -> str:
        """Экспорт временной шкалы"""
        task_events = self.get_task_timeline(task_id)
        task_segments = self.get_timeline_segments(task_id)
        performance_analysis = self.analyze_performance(task_id)
        
        timeline_data = {
            "task_id": task_id,
            "exported_at": datetime.now().isoformat(),
            "events": [event.to_dict() for event in task_events],
            "segments": [segment.to_dict() for segment in task_segments],
            "performance_analysis": performance_analysis
        }
        
        # Создаем директорию для экспорта
        export_dir = Path(self.config.get("export_dir", "timeline_exports"))
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерируем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"timeline_{task_id}_{timestamp}.{format_type}"
        file_path = export_dir / filename
        
        # Экспортируем в указанном формате
        if format_type == "json":
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        else:
            # Для других форматов можно добавить дополнительную логику
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json.dumps(timeline_data, ensure_ascii=False, indent=2))
        
        self.logger.info(
            "Временная шкала экспортирована",
            task_id=task_id,
            format=format_type,
            file_path=str(file_path),
            events_count=len(task_events)
        )
        
        return str(file_path)
    
    def cleanup_old_events(self, days: int = 30):
        """Очистка старых событий"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        old_events = [
            event_id for event_id, event in self.events.items()
            if event.timestamp < cutoff_time
        ]
        
        for event_id in old_events:
            del self.events[event_id]
        
        old_segments = [
            segment_id for segment_id, segment in self.segments.items()
            if segment.start_time < cutoff_time
        ]
        
        for segment_id in old_segments:
            del self.segments[segment_id]
        
        self.logger.info(
            "Старые события и сегменты очищены",
            events_removed=len(old_events),
            segments_removed=len(old_segments),
            retention_days=days
        )
    
    def _create_event(self, event_type: TimelineEventType, task_id: Optional[str] = None, 
                     step_id: Optional[str] = None, title: str = "", description: str = "", 
                     duration: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> TimelineEvent:
        """Создание события"""
        event_id = f"event_{event_type.value}_{int(time.time() * 1000)}"
        
        event = TimelineEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(),
            task_id=task_id,
            step_id=step_id,
            title=title,
            description=description,
            duration=duration,
            metadata=metadata or {}
        )
        
        # Проверяем лимит событий на задачу
        if task_id:
            task_events_count = len([e for e in self.events.values() if e.task_id == task_id])
            if task_events_count >= self.max_events_per_task:
                self.logger.warning(
                    "Достигнут лимит событий для задачи",
                    task_id=task_id,
                    max_events=self.max_events_per_task
                )
                return event
        
        self.events[event_id] = event
        return event
    
    def _create_task_segment(self, task: Task):
        """Создание сегмента задачи"""
        segment_id = f"task_segment_{task.task_id}_{int(time.time() * 1000)}"
        
        segment = TimelineSegment(
            segment_id=segment_id,
            start_time=datetime.now(),
            end_time=None,
            duration=None,
            event_type=TimelineEventType.TASK_STARTED,
            title=f"Выполнение задачи: {task.title}",
            description=f"Сегмент выполнения задачи '{task.title}'",
            metadata={
                "task_id": task.task_id,
                "task_title": task.title,
                "task_ids": [task.task_id]
            }
        )
        
        self.segments[segment_id] = segment
    
    def _complete_task_segment(self, task: Task):
        """Завершение сегмента задачи"""
        # Находим активный сегмент задачи
        active_segments = [
            segment for segment in self.segments.values()
            if segment.metadata.get("task_id") == task.task_id and segment.end_time is None
        ]
        
        if active_segments:
            segment = active_segments[0]
            segment.end_time = datetime.now()
            segment.duration = (segment.end_time - segment.start_time).total_seconds()
    
    def _create_step_segment(self, task: Task, step: TaskStep):
        """Создание сегмента шага"""
        segment_id = f"step_segment_{step.step_id}_{int(time.time() * 1000)}"
        
        segment = TimelineSegment(
            segment_id=segment_id,
            start_time=datetime.now(),
            end_time=None,
            duration=None,
            event_type=TimelineEventType.STEP_STARTED,
            title=f"Выполнение шага: {step.title}",
            description=f"Сегмент выполнения шага '{step.title}'",
            metadata={
                "task_id": task.task_id,
                "step_id": step.step_id,
                "step_title": step.title,
                "task_ids": [task.task_id]
            }
        )
        
        self.segments[segment_id] = segment
    
    def _complete_step_segment(self, task: Task, step: TaskStep):
        """Завершение сегмента шага"""
        # Находим активный сегмент шага
        active_segments = [
            segment for segment in self.segments.values()
            if segment.metadata.get("step_id") == step.step_id and segment.end_time is None
        ]
        
        if active_segments:
            segment = active_segments[0]
            segment.end_time = datetime.now()
            segment.duration = (segment.end_time - segment.start_time).total_seconds()
