"""
Интерфейс для взаимодействия с LLM
"""
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import requests
import logging
from datetime import datetime

from ..config.agent_config import LLMConfig
from ..utils.logger import StructuredLogger


@dataclass
class LLMRequest:
    """Запрос к LLM"""
    
    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    system_message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """Ответ от LLM"""
    
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    duration: Optional[float] = None  # в секундах
    metadata: Optional[Dict[str, Any]] = None


class LLMInterface(ABC):
    """Абстрактный интерфейс для работы с LLM"""
    
    @abstractmethod
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Генерация ответа от LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Проверка доступности LLM"""
        pass


class OpenAIInterface(LLMInterface):
    """Интерфейс для работы с OpenAI API"""
    
    def __init__(self, config: LLMConfig, logger: Optional[StructuredLogger] = None):
        """
        Инициализация интерфейса OpenAI
        
        Args:
            config: Конфигурация LLM
            logger: Логгер
        """
        self.config = config
        self.logger = logger or StructuredLogger("OpenAIInterface")
        self.base_url = config.base_url.rstrip('/')
        self.api_key = config.api_key
        self.timeout = config.timeout
        
        # Проверяем доступность API
        if not self.is_available():
            self.logger.warning("OpenAI API недоступен")
    
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация ответа от OpenAI
        
        Args:
            request: Запрос к LLM
            
        Returns:
            Ответ от LLM
        """
        start_time = time.time()
        
        try:
            # Подготавливаем сообщения
            messages = []
            
            if request.system_message:
                messages.append({
                    "role": "system",
                    "content": request.system_message
                })
            
            # Добавляем контекст если есть
            if request.context:
                context_message = self._format_context(request.context)
                messages.append({
                    "role": "system",
                    "content": context_message
                })
            
            messages.append({
                "role": "user",
                "content": request.prompt
            })
            
            # Подготавливаем параметры запроса
            payload = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
            
            # Выполняем запрос
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            self.logger.debug(
                "Отправка запроса к OpenAI",
                model=request.model,
                prompt_length=len(request.prompt),
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # Извлекаем ответ
                content = data['choices'][0]['message']['content']
                usage = data.get('usage', {})
                
                self.logger.info(
                    "Успешный ответ от OpenAI",
                    model=request.model,
                    response_length=len(content),
                    duration=duration,
                    tokens_used=usage.get('total_tokens', 0)
                )
                
                return LLMResponse(
                    success=True,
                    content=content,
                    usage=usage,
                    model=request.model,
                    duration=duration,
                    metadata=request.metadata
                )
            else:
                error_msg = f"Ошибка API: {response.status_code} - {response.text}"
                self.logger.error(
                    "Ошибка запроса к OpenAI",
                    status_code=response.status_code,
                    error=error_msg,
                    duration=duration
                )
                
                return LLMResponse(
                    success=False,
                    error=error_msg,
                    duration=duration,
                    metadata=request.metadata
                )
                
        except requests.exceptions.Timeout:
            duration = time.time() - start_time
            error_msg = f"Таймаут запроса к OpenAI ({self.timeout}s)"
            self.logger.error("Таймаут запроса к OpenAI", duration=duration)
            
            return LLMResponse(
                success=False,
                error=error_msg,
                duration=duration,
                metadata=request.metadata
            )
            
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            error_msg = f"Ошибка сети: {str(e)}"
            self.logger.error("Ошибка сети при запросе к OpenAI", error=error_msg, duration=duration)
            
            return LLMResponse(
                success=False,
                error=error_msg,
                duration=duration,
                metadata=request.metadata
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Неожиданная ошибка: {str(e)}"
            self.logger.error("Неожиданная ошибка при запросе к OpenAI", error=error_msg, duration=duration)
            
            return LLMResponse(
                success=False,
                error=error_msg,
                duration=duration,
                metadata=request.metadata
            )
    
    def is_available(self) -> bool:
        """Проверка доступности OpenAI API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Простой запрос для проверки доступности
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self.logger.debug(f"OpenAI API недоступен: {e}")
            return False
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Форматирование контекста для LLM"""
        if not context:
            return ""
        
        context_parts = []
        for key, value in context.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            context_parts.append(f"{key}: {value}")
        
        return "Контекст:\n" + "\n".join(context_parts)


class MockLLMInterface(LLMInterface):
    """Мок-интерфейс для тестирования"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger("MockLLMInterface")
        self.responses = []
        self.request_count = 0
    
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Генерация мок-ответа"""
        self.request_count += 1
        
        # Простая логика для тестирования
        if "подзадач" in request.prompt.lower() or "команды" in request.prompt.lower():
            mock_content = self._generate_mock_execution_response()
        elif "план" in request.prompt.lower() or "шаги" in request.prompt.lower():
            mock_content = self._generate_mock_planning_response()
        else:
            mock_content = self._generate_mock_execution_response()  # По умолчанию используем execution response
        
        self.logger.debug(f"Генерация мок-ответа #{self.request_count}")
        self.logger.debug(f"Мок-контент: {mock_content[:200]}...")
        
        return LLMResponse(
            success=True,
            content=mock_content,
            model=request.model,
            duration=0.1,
            usage={"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50}
        )
    
    def is_available(self) -> bool:
        """Мок всегда доступен"""
        return True
    
    def _generate_mock_planning_response(self) -> str:
        """Генерация мок-ответа для планирования"""
        return """
        {
            "steps": [
                {
                    "title": "Подготовка системы",
                    "description": "Обновить систему и установить необходимые пакеты",
                    "priority": "high",
                    "estimated_duration": 10,
                    "dependencies": []
                },
                {
                    "title": "Настройка сервиса",
                    "description": "Настроить и запустить сервис",
                    "priority": "high",
                    "estimated_duration": 15,
                    "dependencies": []
                },
                {
                    "title": "Проверка работоспособности",
                    "description": "Проверить что сервис работает корректно",
                    "priority": "medium",
                    "estimated_duration": 5,
                    "dependencies": []
                }
            ]
        }
        """
    
    def _generate_mock_execution_response(self) -> str:
        """Генерация мок-ответа для выполнения"""
        return """
        {
            "subtasks": [
                {
                    "title": "Обновление системы",
                    "description": "Обновить список пакетов",
                    "commands": ["sudo apt update"],
                    "health_checks": ["apt list --upgradable | wc -l"],
                    "expected_output": "Обновление завершено",
                    "rollback_commands": [],
                    "dependencies": [],
                    "timeout": 30
                },
                {
                    "title": "Установка Nginx",
                    "description": "Установить пакет nginx",
                    "commands": ["sudo apt install -y nginx"],
                    "health_checks": ["dpkg -l | grep nginx"],
                    "expected_output": "Nginx установлен",
                    "rollback_commands": ["sudo apt remove -y nginx"],
                    "dependencies": [],
                    "timeout": 30
                },
                {
                    "title": "Запуск Nginx",
                    "description": "Запустить и включить Nginx",
                    "commands": ["sudo systemctl start nginx", "sudo systemctl enable nginx"],
                    "health_checks": ["systemctl is-active nginx", "curl -I http://localhost"],
                    "expected_output": "Nginx запущен",
                    "rollback_commands": ["sudo systemctl stop nginx"],
                    "dependencies": [],
                    "timeout": 30
                }
            ]
        }
        """


class LLMInterfaceFactory:
    """Фабрика для создания интерфейсов LLM"""
    
    @staticmethod
    def create_interface(config: LLMConfig, logger: Optional[StructuredLogger] = None, 
                        mock_mode: bool = False) -> LLMInterface:
        """
        Создание интерфейса LLM
        
        Args:
            config: Конфигурация LLM
            logger: Логгер
            mock_mode: Использовать ли мок-режим
            
        Returns:
            Интерфейс LLM
        """
        if mock_mode:
            return MockLLMInterface(logger)
        
        # Определяем тип интерфейса по базовому URL
        if "openai" in config.base_url.lower() or "api.openai.com" in config.base_url:
            return OpenAIInterface(config, logger)
        else:
            # По умолчанию используем OpenAI-совместимый интерфейс
            return OpenAIInterface(config, logger)


class LLMRequestBuilder:
    """Построитель запросов к LLM"""
    
    def __init__(self, default_model: str = "gpt-4", default_temperature: float = 0.7):
        self.default_model = default_model
        self.default_temperature = default_temperature
        self.system_message = None
        self.context = None
        self.metadata = None
    
    def with_model(self, model: str) -> 'LLMRequestBuilder':
        """Установка модели"""
        self.default_model = model
        return self
    
    def with_temperature(self, temperature: float) -> 'LLMRequestBuilder':
        """Установка температуры"""
        self.default_temperature = temperature
        return self
    
    def with_system_message(self, message: str) -> 'LLMRequestBuilder':
        """Установка системного сообщения"""
        self.system_message = message
        return self
    
    def with_context(self, context: Dict[str, Any]) -> 'LLMRequestBuilder':
        """Установка контекста"""
        self.context = context
        return self
    
    def with_metadata(self, metadata: Dict[str, Any]) -> 'LLMRequestBuilder':
        """Установка метаданных"""
        self.metadata = metadata
        return self
    
    def build(self, prompt: str, max_tokens: int = 2000) -> LLMRequest:
        """Построение запроса"""
        return LLMRequest(
            prompt=prompt,
            model=self.default_model,
            temperature=self.default_temperature,
            max_tokens=max_tokens,
            system_message=self.system_message,
            context=self.context,
            metadata=self.metadata
        )
