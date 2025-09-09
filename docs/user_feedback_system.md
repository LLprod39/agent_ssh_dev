# Система обратной связи с пользователем

## Обзор

Система обратной связи с пользователем предоставляет комплексное решение для информирования пользователя о ходе выполнения задач, генерации детальных отчетов и отслеживания временной шкалы выполнения.

## Компоненты системы

### 1. Система уведомлений (NotificationSystem)

Отправляет уведомления пользователю через различные каналы:

- **Консоль** - вывод в терминал с цветовой индикацией
- **Логи** - запись в файлы логов
- **Email** - отправка по электронной почте
- **Webhook** - отправка HTTP запросов
- **Файл** - запись в текстовый файл

#### Типы уведомлений

- `TASK_STARTED` - начало задачи
- `TASK_PROGRESS` - прогресс выполнения
- `TASK_COMPLETED` - успешное завершение
- `TASK_FAILED` - провал задачи
- `STEP_STARTED` - начало шага
- `STEP_COMPLETED` - завершение шага
- `STEP_FAILED` - провал шага
- `ERROR_ESCALATION` - эскалация ошибок
- `HUMAN_ESCALATION` - эскалация к человеку
- `AUTOCORRECTION` - применение автокоррекции
- `SYSTEM_STATUS` - статус системы

### 2. Генератор отчетов (ReportGenerator)

Создает детальные отчеты в различных форматах:

- **JSON** - структурированные данные
- **HTML** - веб-страницы с форматированием
- **Markdown** - документы в формате Markdown
- **CSV** - табличные данные
- **TEXT** - простой текстовый формат

#### Типы отчетов

- `TASK_SUMMARY` - сводный отчет по задаче
- `STEP_DETAILS` - детальный отчет по шагу
- `ERROR_ANALYSIS` - анализ ошибок
- `PERFORMANCE` - отчет производительности
- `TIMELINE` - временная шкала
- `FULL_REPORT` - полный отчет

### 3. Трекер временной шкалы (TimelineTracker)

Отслеживает все события выполнения задач:

- Создание и завершение задач
- Выполнение шагов
- Выполнение команд
- Применение автокоррекции
- Эскалации ошибок
- Системные события

## Конфигурация

### Основная конфигурация

```yaml
user_feedback:
  enabled: true
  log_level: "INFO"
  
  notifications:
    enabled: true
    console:
      enabled: true
    log:
      enabled: true
    email:
      enabled: false
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      username: "your-email@gmail.com"
      password: "your-password"
      from_address: "your-email@gmail.com"
      to_addresses: ["admin@company.com"]
    webhook:
      enabled: false
      url: "https://hooks.slack.com/services/..."
      headers: {}
      timeout: 30
    file:
      enabled: true
      file_path: "notifications.log"
  
  reports:
    enabled: true
    output_dir: "reports"
    formats: ["json", "html", "markdown"]
    include_timeline: true
    include_performance: true
    include_error_analysis: true
  
  timeline:
    enabled: true
    auto_create_segments: true
    max_events_per_task: 1000
    enable_performance_analysis: true
    export_dir: "timeline_exports"
```

## Использование

### Инициализация

```python
from src.utils.user_feedback_system import UserFeedbackSystem, FeedbackConfig

# Создание конфигурации
config = FeedbackConfig(
    notifications={
        "enabled": True,
        "console": {"enabled": True},
        "log": {"enabled": True}
    },
    reports={
        "enabled": True,
        "output_dir": "reports",
        "formats": ["json", "html"]
    },
    timeline={
        "enabled": True,
        "auto_create_segments": True
    }
)

# Инициализация системы
feedback_system = UserFeedbackSystem(config)
```

### Интеграция с выполнением задач

```python
# Начало задачи
task.mark_started()
feedback_system.on_task_started(task)

# Прогресс задачи
feedback_system.on_task_progress(task, completed_steps, current_step)

# Завершение задачи
if success:
    feedback_system.on_task_completed(task, execution_results)
else:
    feedback_system.on_task_failed(task, failure_reason, execution_results)

# Выполнение шага
step.mark_started()
feedback_system.on_step_started(task, step)

# Выполнение команды
feedback_system.on_command_executed(
    task_id=task.task_id,
    step_id=step.step_id,
    command=command,
    success=success,
    duration=duration,
    output=output,
    error=error
)

# Завершение шага
feedback_system.on_step_completed(task, step, duration)
```

### Генерация отчетов

```python
# Создание отчета по задаче
report = feedback_system.generate_task_report(task, execution_results)

# Экспорт отчета
exported_files = feedback_system.report_generator.export_report(report)
print(f"Отчет экспортирован: {exported_files}")

# Создание отчета по шагу
step_report = feedback_system.generate_step_report(task, step_id, step_results)
```

### Работа с временной шкалой

```python
# Получение временной шкалы задачи
timeline = feedback_system.get_task_timeline(task.task_id)

# Экспорт временной шкалы
timeline_file = feedback_system.export_task_timeline(task.task_id, "json")

# Анализ производительности
performance = feedback_system.timeline_tracker.analyze_performance(task.task_id)
```

### Получение уведомлений

```python
# История уведомлений
notifications = feedback_system.get_notification_history(hours=24)

# Статус системы
status = feedback_system.get_system_status()
print(f"Отправлено уведомлений: {status['notifications']['notifications_sent']}")
```

## Шаблоны уведомлений

Система использует настраиваемые шаблоны для различных типов уведомлений:

### Шаблон начала задачи

```
🚀 Задача начата: {task_title}

Задача '{task_title}' начата.
ID задачи: {task_id}
Описание: {task_description}
Количество шагов: {total_steps}
Время начала: {start_time}
Приоритет: {priority}
```

### Шаблон завершения задачи

```
✅ Задача завершена: {task_title}

Задача '{task_title}' успешно завершена!
ID задачи: {task_id}
Общее время выполнения: {total_duration}
Выполнено шагов: {completed_steps}/{total_steps}
Ошибок: {error_count}
Время завершения: {completion_time}
```

### Шаблон эскалации к человеку

```
🚨 КРИТИЧЕСКАЯ ЭСКАЛАЦИЯ: {step_title}

ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО ЧЕЛОВЕКА!
Шаг '{step_title}' требует немедленного внимания.
ID шага: {step_id}
ID задачи: {task_id}
Количество ошибок: {error_count}
Причина: {escalation_reason}
Время эскалации: {escalation_time}
Последние ошибки:
{recent_errors}
Пожалуйста, проверьте систему и примите меры
```

## Форматы отчетов

### JSON отчет

```json
{
  "report_id": "task_summary_demo_task_001_1234567890",
  "report_type": "task_summary",
  "task_id": "demo_task_001",
  "title": "Сводный отчет по задаче: Установка веб-сервера",
  "created_at": "2024-01-15T10:30:00",
  "sections": [
    {
      "section_id": "task_overview",
      "title": "Обзор задачи",
      "content": "# Обзор задачи\n\n**ID задачи:** demo_task_001\n...",
      "order": 1
    }
  ]
}
```

### HTML отчет

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Сводный отчет по задаче: Установка веб-сервера</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        h2 { color: #666; border-bottom: 1px solid #ccc; }
        pre { background: #f5f5f5; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Сводный отчет по задаче: Установка веб-сервера</h1>
    <div class="metadata">
        <p><strong>ID отчета:</strong> task_summary_demo_task_001_1234567890</p>
        <p><strong>Тип отчета:</strong> task_summary</p>
        <p><strong>ID задачи:</strong> demo_task_001</p>
        <p><strong>Создан:</strong> 2024-01-15 10:30:00</p>
    </div>
    <h2>Обзор задачи</h2>
    <div>...</div>
</body>
</html>
```

## Мониторинг и статистика

### Статистика уведомлений

```python
stats = feedback_system.notification_system.get_stats()
print(f"Отправлено уведомлений: {stats['notifications_sent']}")
print(f"Уведомлений по типам: {stats['notifications_by_type']}")
print(f"Уведомлений по приоритетам: {stats['notifications_by_priority']}")
```

### Анализ производительности

```python
performance = feedback_system.timeline_tracker.analyze_performance(task.task_id)
print(f"Общее время выполнения: {performance['total_duration']} сек")
print(f"Успешность команд: {performance['command_stats']['success_rate']:.1f}%")
print(f"Успешность шагов: {performance['step_stats']['success_rate']:.1f}%")
```

## Очистка данных

```python
# Очистка старых данных (по умолчанию 30 дней)
feedback_system.cleanup_old_data(days=30)

# Очистка отдельных компонентов
feedback_system.notification_system.cleanup_old_notifications(days=7)
feedback_system.report_generator.cleanup_old_reports(days=14)
feedback_system.timeline_tracker.cleanup_old_events(days=30)
```

## Примеры использования

### Полный пример

```python
from src.utils.user_feedback_system import UserFeedbackSystem, FeedbackConfig
from src.models.planning_model import Task, TaskStep, Priority

# Создание задачи
task = Task(
    task_id="example_task",
    title="Установка веб-сервера",
    description="Установка и настройка Nginx",
    priority=Priority.HIGH
)

# Добавление шагов
step = TaskStep(
    step_id="step_1",
    title="Установка Nginx",
    description="Установка веб-сервера Nginx"
)
task.add_step(step)

# Инициализация системы обратной связи
config = FeedbackConfig(
    notifications={"enabled": True, "console": {"enabled": True}},
    reports={"enabled": True, "output_dir": "reports"},
    timeline={"enabled": True}
)
feedback_system = UserFeedbackSystem(config)

# Выполнение задачи с обратной связью
task.mark_started()
feedback_system.on_task_started(task)

step.mark_started()
feedback_system.on_step_started(task, step)

# Симуляция выполнения команды
feedback_system.on_command_executed(
    task_id=task.task_id,
    step_id=step.step_id,
    command="apt install nginx -y",
    success=True,
    duration=15.5,
    output="Nginx установлен успешно"
)

step.mark_completed()
feedback_system.on_step_completed(task, step, 15.5)

task.mark_completed()
feedback_system.on_task_completed(task, {"successful_commands": 1})

# Генерация отчета
report = feedback_system.generate_task_report(task, {})
exported_files = feedback_system.report_generator.export_report(report)
print(f"Отчет создан: {exported_files}")
```

## Расширение системы

### Добавление нового типа уведомления

```python
from src.utils.notification_system import NotificationType, NotificationTemplate

# Добавление нового типа
class CustomNotificationType(NotificationType):
    CUSTOM_EVENT = "custom_event"

# Создание шаблона
template = NotificationTemplate(
    template_id="custom_event",
    notification_type=CustomNotificationType.CUSTOM_EVENT,
    priority=NotificationPriority.MEDIUM,
    title_template="Пользовательское событие: {event_name}",
    message_template="Описание: {event_description}",
    channels=[NotificationChannel.CONSOLE, NotificationChannel.LOG]
)

# Регистрация шаблона
notification_system.templates[template.template_id] = template
```

### Добавление нового формата отчета

```python
from src.utils.report_generator import ReportFormat

# Добавление нового формата
class CustomReportFormat(ReportFormat):
    XML = "xml"

# Реализация экспорта
def _export_to_xml(self, report: DetailedReport, file_path: Path):
    # Реализация экспорта в XML
    pass
```

## Лучшие практики

1. **Настройка уведомлений**: Включите только необходимые каналы уведомлений
2. **Очистка данных**: Регулярно очищайте старые данные для экономии места
3. **Мониторинг**: Отслеживайте статистику для выявления проблем
4. **Шаблоны**: Настройте шаблоны уведомлений под ваши нужды
5. **Производительность**: Ограничьте количество событий в временной шкале
6. **Безопасность**: Не передавайте чувствительные данные в уведомления

## Устранение неполадок

### Проблемы с email уведомлениями

- Проверьте настройки SMTP сервера
- Убедитесь в правильности учетных данных
- Проверьте настройки файрвола

### Проблемы с webhook уведомлениями

- Проверьте URL webhook
- Убедитесь в доступности сервера
- Проверьте формат данных

### Проблемы с производительностью

- Уменьшите количество событий в временной шкале
- Отключите ненужные каналы уведомлений
- Регулярно очищайте старые данные

### Проблемы с отчетами

- Проверьте права доступа к директории отчетов
- Убедитесь в наличии свободного места
- Проверьте формат данных в отчетах
