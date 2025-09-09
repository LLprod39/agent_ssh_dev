#!/usr/bin/env python3
"""
Пример использования Google Gemini в SSH Agent
"""

import os
import sys
from pathlib import Path

# Добавляем путь к src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.agent_config import AgentConfig
from models.llm_interface import LLMInterfaceFactory, LLMRequest
from utils.logger import StructuredLogger


def main():
    """Основная функция для демонстрации работы с Gemini"""
    
    # Создаем логгер
    logger = StructuredLogger("GeminiExample")
    
    try:
        # Загружаем конфигурацию для Gemini
        config_path = Path(__file__).parent.parent / "config" / "agent_config_gemini.yaml.example"
        
        if not config_path.exists():
            logger.error(f"Файл конфигурации не найден: {config_path}")
            return
        
        # Создаем конфигурацию
        config = AgentConfig.from_yaml(str(config_path))
        
        # Проверяем API ключ
        if config.llm.api_key == "your-gemini-api-key-here":
            logger.warning("Необходимо установить реальный API ключ Gemini в конфигурации")
            logger.info("Получите API ключ на: https://makersuite.google.com/app/apikey")
            return
        
        logger.info("Создание интерфейса Gemini...")
        
        # Создаем интерфейс LLM
        llm_interface = LLMInterfaceFactory.create_interface(
            config.llm,
            logger,
            mock_mode=False
        )
        
        # Проверяем доступность
        if not llm_interface.is_available():
            logger.error("Gemini API недоступен")
            return
        
        logger.info("Gemini API доступен!")
        
        # Тестируем планирование задачи
        logger.info("Тестирование планирования задачи...")
        
        request = LLMRequest(
            prompt="""
            Создай план для установки и настройки веб-сервера Nginx на Ubuntu 22.04.
            Включи следующие шаги:
            1. Обновление системы
            2. Установка Nginx
            3. Настройка конфигурации
            4. Запуск и проверка работы
            
            Ответь в формате JSON с полями: title, description, steps (массив шагов).
            """,
            model=config.llm.model,
            temperature=0.3,
            max_tokens=2000,
            system_message="Ты эксперт по системному администрированию Linux. Отвечай на русском языке."
        )
        
        response = llm_interface.generate_response(request)
        
        if response.success:
            logger.info("Успешный ответ от Gemini:")
            logger.info(f"Длительность: {response.duration:.2f} сек")
            logger.info(f"Использование токенов: {response.usage}")
            print("\n" + "="*50)
            print("ОТВЕТ ОТ GEMINI:")
            print("="*50)
            print(response.content)
            print("="*50)
        else:
            logger.error(f"Ошибка при запросе к Gemini: {response.error}")
        
        # Тестируем генерацию команд
        logger.info("Тестирование генерации команд...")
        
        command_request = LLMRequest(
            prompt="""
            Сгенерируй команды для установки Docker на Ubuntu 22.04.
            Включи проверки работоспособности после установки.
            
            Ответь в формате JSON с полями: commands (массив команд), health_checks (массив проверок).
            """,
            model=config.llm.model,
            temperature=0.1,
            max_tokens=1500,
            system_message="Ты эксперт по DevOps и контейнеризации. Отвечай на русском языке."
        )
        
        command_response = llm_interface.generate_response(command_request)
        
        if command_response.success:
            logger.info("Успешная генерация команд:")
            logger.info(f"Длительность: {command_response.duration:.2f} сек")
            print("\n" + "="*50)
            print("КОМАНДЫ ОТ GEMINI:")
            print("="*50)
            print(command_response.content)
            print("="*50)
        else:
            logger.error(f"Ошибка при генерации команд: {command_response.error}")
        
    except Exception as e:
        logger.error(f"Ошибка в примере: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
