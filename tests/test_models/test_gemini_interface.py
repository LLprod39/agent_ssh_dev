"""
Тесты для GeminiInterface
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Добавляем путь к src
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.config.agent_config import LLMConfig
from src.models.llm_interface import GeminiInterface, LLMRequest, LLMResponse, GEMINI_AVAILABLE
from src.utils.logger import StructuredLogger


class TestGeminiInterface:
    """Тесты для GeminiInterface"""
    
    def setup_method(self):
        """Настройка для каждого теста"""
        self.config = LLMConfig(
            api_key="test-gemini-key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-pro",
            provider="gemini",
            max_tokens=1000,
            temperature=0.7,
            timeout=60
        )
        self.logger = StructuredLogger("TestGemini")
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    @patch('os.environ', {})
    def test_gemini_interface_initialization(self, mock_genai, mock_os_env):
        """Тест инициализации GeminiInterface"""
        mock_client = Mock()
        mock_genai.Client.return_value = mock_client
        
        interface = GeminiInterface(self.config, self.logger)
        
        assert interface.config == self.config
        assert interface.api_key == "test-gemini-key"
        assert interface.timeout == 60
        assert interface.client == mock_client
        mock_genai.Client.assert_called_once()
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', False)
    def test_gemini_interface_import_error(self):
        """Тест ошибки импорта при отсутствии google-generativeai"""
        with pytest.raises(ImportError, match="google-generativeai не установлен"):
            GeminiInterface(self.config, self.logger)
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    @patch('os.environ', {})
    def test_generate_response_success(self, mock_genai, mock_os_env):
        """Тест успешной генерации ответа"""
        # Настройка моков
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Тестовый ответ от Gemini"
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        interface = GeminiInterface(self.config, self.logger)
        
        request = LLMRequest(
            prompt="Тестовый промт",
            model="gemini-2.5-flash",
            temperature=0.5,
            max_tokens=500
        )
        
        response = interface.generate_response(request)
        
        assert response.success is True
        assert response.content == "Тестовый ответ от Gemini"
        assert response.model == "gemini-2.5-flash"
        assert response.duration is not None
        
        # Проверяем вызовы
        mock_client.models.generate_content.assert_called_once()
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    @patch('os.environ', {})
    def test_generate_response_empty_response(self, mock_genai, mock_os_env):
        """Тест обработки пустого ответа"""
        # Настройка моков
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        interface = GeminiInterface(self.config, self.logger)
        
        request = LLMRequest(
            prompt="Тестовый промт",
            model="gemini-2.5-flash"
        )
        
        response = interface.generate_response(request)
        
        assert response.success is False
        assert "Пустой ответ от Gemini" in response.error
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    @patch('os.environ', {})
    def test_generate_response_exception(self, mock_genai, mock_os_env):
        """Тест обработки исключения"""
        # Настройка моков
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("Ошибка API")
        mock_genai.Client.return_value = mock_client
        
        interface = GeminiInterface(self.config, self.logger)
        
        request = LLMRequest(
            prompt="Тестовый промт",
            model="gemini-2.5-flash"
        )
        
        response = interface.generate_response(request)
        
        assert response.success is False
        assert "Ошибка при запросе к Gemini" in response.error
        assert "Ошибка API" in response.error
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    @patch('os.environ', {})
    def test_is_available_true(self, mock_genai, mock_os_env):
        """Тест проверки доступности - доступен"""
        # Настройка моков
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "test"
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        interface = GeminiInterface(self.config, self.logger)
        
        result = interface.is_available()
        
        assert result is True
        mock_client.models.generate_content.assert_called_with(
            model="gemini-2.5-flash",
            contents="test",
            config={"max_output_tokens": 1}
        )
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    @patch('os.environ', {})
    def test_is_available_false(self, mock_genai, mock_os_env):
        """Тест проверки доступности - недоступен"""
        # Настройка моков
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception("API недоступен")
        mock_genai.Client.return_value = mock_client
        
        interface = GeminiInterface(self.config, self.logger)
        
        result = interface.is_available()
        
        assert result is False
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', False)
    def test_is_available_no_import(self):
        """Тест проверки доступности - нет импорта"""
        interface = GeminiInterface.__new__(GeminiInterface)
        interface.logger = self.logger
        
        result = interface.is_available()
        
        assert result is False
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    def test_build_prompt(self, mock_genai):
        """Тест построения промта"""
        interface = GeminiInterface(self.config, self.logger)
        
        request = LLMRequest(
            prompt="Основной запрос",
            model="gemini-pro",
            system_message="Системное сообщение",
            context={"key1": "value1", "key2": {"nested": "value"}}
        )
        
        prompt = interface._build_prompt(request)
        
        assert "Система: Системное сообщение" in prompt
        assert "Контекст:" in prompt
        assert "key1: value1" in prompt
        assert "key2: {\n  \"nested\": \"value\"\n}" in prompt
        assert "Запрос: Основной запрос" in prompt
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    def test_format_context(self, mock_genai):
        """Тест форматирования контекста"""
        interface = GeminiInterface(self.config, self.logger)
        
        context = {
            "simple": "value",
            "complex": {"nested": "data"},
            "list": [1, 2, 3]
        }
        
        formatted = interface._format_context(context)
        
        assert "simple: value" in formatted
        assert "complex: {\n  \"nested\": \"data\"\n}" in formatted
        assert "list: [\n  1,\n  2,\n  3\n]" in formatted
    
    @patch('src.models.llm_interface.GEMINI_AVAILABLE', True)
    @patch('src.models.llm_interface.genai')
    def test_extract_usage(self, mock_genai):
        """Тест извлечения информации об использовании токенов"""
        interface = GeminiInterface(self.config, self.logger)
        
        # Тест без usage_metadata
        mock_response = Mock()
        mock_response.usage_metadata = None
        
        usage = interface._extract_usage(mock_response)
        
        assert usage["total_tokens"] == 0
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        
        # Тест с usage_metadata
        mock_usage_metadata = Mock()
        mock_usage_metadata.total_token_count = 100
        mock_usage_metadata.prompt_token_count = 50
        mock_usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata = mock_usage_metadata
        
        usage = interface._extract_usage(mock_response)
        
        assert usage["total_tokens"] == 100
        assert usage["prompt_tokens"] == 50
        assert usage["completion_tokens"] == 50


class TestGeminiInterfaceIntegration:
    """Интеграционные тесты для GeminiInterface"""
    
    @pytest.mark.skipif(not GEMINI_AVAILABLE, reason="google-generativeai не установлен")
    def test_real_gemini_connection(self):
        """Тест реального подключения к Gemini (требует API ключ)"""
        # Этот тест запускается только если установлен google-generativeai
        # и предоставлен реальный API ключ
        api_key = "AIzaSyDGBAljOf_M5vZr8FhICnoH6w8ij4a87OQ"
        if not api_key:
            pytest.skip("GEMINI_API_KEY не установлен")
        
        config = LLMConfig(
            api_key=api_key,
            model="gemini-2.5-flash",
            provider="gemini",
            max_tokens=100,
            temperature=0.1
        )
        
        interface = GeminiInterface(config)
        
        # Проверяем доступность
        assert interface.is_available()
        
        # Тестируем простой запрос
        request = LLMRequest(
            prompt="Скажи 'Привет' на русском языке",
            model="gemini-2.5-flash",
            max_tokens=50
        )
        
        response = interface.generate_response(request)
        
        assert response.success
        assert response.content is not None
        assert len(response.content) > 0
