# Руководство по интеграции Google Gemini

Это руководство описывает, как настроить и использовать Google Gemini в качестве провайдера LLM в SSH Agent.

## Содержание

1. [Установка зависимостей](#установка-зависимостей)
2. [Получение API ключа](#получение-api-ключа)
3. [Настройка конфигурации](#настройка-конфигурации)
4. [Использование в коде](#использование-в-коде)
5. [Примеры](#примеры)
6. [Устранение неполадок](#устранение-неполадок)

## Установка зависимостей

### 1. Установка библиотеки Google Generative AI

```bash
pip install google-generativeai>=0.3.0
```

Или установите все зависимости проекта:

```bash
pip install -r requirements.txt
```

### 2. Проверка установки

```python
from google import genai
print("Google Generative AI установлен успешно")
```

## Получение API ключа

### 1. Создание проекта в Google AI Studio

1. Перейдите на [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Войдите в свой Google аккаунт
3. Нажмите "Create API Key"
4. Скопируйте созданный API ключ

### 2. Альтернативный способ через Google Cloud

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите API "Generative Language API"
4. Создайте учетные данные (API ключ)
5. Скопируйте API ключ

## Настройка конфигурации

### 1. Создание конфигурационного файла

Создайте файл `config/agent_config.yaml` на основе примера:

```yaml
llm:
  api_key: "AIzaSyDGBAljOf_M5vZr8FhICnoH6w8ij4a87OQ"
  base_url: "https://generativelanguage.googleapis.com/v1beta"
  model: "gemini-2.5-flash"
  provider: "gemini"
  max_tokens: 4000
  temperature: 0.7
  timeout: 60

agents:
  taskmaster:
    model: "gemini-2.5-flash"
    temperature: 0.7
    max_tokens: 1000
  
  task_agent:
    model: "gemini-2.5-flash"
    temperature: 0.3
    max_tokens: 2000
  
  subtask_agent:
    model: "gemini-2.5-flash"
    temperature: 0.1
    max_tokens: 3000
```

### 2. Переменные окружения (альтернативный способ)

```bash
export GEMINI_API_KEY="ваш-gemini-api-ключ"
```

И в конфигурации:

```yaml
llm:
  api_key: "${GEMINI_API_KEY}"
  provider: "gemini"
  model: "gemini-pro"
```

## Использование в коде

### 1. Базовое использование

```python
from config.agent_config import AgentConfig
from models.llm_interface import LLMInterfaceFactory, LLMRequest

# Загрузка конфигурации
config = AgentConfig.from_yaml("config/agent_config.yaml")

# Создание интерфейса
llm_interface = LLMInterfaceFactory.create_interface(config.llm)

# Создание запроса
request = LLMRequest(
    prompt="Создай план установки Nginx",
    model="gemini-pro",
    temperature=0.3,
    max_tokens=2000
)

# Получение ответа
response = llm_interface.generate_response(request)

if response.success:
    print(response.content)
else:
    print(f"Ошибка: {response.error}")
```

### 2. Использование в агентах

```python
from agents.task_agent import TaskAgent
from config.agent_config import AgentConfig

# Загрузка конфигурации с Gemini
config = AgentConfig.from_yaml("config/agent_config.yaml")

# Создание Task Agent с Gemini
task_agent = TaskAgent(config)

# Планирование задачи
result = task_agent.plan_task("Установить и настроить веб-сервер")
```

## Примеры

### 1. Простой пример

См. файл `examples/gemini_example.py` для полного примера использования.

### 2. Запуск примера

```bash
# Установите API ключ в конфигурации
cp config/agent_config_gemini.yaml.example config/agent_config.yaml
# Отредактируйте config/agent_config.yaml и добавьте ваш API ключ

# Запустите пример
python examples/gemini_example.py
```

### 3. Тестирование

```bash
# Запуск тестов
pytest tests/test_models/test_gemini_interface.py -v

# Запуск с реальным API ключом
GEMINI_API_KEY="ваш-ключ" pytest tests/test_models/test_gemini_interface.py::TestGeminiInterfaceIntegration::test_real_gemini_connection -v
```

## Доступные модели Gemini

### 1. Gemini 2.5 Flash
- **Модель**: `gemini-2.5-flash`
- **Описание**: Быстрая и эффективная модель для большинства задач
- **Рекомендуется для**: Планирования задач, генерации команд, быстрых ответов

### 2. Gemini Pro
- **Модель**: `gemini-pro`
- **Описание**: Основная модель для текстовых задач
- **Рекомендуется для**: Сложного планирования, детального анализа

### 3. Gemini Pro Vision
- **Модель**: `gemini-pro-vision`
- **Описание**: Модель с поддержкой изображений
- **Рекомендуется для**: Анализа скриншотов, работы с изображениями

## Настройка параметров

### 1. Температура
- **0.0-0.3**: Детерминированные ответы, подходит для команд
- **0.3-0.7**: Сбалансированные ответы, подходит для планирования
- **0.7-1.0**: Креативные ответы, подходит для анализа

### 2. Максимальные токены
- **1000-2000**: Короткие ответы, команды
- **2000-4000**: Средние ответы, планы
- **4000+**: Длинные ответы, подробные инструкции

### 3. Таймаут
- **30-60 секунд**: Для быстрых запросов
- **60-120 секунд**: Для сложных задач

## Устранение неполадок

### 1. Ошибка импорта

```
ImportError: google-generativeai не установлен
```

**Решение**: Установите библиотеку:
```bash
pip install google-generativeai>=0.3.0
```

### 2. Ошибка API ключа

```
Ошибка при запросе к Gemini: 403 Forbidden
```

**Решение**: 
- Проверьте правильность API ключа
- Убедитесь, что API ключ активен
- Проверьте квоты в Google AI Studio

### 3. Ошибка модели

```
Ошибка при запросе к Gemini: 400 Bad Request
```

**Решение**:
- Проверьте название модели (`gemini-pro`, `gemini-pro-vision`)
- Убедитесь, что модель доступна в вашем регионе

### 4. Таймаут

```
Ошибка при запросе к Gemini: timeout
```

**Решение**:
- Увеличьте значение `timeout` в конфигурации
- Проверьте стабильность интернет-соединения
- Уменьшите `max_tokens` для более быстрых ответов

### 5. Фильтры безопасности

```
Пустой ответ от Gemini: Фильтр безопасности
```

**Решение**:
- Переформулируйте запрос
- Избегайте потенциально опасных команд
- Используйте более мягкие формулировки

## Лучшие практики

### 1. Обработка ошибок

```python
response = llm_interface.generate_response(request)

if not response.success:
    logger.error(f"Ошибка Gemini: {response.error}")
    # Fallback на другой провайдер или мок
    return fallback_response()
```

### 2. Кэширование

```python
# Используйте кэширование для повторяющихся запросов
cache_key = f"gemini:{hash(request.prompt)}"
if cache_key in cache:
    return cache[cache_key]
```

### 3. Мониторинг

```python
# Логируйте использование токенов
logger.info(f"Gemini usage: {response.usage}")
logger.info(f"Response time: {response.duration:.2f}s")
```

### 4. Безопасность

```python
# Не храните API ключи в коде
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY не установлен")
```

## Сравнение с другими провайдерами

| Параметр | Gemini | OpenAI | Anthropic |
|----------|--------|--------|-----------|
| Скорость | Высокая | Средняя | Средняя |
| Качество | Высокое | Высокое | Высокое |
| Цена | Низкая | Высокая | Средняя |
| Доступность | Ограниченная | Широкая | Ограниченная |
| Поддержка русского | Хорошая | Хорошая | Хорошая |

## Заключение

Google Gemini предоставляет отличную альтернативу OpenAI для использования в SSH Agent. Следуйте этому руководству для успешной интеграции и настройки.
