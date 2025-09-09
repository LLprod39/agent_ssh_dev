"""
Тесты для LLM Interface
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.models.llm_interface import (
    LLMRequest, LLMResponse, LLMInterface, OpenAIInterface, MockLLMInterface,
    LLMInterfaceFactory, LLMRequestBuilder
)
from src.config.agent_config import LLMConfig


class TestLLMRequest:
    """Тесты для LLMRequest"""
    
    def test_llm_request_creation(self):
        """Тест создания запроса к LLM"""
        request = LLMRequest(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000,
            system_message="You are a helpful assistant",
            context={"key": "value"},
            metadata={"request_id": "123"}
        )
        
        assert request.prompt == "Test prompt"
        assert request.model == "gpt-4"
        assert request.temperature == 0.7
        assert request.max_tokens == 2000
        assert request.system_message == "You are a helpful assistant"
        assert request.context == {"key": "value"}
        assert request.metadata == {"request_id": "123"}
    
    def test_llm_request_default_values(self):
        """Тест значений по умолчанию"""
        request = LLMRequest(prompt="Test", model="gpt-4")
        
        assert request.prompt == "Test"
        assert request.model == "gpt-4"
        assert request.temperature == 0.7
        assert request.max_tokens == 2000
        assert request.system_message is None
        assert request.context is None
        assert request.metadata is None


class TestLLMResponse:
    """Тесты для LLMResponse"""
    
    def test_llm_response_success(self):
        """Тест успешного ответа"""
        response = LLMResponse(
            success=True,
            content="Test response",
            usage={"total_tokens": 100},
            model="gpt-4",
            duration=1.5,
            metadata={"response_id": "456"}
        )
        
        assert response.success is True
        assert response.content == "Test response"
        assert response.error is None
        assert response.usage == {"total_tokens": 100}
        assert response.model == "gpt-4"
        assert response.duration == 1.5
        assert response.metadata == {"response_id": "456"}
    
    def test_llm_response_failure(self):
        """Тест неудачного ответа"""
        response = LLMResponse(
            success=False,
            error="API error",
            duration=0.5
        )
        
        assert response.success is False
        assert response.content is None
        assert response.error == "API error"
        assert response.usage is None
        assert response.model is None
        assert response.duration == 0.5
        assert response.metadata is None


class TestOpenAIInterface:
    """Тесты для OpenAIInterface"""
    
    @pytest.fixture
    def llm_config(self):
        """Конфигурация LLM"""
        return LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            max_tokens=2000,
            temperature=0.7,
            timeout=60
        )
    
    @pytest.fixture
    def openai_interface(self, llm_config):
        """Интерфейс OpenAI"""
        return OpenAIInterface(llm_config)
    
    def test_initialization(self, llm_config):
        """Тест инициализации"""
        interface = OpenAIInterface(llm_config)
        
        assert interface.config == llm_config
        assert interface.base_url == "https://api.openai.com/v1"
        assert interface.api_key == "test-key"
        assert interface.timeout == 60
    
    def test_format_context(self, openai_interface):
        """Тест форматирования контекста"""
        context = {
            "server_info": {"os": "ubuntu", "version": "20.04"},
            "user_requirements": "Install nginx",
            "constraints": ["No reboot", "Use apt only"],
            "tools": ["apt", "systemctl"]
        }
        
        formatted = openai_interface._format_context(context)
        
        assert "Контекст:" in formatted
        assert "server_info:" in formatted
        assert "ubuntu" in formatted
        assert "user_requirements:" in formatted
        assert "Install nginx" in formatted
    
    def test_format_context_empty(self, openai_interface):
        """Тест форматирования пустого контекста"""
        formatted = openai_interface._format_context({})
        assert formatted == ""
    
    def test_format_context_with_json(self, openai_interface):
        """Тест форматирования контекста с JSON"""
        context = {
            "config": {"key": "value", "nested": {"inner": "data"}},
            "list": [1, 2, 3]
        }
        
        formatted = openai_interface._format_context(context)
        
        assert "config:" in formatted
        assert "list:" in formatted
        assert "key" in formatted
        assert "nested" in formatted
    
    @patch('requests.post')
    def test_generate_response_success(self, mock_post, openai_interface):
        """Тест успешной генерации ответа"""
        # Настройка мока
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}],
            'usage': {'total_tokens': 100, 'prompt_tokens': 50, 'completion_tokens': 50}
        }
        mock_post.return_value = mock_response
        
        request = LLMRequest(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.7,
            max_tokens=1000
        )
        
        response = openai_interface.generate_response(request)
        
        assert response.success is True
        assert response.content == "Test response"
        assert response.usage == {'total_tokens': 100, 'prompt_tokens': 50, 'completion_tokens': 50}
        assert response.model == "gpt-4"
        assert response.duration is not None
        
        # Проверяем что запрос был отправлен правильно
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.openai.com/v1/chat/completions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
        assert call_args[1]["json"]["model"] == "gpt-4"
        assert call_args[1]["json"]["temperature"] == 0.7
        assert call_args[1]["json"]["max_tokens"] == 1000
    
    @patch('requests.post')
    def test_generate_response_with_system_message(self, mock_post, openai_interface):
        """Тест генерации ответа с системным сообщением"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}],
            'usage': {'total_tokens': 100}
        }
        mock_post.return_value = mock_response
        
        request = LLMRequest(
            prompt="Test prompt",
            model="gpt-4",
            system_message="You are a helpful assistant"
        )
        
        response = openai_interface.generate_response(request)
        
        assert response.success is True
        
        # Проверяем что системное сообщение было добавлено
        call_args = mock_post.call_args
        messages = call_args[1]["json"]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Test prompt"
    
    @patch('requests.post')
    def test_generate_response_with_context(self, mock_post, openai_interface):
        """Тест генерации ответа с контекстом"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}],
            'usage': {'total_tokens': 100}
        }
        mock_post.return_value = mock_response
        
        request = LLMRequest(
            prompt="Test prompt",
            model="gpt-4",
            context={"server_info": {"os": "ubuntu"}}
        )
        
        response = openai_interface.generate_response(request)
        
        assert response.success is True
        
        # Проверяем что контекст был добавлен
        call_args = mock_post.call_args
        messages = call_args[1]["json"]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "Контекст:" in messages[0]["content"]
        assert "server_info:" in messages[0]["content"]
    
    @patch('requests.post')
    def test_generate_response_api_error(self, mock_post, openai_interface):
        """Тест генерации ответа при ошибке API"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response
        
        request = LLMRequest(prompt="Test prompt", model="gpt-4")
        
        response = openai_interface.generate_response(request)
        
        assert response.success is False
        assert "Ошибка API: 400" in response.error
        assert response.content is None
    
    @patch('requests.post')
    def test_generate_response_timeout(self, mock_post, openai_interface):
        """Тест генерации ответа при таймауте"""
        mock_post.side_effect = Exception("Timeout")
        
        request = LLMRequest(prompt="Test prompt", model="gpt-4")
        
        response = openai_interface.generate_response(request)
        
        assert response.success is False
        assert "Неожиданная ошибка" in response.error
    
    @patch('requests.get')
    def test_is_available_success(self, mock_get, openai_interface):
        """Тест проверки доступности - успех"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        available = openai_interface.is_available()
        
        assert available is True
        mock_get.assert_called_once_with(
            "https://api.openai.com/v1/models",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json"
            },
            timeout=10
        )
    
    @patch('requests.get')
    def test_is_available_failure(self, mock_get, openai_interface):
        """Тест проверки доступности - неудача"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        available = openai_interface.is_available()
        
        assert available is False
    
    @patch('requests.get')
    def test_is_available_exception(self, mock_get, openai_interface):
        """Тест проверки доступности - исключение"""
        mock_get.side_effect = Exception("Network error")
        
        available = openai_interface.is_available()
        
        assert available is False


class TestMockLLMInterface:
    """Тесты для MockLLMInterface"""
    
    @pytest.fixture
    def mock_interface(self):
        """Мок-интерфейс"""
        return MockLLMInterface()
    
    def test_initialization(self, mock_interface):
        """Тест инициализации мок-интерфейса"""
        assert mock_interface.request_count == 0
        assert mock_interface.responses == []
    
    def test_is_available(self, mock_interface):
        """Тест доступности мок-интерфейса"""
        assert mock_interface.is_available() is True
    
    def test_generate_response_planning(self, mock_interface):
        """Тест генерации ответа для планирования"""
        request = LLMRequest(
            prompt="Создай план установки nginx",
            model="gpt-4"
        )
        
        response = mock_interface.generate_response(request)
        
        assert response.success is True
        assert response.model == "gpt-4"
        assert response.duration == 0.1
        assert response.usage == {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50}
        assert "steps" in response.content
        assert "Подготовка системы" in response.content
        assert mock_interface.request_count == 1
    
    def test_generate_response_execution(self, mock_interface):
        """Тест генерации ответа для выполнения"""
        request = LLMRequest(
            prompt="Создай подзадачи для установки nginx",
            model="gpt-4"
        )
        
        response = mock_interface.generate_response(request)
        
        assert response.success is True
        assert "subtasks" in response.content
        assert "Обновление системы" in response.content
        assert "sudo apt update" in response.content
        assert mock_interface.request_count == 1
    
    def test_generate_response_default(self, mock_interface):
        """Тест генерации ответа по умолчанию"""
        request = LLMRequest(
            prompt="Простое сообщение",
            model="gpt-4"
        )
        
        response = mock_interface.generate_response(request)
        
        assert response.success is True
        assert "subtasks" in response.content  # По умолчанию используем execution response
        assert mock_interface.request_count == 1
    
    def test_generate_mock_planning_response(self, mock_interface):
        """Тест генерации мок-ответа для планирования"""
        response = mock_interface._generate_mock_planning_response()
        
        assert isinstance(response, str)
        data = json.loads(response)
        assert "steps" in data
        assert len(data["steps"]) == 3
        assert data["steps"][0]["title"] == "Подготовка системы"
        assert data["steps"][0]["priority"] == "high"
        assert data["steps"][0]["estimated_duration"] == 10
    
    def test_generate_mock_execution_response(self, mock_interface):
        """Тест генерации мок-ответа для выполнения"""
        response = mock_interface._generate_mock_execution_response()
        
        assert isinstance(response, str)
        data = json.loads(response)
        assert "subtasks" in data
        assert len(data["subtasks"]) == 3
        assert data["subtasks"][0]["title"] == "Обновление системы"
        assert "sudo apt update" in data["subtasks"][0]["commands"]
        assert "health_checks" in data["subtasks"][0]


class TestLLMInterfaceFactory:
    """Тесты для LLMInterfaceFactory"""
    
    def test_create_interface_mock_mode(self):
        """Тест создания интерфейса в мок-режиме"""
        config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
        
        interface = LLMInterfaceFactory.create_interface(config, mock_mode=True)
        
        assert isinstance(interface, MockLLMInterface)
    
    def test_create_interface_openai(self):
        """Тест создания OpenAI интерфейса"""
        config = LLMConfig(
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
        
        interface = LLMInterfaceFactory.create_interface(config, mock_mode=False)
        
        assert isinstance(interface, OpenAIInterface)
        assert interface.config == config
    
    def test_create_interface_openai_compatible(self):
        """Тест создания OpenAI-совместимого интерфейса"""
        config = LLMConfig(
            api_key="test-key",
            base_url="https://custom-api.com/v1"
        )
        
        interface = LLMInterfaceFactory.create_interface(config, mock_mode=False)
        
        assert isinstance(interface, OpenAIInterface)
        assert interface.config == config


class TestLLMRequestBuilder:
    """Тесты для LLMRequestBuilder"""
    
    def test_initialization(self):
        """Тест инициализации построителя"""
        builder = LLMRequestBuilder()
        
        assert builder.default_model == "gpt-4"
        assert builder.default_temperature == 0.7
        assert builder.system_message is None
        assert builder.context is None
        assert builder.metadata is None
    
    def test_with_model(self):
        """Тест установки модели"""
        builder = LLMRequestBuilder().with_model("gpt-3.5-turbo")
        
        assert builder.default_model == "gpt-3.5-turbo"
    
    def test_with_temperature(self):
        """Тест установки температуры"""
        builder = LLMRequestBuilder().with_temperature(0.5)
        
        assert builder.default_temperature == 0.5
    
    def test_with_system_message(self):
        """Тест установки системного сообщения"""
        builder = LLMRequestBuilder().with_system_message("You are a helpful assistant")
        
        assert builder.system_message == "You are a helpful assistant"
    
    def test_with_context(self):
        """Тест установки контекста"""
        context = {"key": "value"}
        builder = LLMRequestBuilder().with_context(context)
        
        assert builder.context == context
    
    def test_with_metadata(self):
        """Тест установки метаданных"""
        metadata = {"request_id": "123"}
        builder = LLMRequestBuilder().with_metadata(metadata)
        
        assert builder.metadata == metadata
    
    def test_chaining(self):
        """Тест цепочки вызовов"""
        builder = (LLMRequestBuilder()
                  .with_model("gpt-3.5-turbo")
                  .with_temperature(0.5)
                  .with_system_message("Test system")
                  .with_context({"key": "value"})
                  .with_metadata({"id": "123"}))
        
        assert builder.default_model == "gpt-3.5-turbo"
        assert builder.default_temperature == 0.5
        assert builder.system_message == "Test system"
        assert builder.context == {"key": "value"}
        assert builder.metadata == {"id": "123"}
    
    def test_build(self):
        """Тест построения запроса"""
        builder = (LLMRequestBuilder()
                  .with_model("gpt-3.5-turbo")
                  .with_temperature(0.5)
                  .with_system_message("Test system")
                  .with_context({"key": "value"})
                  .with_metadata({"id": "123"}))
        
        request = builder.build("Test prompt", max_tokens=1000)
        
        assert isinstance(request, LLMRequest)
        assert request.prompt == "Test prompt"
        assert request.model == "gpt-3.5-turbo"
        assert request.temperature == 0.5
        assert request.max_tokens == 1000
        assert request.system_message == "Test system"
        assert request.context == {"key": "value"}
        assert request.metadata == {"id": "123"}
    
    def test_build_default_values(self):
        """Тест построения запроса со значениями по умолчанию"""
        builder = LLMRequestBuilder()
        request = builder.build("Test prompt")
        
        assert request.prompt == "Test prompt"
        assert request.model == "gpt-4"
        assert request.temperature == 0.7
        assert request.max_tokens == 2000
        assert request.system_message is None
        assert request.context is None
        assert request.metadata is None


if __name__ == "__main__":
    pytest.main([__file__])
