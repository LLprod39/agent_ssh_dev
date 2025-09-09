"""
State Manager - Система управления состоянием SSH Agent

Этот модуль обеспечивает:
- Централизованное управление состоянием системы
- Отслеживание изменений состояния
- Восстановление состояния после ошибок
- Синхронизацию состояния между компонентами
- Персистентность состояния
"""

import json
import time
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import threading
import asyncio
import logging

from ..utils.logger import StructuredLogger


class StateType(Enum):
    """Тип состояния"""
    AGENT_STATE = "agent_state"
    TASK_STATE = "task_state"
    EXECUTION_STATE = "execution_state"
    CONNECTION_STATE = "connection_state"
    ERROR_STATE = "error_state"
    CONFIG_STATE = "config_state"


class StateEvent(Enum):
    """Событие изменения состояния"""
    STATE_CHANGED = "state_changed"
    STATE_RESTORED = "state_restored"
    STATE_CLEARED = "state_cleared"
    STATE_SYNCED = "state_synced"
    STATE_ERROR = "state_error"


@dataclass
class StateSnapshot:
    """Снимок состояния"""
    
    snapshot_id: str
    state_type: StateType
    timestamp: datetime
    data: Dict[str, Any]
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "snapshot_id": self.snapshot_id,
            "state_type": self.state_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "version": self.version,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateSnapshot':
        """Создание из словаря"""
        return cls(
            snapshot_id=data["snapshot_id"],
            state_type=StateType(data["state_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data["data"],
            version=data.get("version", 1),
            metadata=data.get("metadata", {})
        )


@dataclass
class StateChange:
    """Изменение состояния"""
    
    change_id: str
    state_type: StateType
    timestamp: datetime
    old_data: Dict[str, Any]
    new_data: Dict[str, Any]
    change_reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "change_id": self.change_id,
            "state_type": self.state_type.value,
            "timestamp": self.timestamp.isoformat(),
            "old_data": self.old_data,
            "new_data": self.new_data,
            "change_reason": self.change_reason,
            "metadata": self.metadata
        }


class StateManager:
    """
    Менеджер состояния системы
    
    Основные возможности:
    - Централизованное управление состоянием
    - Отслеживание изменений состояния
    - Восстановление состояния после ошибок
    - Синхронизация состояния между компонентами
    - Персистентность состояния
    """
    
    def __init__(
        self,
        state_file: Optional[str] = None,
        max_snapshots: int = 100,
        auto_save_interval: int = 30
    ):
        """
        Инициализация State Manager
        
        Args:
            state_file: Путь к файлу для сохранения состояния
            max_snapshots: Максимальное количество снимков состояния
            auto_save_interval: Интервал автоматического сохранения в секундах
        """
        self.state_file = state_file or "state/agent_state.json"
        self.max_snapshots = max_snapshots
        self.auto_save_interval = auto_save_interval
        self.logger = StructuredLogger("StateManager")
        
        # Текущие состояния
        self.current_states: Dict[StateType, Dict[str, Any]] = {}
        
        # История изменений состояния
        self.state_history: List[StateChange] = []
        
        # Снимки состояния
        self.state_snapshots: List[StateSnapshot] = []
        
        # Колбэки для уведомлений
        self.state_callbacks: Dict[StateEvent, List[Callable]] = {
            event: [] for event in StateEvent
        }
        
        # Блокировка для потокобезопасности
        self._lock = threading.RLock()
        
        # Автоматическое сохранение
        self._auto_save_task: Optional[asyncio.Task] = None
        self._auto_save_enabled = False
        
        # Статистика
        self.stats = {
            "state_changes": 0,
            "snapshots_created": 0,
            "states_restored": 0,
            "auto_saves": 0,
            "errors": 0
        }
        
        self.logger.info(
            "State Manager инициализирован",
            state_file=self.state_file,
            max_snapshots=self.max_snapshots
        )
    
    async def start(self):
        """Запуск State Manager"""
        self.logger.info("Запуск State Manager")
        
        # Загружаем сохраненное состояние
        await self.load_state()
        
        # Запускаем автоматическое сохранение
        if self.auto_save_interval > 0:
            self._auto_save_enabled = True
            self._auto_save_task = asyncio.create_task(self._auto_save_loop())
            self.logger.info("Автоматическое сохранение запущено")
    
    async def stop(self):
        """Остановка State Manager"""
        self.logger.info("Остановка State Manager")
        
        # Останавливаем автоматическое сохранение
        self._auto_save_enabled = False
        if self._auto_save_task:
            self._auto_save_task.cancel()
            try:
                await self._auto_save_task
            except asyncio.CancelledError:
                pass
        
        # Сохраняем состояние
        await self.save_state()
        
        self.logger.info("State Manager остановлен")
    
    def set_state(
        self,
        state_type: StateType,
        data: Dict[str, Any],
        reason: str = "manual_change",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Установка состояния
        
        Args:
            state_type: Тип состояния
            data: Данные состояния
            reason: Причина изменения
            metadata: Дополнительные метаданные
            
        Returns:
            True если состояние установлено успешно
        """
        with self._lock:
            try:
                old_data = self.current_states.get(state_type, {}).copy()
                
                # Создаем запись об изменении
                change = StateChange(
                    change_id=f"change_{int(time.time() * 1000)}",
                    state_type=state_type,
                    timestamp=datetime.now(),
                    old_data=old_data,
                    new_data=data.copy(),
                    change_reason=reason,
                    metadata=metadata or {}
                )
                
                # Обновляем состояние
                self.current_states[state_type] = data.copy()
                
                # Добавляем в историю
                self.state_history.append(change)
                
                # Ограничиваем размер истории
                if len(self.state_history) > self.max_snapshots * 2:
                    self.state_history = self.state_history[-self.max_snapshots:]
                
                self.stats["state_changes"] += 1
                
                self.logger.debug(
                    "Состояние обновлено",
                    state_type=state_type.value,
                    reason=reason,
                    changes_count=len(self.state_history)
                )
                
                # Уведомляем о изменении
                self._notify_state_event(StateEvent.STATE_CHANGED, {
                    "state_type": state_type,
                    "change": change,
                    "old_data": old_data,
                    "new_data": data
                })
                
                return True
                
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"Ошибка установки состояния: {str(e)}"
                self.logger.error("Ошибка установки состояния", error=error_msg, state_type=state_type.value)
                
                self._notify_state_event(StateEvent.STATE_ERROR, {
                    "state_type": state_type,
                    "error": error_msg
                })
                
                return False
    
    def get_state(self, state_type: StateType) -> Dict[str, Any]:
        """
        Получение состояния
        
        Args:
            state_type: Тип состояния
            
        Returns:
            Данные состояния
        """
        with self._lock:
            return self.current_states.get(state_type, {}).copy()
    
    def get_all_states(self) -> Dict[StateType, Dict[str, Any]]:
        """Получение всех состояний"""
        with self._lock:
            return {state_type: data.copy() for state_type, data in self.current_states.items()}
    
    def clear_state(self, state_type: StateType, reason: str = "manual_clear") -> bool:
        """
        Очистка состояния
        
        Args:
            state_type: Тип состояния
            reason: Причина очистки
            
        Returns:
            True если состояние очищено успешно
        """
        return self.set_state(state_type, {}, reason)
    
    def clear_all_states(self, reason: str = "manual_clear_all") -> bool:
        """
        Очистка всех состояний
        
        Args:
            reason: Причина очистки
            
        Returns:
            True если состояния очищены успешно
        """
        with self._lock:
            try:
                for state_type in list(self.current_states.keys()):
                    self.clear_state(state_type, reason)
                
                self.logger.info("Все состояния очищены", reason=reason)
                return True
                
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"Ошибка очистки состояний: {str(e)}"
                self.logger.error("Ошибка очистки состояний", error=error_msg)
                return False
    
    def create_snapshot(
        self,
        state_type: StateType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[StateSnapshot]:
        """
        Создание снимка состояния
        
        Args:
            state_type: Тип состояния
            metadata: Дополнительные метаданные
            
        Returns:
            Снимок состояния или None при ошибке
        """
        with self._lock:
            try:
                snapshot_id = f"snapshot_{state_type.value}_{int(time.time() * 1000)}"
                
                snapshot = StateSnapshot(
                    snapshot_id=snapshot_id,
                    state_type=state_type,
                    timestamp=datetime.now(),
                    data=self.current_states.get(state_type, {}).copy(),
                    metadata=metadata or {}
                )
                
                self.state_snapshots.append(snapshot)
                
                # Ограничиваем количество снимков
                if len(self.state_snapshots) > self.max_snapshots:
                    self.state_snapshots = self.state_snapshots[-self.max_snapshots:]
                
                self.stats["snapshots_created"] += 1
                
                self.logger.debug(
                    "Снимок состояния создан",
                    snapshot_id=snapshot_id,
                    state_type=state_type.value
                )
                
                return snapshot
                
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"Ошибка создания снимка: {str(e)}"
                self.logger.error("Ошибка создания снимка", error=error_msg, state_type=state_type.value)
                return None
    
    def restore_from_snapshot(
        self,
        snapshot_id: str,
        reason: str = "manual_restore"
    ) -> bool:
        """
        Восстановление состояния из снимка
        
        Args:
            snapshot_id: ID снимка
            reason: Причина восстановления
            
        Returns:
            True если состояние восстановлено успешно
        """
        with self._lock:
            try:
                # Ищем снимок
                snapshot = None
                for snap in self.state_snapshots:
                    if snap.snapshot_id == snapshot_id:
                        snapshot = snap
                        break
                
                if not snapshot:
                    self.logger.warning("Снимок не найден", snapshot_id=snapshot_id)
                    return False
                
                # Восстанавливаем состояние
                success = self.set_state(
                    snapshot.state_type,
                    snapshot.data,
                    reason,
                    {"restored_from": snapshot_id, "snapshot_timestamp": snapshot.timestamp.isoformat()}
                )
                
                if success:
                    self.stats["states_restored"] += 1
                    
                    self.logger.info(
                        "Состояние восстановлено из снимка",
                        snapshot_id=snapshot_id,
                        state_type=snapshot.state_type.value
                    )
                    
                    # Уведомляем о восстановлении
                    self._notify_state_event(StateEvent.STATE_RESTORED, {
                        "snapshot": snapshot,
                        "state_type": snapshot.state_type
                    })
                
                return success
                
            except Exception as e:
                self.stats["errors"] += 1
                error_msg = f"Ошибка восстановления состояния: {str(e)}"
                self.logger.error("Ошибка восстановления состояния", error=error_msg, snapshot_id=snapshot_id)
                return False
    
    def get_snapshots(
        self,
        state_type: Optional[StateType] = None,
        limit: int = 10
    ) -> List[StateSnapshot]:
        """
        Получение снимков состояния
        
        Args:
            state_type: Тип состояния (если None, то все типы)
            limit: Максимальное количество снимков
            
        Returns:
            Список снимков состояния
        """
        with self._lock:
            snapshots = self.state_snapshots
            
            if state_type:
                snapshots = [snap for snap in snapshots if snap.state_type == state_type]
            
            # Сортируем по времени (новые первыми)
            snapshots.sort(key=lambda x: x.timestamp, reverse=True)
            
            return snapshots[:limit]
    
    def get_state_history(
        self,
        state_type: Optional[StateType] = None,
        limit: int = 50
    ) -> List[StateChange]:
        """
        Получение истории изменений состояния
        
        Args:
            state_type: Тип состояния (если None, то все типы)
            limit: Максимальное количество записей
            
        Returns:
            Список изменений состояния
        """
        with self._lock:
            history = self.state_history
            
            if state_type:
                history = [change for change in history if change.state_type == state_type]
            
            # Сортируем по времени (новые первыми)
            history.sort(key=lambda x: x.timestamp, reverse=True)
            
            return history[:limit]
    
    async def save_state(self) -> bool:
        """
        Сохранение состояния в файл
        
        Returns:
            True если состояние сохранено успешно
        """
        try:
            state_data = {
                "current_states": {
                    state_type.value: data
                    for state_type, data in self.current_states.items()
                },
                "state_snapshots": [snapshot.to_dict() for snapshot in self.state_snapshots],
                "state_history": [change.to_dict() for change in self.state_history[-100:]],  # Последние 100 изменений
                "stats": self.stats,
                "saved_at": datetime.now().isoformat()
            }
            
            # Создаем директорию если не существует
            state_path = Path(self.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем в файл
            with open(state_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("Состояние сохранено", state_file=self.state_file)
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            error_msg = f"Ошибка сохранения состояния: {str(e)}"
            self.logger.error("Ошибка сохранения состояния", error=error_msg)
            return False
    
    async def load_state(self) -> bool:
        """
        Загрузка состояния из файла
        
        Returns:
            True если состояние загружено успешно
        """
        try:
            state_path = Path(self.state_file)
            if not state_path.exists():
                self.logger.info("Файл состояния не найден, создаем новое состояние")
                return True
            
            with open(state_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Загружаем текущие состояния
            current_states = state_data.get("current_states", {})
            for state_type_str, data in current_states.items():
                try:
                    state_type = StateType(state_type_str)
                    self.current_states[state_type] = data
                except ValueError:
                    self.logger.warning("Неизвестный тип состояния", state_type=state_type_str)
            
            # Загружаем снимки состояния
            snapshots_data = state_data.get("state_snapshots", [])
            for snapshot_data in snapshots_data:
                try:
                    snapshot = StateSnapshot.from_dict(snapshot_data)
                    self.state_snapshots.append(snapshot)
                except Exception as e:
                    self.logger.warning("Ошибка загрузки снимка", error=str(e))
            
            # Загружаем историю изменений
            history_data = state_data.get("state_history", [])
            for change_data in history_data:
                try:
                    change = StateChange(
                        change_id=change_data["change_id"],
                        state_type=StateType(change_data["state_type"]),
                        timestamp=datetime.fromisoformat(change_data["timestamp"]),
                        old_data=change_data["old_data"],
                        new_data=change_data["new_data"],
                        change_reason=change_data["change_reason"],
                        metadata=change_data.get("metadata", {})
                    )
                    self.state_history.append(change)
                except Exception as e:
                    self.logger.warning("Ошибка загрузки изменения состояния", error=str(e))
            
            # Загружаем статистику
            saved_stats = state_data.get("stats", {})
            self.stats.update(saved_stats)
            
            self.logger.info(
                "Состояние загружено",
                states_count=len(self.current_states),
                snapshots_count=len(self.state_snapshots),
                history_count=len(self.state_history)
            )
            
            return True
            
        except Exception as e:
            self.stats["errors"] += 1
            error_msg = f"Ошибка загрузки состояния: {str(e)}"
            self.logger.error("Ошибка загрузки состояния", error=error_msg)
            return False
    
    def register_callback(self, event: StateEvent, callback: Callable):
        """Регистрация колбэка для событий состояния"""
        self.state_callbacks[event].append(callback)
        self.logger.debug("Колбэк зарегистрирован", event=event.value)
    
    def unregister_callback(self, event: StateEvent, callback: Callable):
        """Отмена регистрации колбэка"""
        if callback in self.state_callbacks[event]:
            self.state_callbacks[event].remove(callback)
            self.logger.debug("Колбэк отменен", event=event.value)
    
    def _notify_state_event(self, event: StateEvent, data: Dict[str, Any]):
        """Уведомление о событии состояния"""
        for callback in self.state_callbacks[event]:
            try:
                callback(event, data)
            except Exception as e:
                self.logger.warning("Ошибка в колбэке состояния", event=event.value, error=str(e))
    
    async def _auto_save_loop(self):
        """Цикл автоматического сохранения"""
        while self._auto_save_enabled:
            try:
                await asyncio.sleep(self.auto_save_interval)
                
                if self._auto_save_enabled:
                    success = await self.save_state()
                    if success:
                        self.stats["auto_saves"] += 1
                        self.logger.debug("Автоматическое сохранение выполнено")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                self.logger.error("Ошибка автоматического сохранения", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики State Manager"""
        return {
            **self.stats,
            "current_states_count": len(self.current_states),
            "snapshots_count": len(self.state_snapshots),
            "history_count": len(self.state_history),
            "auto_save_enabled": self._auto_save_enabled,
            "auto_save_interval": self.auto_save_interval
        }
    
    def cleanup_old_data(self, days: int = 7):
        """Очистка старых данных"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with self._lock:
            # Очищаем старые снимки
            old_snapshots = [
                snapshot for snapshot in self.state_snapshots
                if snapshot.timestamp < cutoff_time
            ]
            for snapshot in old_snapshots:
                self.state_snapshots.remove(snapshot)
            
            # Очищаем старую историю
            old_history = [
                change for change in self.state_history
                if change.timestamp < cutoff_time
            ]
            for change in old_history:
                self.state_history.remove(change)
            
            self.logger.info(
                "Старые данные очищены",
                snapshots_removed=len(old_snapshots),
                history_removed=len(old_history),
                retention_days=days
            )
    
    def __str__(self) -> str:
        return f"StateManager(states={len(self.current_states)}, snapshots={len(self.state_snapshots)})"
    
    def __repr__(self) -> str:
        return f"StateManager(states={len(self.current_states)}, stats={self.stats})"
