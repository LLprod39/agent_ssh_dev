# Makefile для SSH Agent проекта

.PHONY: help install test test-unit test-integration test-error test-all test-coverage lint format clean

# Цвета для вывода
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[1;33m
BLUE=\033[0;34m
NC=\033[0m # No Color

help: ## Показать справку
	@echo "$(BLUE)SSH Agent - Доступные команды:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Установить зависимости
	@echo "$(YELLOW)Установка зависимостей...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)Зависимости установлены!$(NC)"

test: test-unit ## Запустить unit тесты (по умолчанию)

test-unit: ## Запустить unit тесты
	@echo "$(YELLOW)Запуск unit тестов...$(NC)"
	python -m pytest -m unit -v tests/test_agents/ tests/test_connectors/ tests/test_models/ tests/test_utils/
	@echo "$(GREEN)Unit тесты завершены!$(NC)"

test-integration: ## Запустить интеграционные тесты
	@echo "$(YELLOW)Запуск интеграционных тестов...$(NC)"
	python -m pytest -m integration -v tests/test_integration/
	@echo "$(GREEN)Интеграционные тесты завершены!$(NC)"

test-error: ## Запустить тесты сценариев ошибок
	@echo "$(YELLOW)Запуск тестов сценариев ошибок...$(NC)"
	python -m pytest -m error_scenarios -v tests/test_error_scenarios/
	@echo "$(GREEN)Тесты сценариев ошибок завершены!$(NC)"

test-all: ## Запустить все тесты
	@echo "$(YELLOW)Запуск всех тестов...$(NC)"
	python -m pytest -v tests/
	@echo "$(GREEN)Все тесты завершены!$(NC)"

test-coverage: ## Запустить тесты с покрытием кода
	@echo "$(YELLOW)Запуск тестов с покрытием кода...$(NC)"
	python -m pytest --cov=src --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml --cov-fail-under=80 tests/
	@echo "$(GREEN)Тесты с покрытием завершены!$(NC)"
	@echo "$(BLUE)HTML отчет: htmlcov/index.html$(NC)"

test-fast: ## Запустить быстрые тесты (без медленных)
	@echo "$(YELLOW)Запуск быстрых тестов...$(NC)"
	python -m pytest -v -m "not slow" tests/
	@echo "$(GREEN)Быстрые тесты завершены!$(NC)"

test-parallel: ## Запустить тесты параллельно
	@echo "$(YELLOW)Запуск тестов параллельно...$(NC)"
	python -m pytest -n auto -v tests/
	@echo "$(GREEN)Параллельные тесты завершены!$(NC)"

lint: ## Проверить код линтерами
	@echo "$(YELLOW)Проверка кода линтерами...$(NC)"
	flake8 src/ tests/
	pylint src/
	@echo "$(GREEN)Проверка линтерами завершена!$(NC)"

format: ## Форматировать код
	@echo "$(YELLOW)Форматирование кода...$(NC)"
	black src/ tests/
	isort src/ tests/
	@echo "$(GREEN)Код отформатирован!$(NC)"

clean: ## Очистить временные файлы
	@echo "$(YELLOW)Очистка временных файлов...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .pytest_cache/
	@echo "$(GREEN)Очистка завершена!$(NC)"

setup-dev: install ## Настроить среду разработки
	@echo "$(YELLOW)Настройка среды разработки...$(NC)"
	pip install -r requirements.txt
	pip install black isort flake8 pylint pytest-cov pytest-xdist
	@echo "$(GREEN)Среда разработки настроена!$(NC)"

ci: test-coverage lint ## Запустить CI pipeline
	@echo "$(GREEN)CI pipeline завершен успешно!$(NC)"

# Специальные команды для отладки
test-debug: ## Запустить тесты в режиме отладки
	@echo "$(YELLOW)Запуск тестов в режиме отладки...$(NC)"
	python -m pytest -v -s --tb=long tests/

test-specific: ## Запустить конкретный тест (использование: make test-specific TEST=test_name)
	@echo "$(YELLOW)Запуск теста: $(TEST)$(NC)"
	python -m pytest -v -k "$(TEST)" tests/

# Команды для документации
docs: ## Сгенерировать документацию
	@echo "$(YELLOW)Генерация документации...$(NC)"
	# Добавить команды для генерации документации
	@echo "$(GREEN)Документация сгенерирована!$(NC)"

# Команды для безопасности
security: ## Проверить безопасность
	@echo "$(YELLOW)Проверка безопасности...$(NC)"
	bandit -r src/
	safety check
	@echo "$(GREEN)Проверка безопасности завершена!$(NC)"

# Команды для производительности
benchmark: ## Запустить бенчмарки
	@echo "$(YELLOW)Запуск бенчмарков...$(NC)"
	python -m pytest -m performance -v tests/
	@echo "$(GREEN)Бенчмарки завершены!$(NC)"
