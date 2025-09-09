# Примеры использования SSH Agent

## Содержание

1. [Базовые примеры](#базовые-примеры)
2. [Продвинутые сценарии](#продвинутые-сценарии)
3. [Интеграция с существующими системами](#интеграция-с-существующими-системами)
4. [Обработка ошибок](#обработка-ошибок)
5. [Мониторинг и логирование](#мониторинг-и-логирование)

## Базовые примеры

### Простая установка пакета

```python
import asyncio
from src.main import SSHAgent

async def install_package():
    """Установка пакета на сервер"""
    agent = SSHAgent(
        server_config_path="config/server_config.yaml",
        agent_config_path="config/agent_config.yaml"
    )
    
    result = await agent.execute_task("Установить nginx на сервере")
    
    if result["success"]:
        print(f"✅ Nginx установлен за {result['execution_duration']:.2f}с")
        print(f"Выполнено шагов: {result['steps_completed']}/{result['total_steps']}")
    else:
        print(f"❌ Ошибка установки: {result.get('error')}")

asyncio.run(install_package())
```

### Настройка веб-сервера

```python
import asyncio
from src.main import SSHAgent

async def setup_web_server():
    """Настройка веб-сервера с SSL"""
    agent = SSHAgent()
    
    # Сначала dry-run для проверки плана
    dry_run_result = await agent.execute_task(
        "Настроить nginx с SSL сертификатом Let's Encrypt",
        dry_run=True
    )
    
    print(f"План выполнения: {dry_run_result['total_steps']} шагов")
    
    # Реальное выполнение
    result = await agent.execute_task(
        "Настроить nginx с SSL сертификатом Let's Encrypt"
    )
    
    return result

asyncio.run(setup_web_server())
```

### Развертывание приложения

```python
import asyncio
from src.main import SSHAgent

async def deploy_application():
    """Развертывание веб-приложения"""
    agent = SSHAgent()
    
    tasks = [
        "Установить Docker и Docker Compose",
        "Создать директорию для приложения",
        "Настроить nginx как reverse proxy",
        "Запустить приложение в Docker контейнере"
    ]
    
    results = []
    for task in tasks:
        print(f"Выполнение: {task}")
        result = await agent.execute_task(task)
        results.append(result)
        
        if not result["success"]:
            print(f"❌ Провал задачи: {task}")
            break
        else:
            print(f"✅ Задача выполнена: {task}")
    
    return results

asyncio.run(deploy_application())
```

## Продвинутые сценарии

### Автоматическое резервное копирование

```python
import asyncio
from datetime import datetime
from src.main import SSHAgent

async def backup_database():
    """Автоматическое резервное копирование базы данных"""
    agent = SSHAgent()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_task = f"""
    Создать резервную копию PostgreSQL базы данных:
    1. Остановить приложение
    2. Создать дамп базы данных с именем backup_{timestamp}.sql
    3. Сжать дамп в архив backup_{timestamp}.tar.gz
    4. Загрузить архив в S3 bucket
    5. Запустить приложение
    6. Удалить локальные файлы резервной копии
    """
    
    result = await agent.execute_task(backup_task)
    
    if result["success"]:
        print(f"✅ Резервная копия создана: backup_{timestamp}")
    else:
        print(f"❌ Ошибка создания резервной копии: {result.get('error')}")
    
    return result

asyncio.run(backup_database())
```

### Обновление системы

```python
import asyncio
from src.main import SSHAgent

async def system_update():
    """Безопасное обновление системы"""
    agent = SSHAgent()
    
    # Создание снимка состояния перед обновлением
    snapshot_task = """
    Создать снимок состояния системы:
    1. Создать резервную копию конфигураций
    2. Записать список установленных пакетов
    3. Создать снимок файловой системы
    """
    
    snapshot_result = await agent.execute_task(snapshot_task)
    
    if not snapshot_result["success"]:
        print("❌ Не удалось создать снимок состояния")
        return snapshot_result
    
    # Обновление системы
    update_task = """
    Обновить систему:
    1. Обновить список пакетов
    2. Установить обновления безопасности
    3. Обновить ядро системы
    4. Перезагрузить сервер
    """
    
    update_result = await agent.execute_task(update_task)
    
    if update_result["success"]:
        print("✅ Система успешно обновлена")
    else:
        print("❌ Ошибка обновления системы")
        # Здесь можно добавить логику отката
    
    return update_result

asyncio.run(system_update())
```

### Мониторинг и алерты

```python
import asyncio
import time
from src.main import SSHAgent

async def health_check():
    """Проверка состояния системы"""
    agent = SSHAgent()
    
    health_checks = [
        "Проверить использование диска (должно быть < 80%)",
        "Проверить использование памяти (должно быть < 90%)",
        "Проверить статус критических сервисов",
        "Проверить доступность веб-сервера",
        "Проверить логи на наличие ошибок"
    ]
    
    for check in health_checks:
        result = await agent.execute_task(check)
        
        if not result["success"]:
            # Отправка алерта
            alert_task = f"Отправить алерт: {check} - ПРОВАЛ"
            await agent.execute_task(alert_task)
            print(f"🚨 АЛЕРТ: {check}")
        else:
            print(f"✅ OK: {check}")
        
        time.sleep(1)  # Пауза между проверками

asyncio.run(health_check())
```

## Интеграция с существующими системами

### CI/CD Pipeline

```python
import asyncio
import os
from src.main import SSHAgent

async def deploy_from_ci():
    """Развертывание из CI/CD pipeline"""
    agent = SSHAgent()
    
    # Получение переменных окружения из CI
    branch = os.getenv("GIT_BRANCH", "main")
    commit_hash = os.getenv("GIT_COMMIT", "unknown")
    build_number = os.getenv("BUILD_NUMBER", "0")
    
    deploy_task = f"""
    Развернуть приложение из CI/CD:
    1. Остановить текущую версию приложения
    2. Скачать артефакты сборки {build_number}
    3. Проверить целостность файлов
    4. Развернуть новую версию
    5. Запустить миграции базы данных
    6. Запустить приложение
    7. Проверить работоспособность
    8. Обновить символическую ссылку на текущую версию
    """
    
    result = await agent.execute_task(deploy_task)
    
    # Отправка уведомления о результатах
    if result["success"]:
        notification = f"✅ Развертывание успешно: {branch}@{commit_hash}"
    else:
        notification = f"❌ Ошибка развертывания: {branch}@{commit_hash}"
    
    await agent.execute_task(f"Отправить уведомление: {notification}")
    
    return result

asyncio.run(deploy_from_ci())
```

### Интеграция с мониторингом

```python
import asyncio
import json
from src.main import SSHAgent

async def send_metrics_to_monitoring():
    """Отправка метрик в систему мониторинга"""
    agent = SSHAgent()
    
    # Получение метрик системы
    metrics_task = """
    Собрать метрики системы:
    1. CPU usage
    2. Memory usage
    3. Disk usage
    4. Network statistics
    5. Service status
    6. Error logs count
    """
    
    result = await agent.execute_task(metrics_task)
    
    if result["success"]:
        # Отправка метрик в Prometheus/Grafana
        send_metrics_task = """
        Отправить метрики в систему мониторинга:
        1. Форматировать метрики в Prometheus format
        2. Отправить HTTP POST запрос в Pushgateway
        3. Обновить дашборд Grafana
        """
        
        await agent.execute_task(send_metrics_task)
        print("✅ Метрики отправлены в систему мониторинга")
    
    return result

asyncio.run(send_metrics_to_monitoring())
```

## Обработка ошибок

### Обработка сетевых ошибок

```python
import asyncio
import time
from src.main import SSHAgent

async def robust_task_execution():
    """Выполнение задачи с обработкой сетевых ошибок"""
    agent = SSHAgent()
    
    max_retries = 3
    retry_delay = 5  # секунд
    
    task = "Установить пакет, который требует интернет соединение"
    
    for attempt in range(max_retries):
        try:
            result = await agent.execute_task(task)
            
            if result["success"]:
                print(f"✅ Задача выполнена с попытки {attempt + 1}")
                return result
            else:
                print(f"❌ Попытка {attempt + 1} провалена: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Исключение на попытке {attempt + 1}: {e}")
        
        if attempt < max_retries - 1:
            print(f"⏳ Ожидание {retry_delay}с перед следующей попыткой...")
            time.sleep(retry_delay)
    
    print("❌ Все попытки исчерпаны")
    return {"success": False, "error": "Max retries exceeded"}

asyncio.run(robust_task_execution())
```

### Обработка критических ошибок

```python
import asyncio
from src.main import SSHAgent

async def critical_task_with_rollback():
    """Выполнение критической задачи с возможностью отката"""
    agent = SSHAgent()
    
    # Создание точки восстановления
    backup_task = """
    Создать точку восстановления:
    1. Создать снимок текущего состояния
    2. Сохранить конфигурации
    3. Создать резервную копию данных
    """
    
    backup_result = await agent.execute_task(backup_task)
    
    if not backup_result["success"]:
        print("❌ Не удалось создать точку восстановления")
        return backup_result
    
    # Выполнение критической задачи
    critical_task = """
    Выполнить критическое обновление:
    1. Обновить конфигурации
    2. Перезапустить сервисы
    3. Проверить работоспособность
    """
    
    critical_result = await agent.execute_task(critical_task)
    
    if not critical_result["success"]:
        print("❌ Критическая задача провалена, выполняется откат...")
        
        # Откат к предыдущему состоянию
        rollback_task = """
        Выполнить откат:
        1. Восстановить конфигурации из резервной копии
        2. Восстановить данные
        3. Перезапустить сервисы
        4. Проверить работоспособность
        """
        
        rollback_result = await agent.execute_task(rollback_task)
        
        if rollback_result["success"]:
            print("✅ Откат выполнен успешно")
        else:
            print("❌ ОШИБКА ОТКАТА - ТРЕБУЕТСЯ РУЧНОЕ ВМЕШАТЕЛЬСТВО")
        
        return rollback_result
    
    print("✅ Критическая задача выполнена успешно")
    return critical_result

asyncio.run(critical_task_with_rollback())
```

## Мониторинг и логирование

### Детальное логирование

```python
import asyncio
import json
from datetime import datetime
from src.main import SSHAgent

async def detailed_logging_example():
    """Пример с детальным логированием"""
    agent = SSHAgent()
    
    # Получение статуса агента
    status = agent.get_agent_status()
    print(f"Статус агента: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    # Выполнение задачи с логированием
    task = "Установить и настроить мониторинг"
    result = await agent.execute_task(task)
    
    # Детальный анализ результата
    print(f"\n=== Анализ выполнения задачи ===")
    print(f"Задача: {task}")
    print(f"Успешность: {result['success']}")
    print(f"Время выполнения: {result['execution_duration']:.2f}с")
    print(f"Прогресс: {result['progress_percentage']:.1f}%")
    
    if result.get("step_results"):
        print(f"\n=== Результаты шагов ===")
        for i, step_result in enumerate(result["step_results"]):
            print(f"Шаг {i+1}: {step_result['step_id']}")
            print(f"  Успешность: {step_result['success']}")
            print(f"  Ошибок: {step_result.get('error_count', 0)}")
            print(f"  Время: {step_result.get('duration', 0):.2f}с")
    
    # Получение истории выполнения
    history = agent.get_execution_history(5)
    print(f"\n=== История выполнения ===")
    for i, hist in enumerate(history):
        print(f"{i+1}. {hist['task_title']} - {hist['success']} ({hist['duration']:.2f}с)")
    
    return result

asyncio.run(detailed_logging_example())
```

### Создание отчетов

```python
import asyncio
import json
from datetime import datetime
from src.main import SSHAgent

async def generate_execution_report():
    """Генерация отчета о выполнении задач"""
    agent = SSHAgent()
    
    # Получение статистики
    status = agent.get_agent_status()
    history = agent.get_execution_history(0)  # Все записи
    
    # Анализ статистики
    total_tasks = status["agent_stats"]["tasks_executed"]
    completed_tasks = status["agent_stats"]["tasks_completed"]
    failed_tasks = status["agent_stats"]["tasks_failed"]
    success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Создание отчета
    report = {
        "report_date": datetime.now().isoformat(),
        "summary": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": f"{success_rate:.1f}%",
            "total_execution_time": status["agent_stats"]["total_execution_time"],
            "total_errors": status["agent_stats"]["total_errors"],
            "escalations": status["agent_stats"]["escalations"]
        },
        "recent_tasks": history[-10:] if history else [],
        "recommendations": []
    }
    
    # Добавление рекомендаций
    if success_rate < 80:
        report["recommendations"].append("Низкий процент успешности - требуется анализ ошибок")
    
    if status["agent_stats"]["escalations"] > 5:
        report["recommendations"].append("Высокое количество эскалаций - проверить конфигурацию")
    
    if status["agent_stats"]["total_errors"] > 20:
        report["recommendations"].append("Много ошибок - улучшить автокоррекцию")
    
    # Сохранение отчета
    report_filename = f"execution_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Отчет сохранен: {report_filename}")
    print(f"Успешность выполнения: {success_rate:.1f}%")
    
    return report

asyncio.run(generate_execution_report())
```

### Мониторинг в реальном времени

```python
import asyncio
import time
from src.main import SSHAgent

async def real_time_monitoring():
    """Мониторинг выполнения задач в реальном времени"""
    agent = SSHAgent()
    
    # Запуск длительной задачи
    task = "Выполнить длительную операцию с множественными шагами"
    
    # Запуск задачи в фоне
    task_coroutine = agent.execute_task(task)
    
    # Мониторинг прогресса
    while True:
        try:
            # Проверка статуса
            status = agent.get_agent_status()
            current_execution = status["current_execution"]
            
            if current_execution["is_running"]:
                print(f"🔄 Выполняется: {current_execution['task_id']}")
                print(f"📊 Прогресс: {current_execution['progress']:.1f}%")
            else:
                print("⏸️ Нет активных задач")
                break
            
            time.sleep(2)  # Проверка каждые 2 секунды
            
        except KeyboardInterrupt:
            print("\n⏹️ Мониторинг остановлен пользователем")
            break
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
            break
    
    # Ожидание завершения задачи
    result = await task_coroutine
    print(f"✅ Задача завершена: {result['success']}")

asyncio.run(real_time_monitoring())
```

## Полезные утилиты

### Пакетное выполнение задач

```python
import asyncio
from src.main import SSHAgent

async def batch_execution():
    """Пакетное выполнение множественных задач"""
    agent = SSHAgent()
    
    tasks = [
        "Установить nginx",
        "Настроить SSL сертификат",
        "Создать виртуальный хост",
        "Настроить логирование",
        "Запустить nginx"
    ]
    
    results = []
    
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] Выполнение: {task}")
        
        result = await agent.execute_task(task)
        results.append({
            "task": task,
            "result": result
        })
        
        if result["success"]:
            print(f"✅ Задача {i} выполнена успешно")
        else:
            print(f"❌ Задача {i} провалена: {result.get('error')}")
            # Можно прервать выполнение или продолжить
            # break
    
    # Сводка результатов
    successful = sum(1 for r in results if r["result"]["success"])
    print(f"\n📊 Сводка: {successful}/{len(tasks)} задач выполнено успешно")
    
    return results

asyncio.run(batch_execution())
```

### Условное выполнение

```python
import asyncio
from src.main import SSHAgent

async def conditional_execution():
    """Условное выполнение задач на основе проверок"""
    agent = SSHAgent()
    
    # Проверка условий
    checks = [
        ("Проверить, установлен ли nginx", "nginx --version"),
        ("Проверить, запущен ли nginx", "systemctl is-active nginx"),
        ("Проверить, есть ли SSL сертификат", "test -f /etc/ssl/certs/nginx.crt")
    ]
    
    for check_name, check_command in checks:
        print(f"🔍 {check_name}")
        
        check_result = await agent.execute_task(f"Выполнить проверку: {check_command}")
        
        if check_result["success"]:
            print(f"✅ {check_name} - условие выполнено")
        else:
            print(f"❌ {check_name} - условие не выполнено")
            
            # Выполнение действия на основе результата проверки
            if "nginx" in check_name.lower():
                if "установлен" in check_name:
                    print("📦 Устанавливаем nginx...")
                    await agent.execute_task("Установить nginx")
                elif "запущен" in check_name:
                    print("🚀 Запускаем nginx...")
                    await agent.execute_task("Запустить nginx")
            elif "SSL" in check_name:
                print("🔒 Создаем SSL сертификат...")
                await agent.execute_task("Создать SSL сертификат")

asyncio.run(conditional_execution())
```

Эти примеры демонстрируют различные способы использования SSH Agent для автоматизации задач на удаленных серверах. Каждый пример можно адаптировать под конкретные потребности и интегрировать в существующие системы.
