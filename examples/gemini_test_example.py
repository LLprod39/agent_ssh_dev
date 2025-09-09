#!/usr/bin/env python3
"""
Тестовый пример использования Google Gemini с новым API
"""

import os
import sys
from pathlib import Path

# Добавляем путь к src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.agent_config import LLMConfig
from models.llm_interface import LLMInterfaceFactory, LLMRequest
from utils.logger import StructuredLogger


def test_gemini_direct():
    """Прямой тест нового API Gemini"""
    print("=== Прямой тест нового API Gemini ===")
    
    try:
        from google import genai
        
        # Устанавливаем API ключ
        os.environ['GEMINI_API_KEY'] = "AIzaSyDGBAljOf_M5vZr8FhICnoH6w8ij4a87OQ"
        
        # Создаем клиент
        client = genai.Client()
        
        # Тестируем генерацию контента
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents="Объясни как работает ИИ в нескольких словах на русском языке"
        )
        
        print(f"Ответ от Gemini: {response.text}")
        print("✅ Прямой тест успешен!")
        
    except Exception as e:
        print(f"❌ Ошибка в прямом тесте: {e}")
        import traceback
        traceback.print_exc()


def test_gemini_interface():
    """Тест через наш интерфейс"""
    print("\n=== Тест через GeminiInterface ===")
    
    try:
        # Создаем конфигурацию
        config = LLMConfig(
            api_key="AIzaSyDGBAljOf_M5vZr8FhICnoH6w8ij4a87OQ",
            model="gemini-2.5-flash",
            provider="gemini",
            max_tokens=1000,
            temperature=0.7,
            timeout=60
        )
        
        # Создаем логгер
        logger = StructuredLogger("GeminiTest")
        
        # Создаем интерфейс
        llm_interface = LLMInterfaceFactory.create_interface(config, logger)
        
        # Проверяем доступность
        if not llm_interface.is_available():
            print("❌ Gemini API недоступен")
            return
        
        print("✅ Gemini API доступен!")
        
        # Тестируем простой запрос
        request = LLMRequest(
            prompt="Создай простой план установки Docker на Ubuntu",
            model="gemini-2.5-flash",
            temperature=0.3,
            max_tokens=500,
            system_message="Ты эксперт по DevOps. Отвечай на русском языке."
        )
        
        response = llm_interface.generate_response(request)
        
        if response.success:
            print("✅ Успешный ответ от Gemini:")
            print(f"Длительность: {response.duration:.2f} сек")
            print(f"Использование токенов: {response.usage}")
            print("\n" + "="*50)
            print("ОТВЕТ ОТ GEMINI:")
            print("="*50)
            print(response.content)
            print("="*50)
        else:
            print(f"❌ Ошибка при запросе к Gemini: {response.error}")
        
    except Exception as e:
        print(f"❌ Ошибка в тесте интерфейса: {e}")
        import traceback
        traceback.print_exc()


def test_task_planning():
    """Тест планирования задач"""
    print("\n=== Тест планирования задач ===")
    
    try:
        # Создаем конфигурацию
        config = LLMConfig(
            api_key="AIzaSyDGBAljOf_M5vZr8FhICnoH6w8ij4a87OQ",
            model="gemini-2.5-flash",
            provider="gemini",
            max_tokens=2000,
            temperature=0.3,
            timeout=60
        )
        
        # Создаем логгер
        logger = StructuredLogger("TaskPlanningTest")
        
        # Создаем интерфейс
        llm_interface = LLMInterfaceFactory.create_interface(config, logger)
        
        # Тестируем планирование задачи
        request = LLMRequest(
            prompt="""
            Создай детальный план для настройки веб-сервера Nginx на Ubuntu 22.04.
            Включи следующие этапы:
            1. Обновление системы
            2. Установка Nginx
            3. Настройка конфигурации
            4. Настройка SSL
            5. Запуск и проверка
            
            Ответь в формате JSON с полями: title, description, steps (массив шагов с командами).
            """,
            model="gemini-2.5-flash",
            temperature=0.3,
            max_tokens=2000,
            system_message="Ты эксперт по системному администрированию Linux. Отвечай на русском языке в формате JSON."
        )
        
        response = llm_interface.generate_response(request)
        
        if response.success:
            print("✅ Успешное планирование задачи:")
            print(f"Длительность: {response.duration:.2f} сек")
            print("\n" + "="*50)
            print("ПЛАН ЗАДАЧИ:")
            print("="*50)
            print(response.content)
            print("="*50)
        else:
            print(f"❌ Ошибка при планировании: {response.error}")
        
    except Exception as e:
        print(f"❌ Ошибка в тесте планирования: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Основная функция"""
    print("🚀 Тестирование Google Gemini с новым API")
    print("=" * 60)
    
    # Тест 1: Прямой API
    test_gemini_direct()
    
    # Тест 2: Через наш интерфейс
    test_gemini_interface()
    
    # Тест 3: Планирование задач
    test_task_planning()
    
    print("\n" + "=" * 60)
    print("🏁 Тестирование завершено!")


if __name__ == "__main__":
    main()
