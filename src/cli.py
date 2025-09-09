"""
CLI интерфейс для SSH Agent с LLM интеграцией.

Этот модуль предоставляет командную строку с полным набором команд
для управления SSH Agent.
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
import yaml

from .main import SSHAgent
from .config.server_config import ServerConfig
from .config.agent_config import AgentConfig

console = Console()
app = typer.Typer(
    name="ssh-agent",
    help="SSH Agent с LLM интеграцией для автоматизации задач на удаленных серверах",
    add_completion=False,
    rich_markup_mode="rich"
)

# Глобальные переменные для состояния
current_agent: Optional[SSHAgent] = None
current_config = {
    "server_config_path": "config/server_config.yaml",
    "agent_config_path": "config/agent_config.yaml"
}


def get_agent() -> SSHAgent:
    """Получение текущего агента или создание нового."""
    global current_agent
    if current_agent is None:
        try:
            current_agent = SSHAgent(
                server_config_path=current_config["server_config_path"],
                agent_config_path=current_config["agent_config_path"]
            )
        except Exception as e:
            console.print(f"[red]Ошибка инициализации агента:[/red] {e}")
            raise typer.Exit(1)
    return current_agent


@app.command()
def execute(
    task: str = typer.Argument(..., help="Описание задачи для выполнения"),
    server_config: str = typer.Option(
        "config/server_config.yaml", 
        "--server-config", "-s",
        help="Путь к файлу конфигурации сервера"
    ),
    agent_config: str = typer.Option(
        "config/agent_config.yaml", 
        "--agent-config", "-a",
        help="Путь к файлу конфигурации агента"
    ),
    dry_run: bool = typer.Option(
        False, 
        "--dry-run", "-d",
        help="Показать что будет выполнено без фактического выполнения"
    ),
    verbose: bool = typer.Option(
        False, 
        "--verbose", "-v",
        help="Подробный вывод"
    ),
    interactive: bool = typer.Option(
        False, 
        "--interactive", "-i",
        help="Интерактивный режим подтверждения каждого шага"
    )
):
    """Выполнить задачу на удаленном сервере."""
    
    # Обновляем глобальную конфигурацию
    current_config["server_config_path"] = server_config
    current_config["agent_config_path"] = agent_config
    
    async def _execute():
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
                transient=True
            ) as progress:
                
                # Инициализация агента
                init_task = progress.add_task("Инициализация агента...", total=None)
                agent = SSHAgent(server_config, agent_config)
                progress.update(init_task, description="Агент инициализирован", completed=True)
                
                # Выполнение задачи
                exec_task = progress.add_task("Выполнение задачи...", total=None)
                result = await agent.execute_task(task, dry_run)
                progress.update(exec_task, description="Задача выполнена", completed=True)
            
            # Отображение результата
            if result["success"]:
                console.print(Panel(
                    f"[green]✓ Задача выполнена успешно![/green]\n"
                    f"ID задачи: {result['task_id']}\n"
                    f"Шагов выполнено: {result['steps_completed']}/{result['total_steps']}\n"
                    f"Время выполнения: {result['execution_duration']:.2f}с\n"
                    f"Прогресс: {result['progress_percentage']:.1f}%",
                    title="[green]Успех[/green]",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    f"[red]✗ Задача завершена с ошибками[/red]\n"
                    f"Ошибка: {result.get('error', 'Неизвестная ошибка')}\n"
                    f"Время выполнения: {result.get('execution_duration', 0):.2f}с",
                    title="[red]Ошибка[/red]",
                    border_style="red"
                ))
                
            # Подробный вывод при необходимости
            if verbose and result.get("step_results"):
                _display_detailed_results(result["step_results"])
                
        except Exception as e:
            console.print(Panel(
                f"[red]Критическая ошибка:[/red] {str(e)}",
                title="[red]Критическая ошибка[/red]",
                border_style="red"
            ))
            raise typer.Exit(1)
    
    asyncio.run(_execute())


@app.command()
def interactive():
    """Запустить интерактивный режим."""
    console.print(Panel(
        "[bold blue]SSH Agent - Интерактивный режим[/bold blue]\n\n"
        "[bold]Доступные команды:[/bold]\n"
        "• [cyan]execute <задача>[/cyan] - выполнить задачу\n"
        "• [cyan]dry-run <задача>[/cyan] - предварительный просмотр\n"
        "• [cyan]status[/cyan] - показать статус агента\n"
        "• [cyan]history [количество][/cyan] - показать историю выполнения\n"
        "• [cyan]config[/cyan] - показать текущую конфигурацию\n"
        "• [cyan]cleanup [дни][/cyan] - очистить старые данные\n"
        "• [cyan]help[/cyan] - показать справку\n"
        "• [cyan]exit[/cyan] или [cyan]quit[/cyan] - выход\n\n"
        "[yellow]Пример:[/yellow] execute Установить nginx на сервере",
        title="[blue]SSH Agent Interactive[/blue]",
        border_style="blue"
    ))
    
    agent = None
    
    while True:
        try:
            command = Prompt.ask("\n[bold cyan]SSH Agent[/bold cyan]")
            
            if command.lower() in ['exit', 'quit', 'выход']:
                console.print("[green]До свидания![/green]")
                break
                
            elif command.lower() == 'help' or command.lower() == 'справка':
                _show_interactive_help()
                
            elif command.lower() == 'status' or command.lower() == 'статус':
                _show_agent_status(agent)
                
            elif command.lower().startswith('history') or command.lower().startswith('история'):
                _show_execution_history(agent, command)
                
            elif command.lower() == 'config' or command.lower() == 'конфиг':
                _show_current_config()
                
            elif command.lower().startswith('cleanup') or command.lower().startswith('очистка'):
                _cleanup_old_data(agent, command)
                
            elif command.lower().startswith('dry-run') or command.lower().startswith('просмотр'):
                _execute_dry_run(agent, command)
                
            elif command.lower().startswith('execute') or command.lower().startswith('выполнить'):
                _execute_task_interactive(agent, command)
                
            else:
                # Попытка выполнить как задачу
                if command.strip():
                    _execute_task_interactive(agent, f"execute {command}")
                else:
                    console.print("[yellow]Введите команду или описание задачи[/yellow]")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Используйте 'exit' для выхода[/yellow]")
        except Exception as e:
            console.print(f"[red]Ошибка:[/red] {e}")


@app.command()
def status(
    server_config: str = typer.Option(
        "config/server_config.yaml", 
        "--server-config", "-s",
        help="Путь к файлу конфигурации сервера"
    ),
    agent_config: str = typer.Option(
        "config/agent_config.yaml", 
        "--agent-config", "-a",
        help="Путь к файлу конфигурации агента"
    )
):
    """Показать статус агента и статистику."""
    try:
        agent = SSHAgent(server_config, agent_config)
        status = agent.get_agent_status()
        
        # Основная статистика
        stats_table = Table(title="[bold green]Статистика агента[/bold green]")
        stats_table.add_column("Метрика", style="cyan")
        stats_table.add_column("Значение", style="white")
        
        stats_table.add_row("Задач выполнено", str(status['agent_stats']['tasks_executed']))
        stats_table.add_row("Задач завершено", str(status['agent_stats']['tasks_completed']))
        stats_table.add_row("Задач провалено", str(status['agent_stats']['tasks_failed']))
        stats_table.add_row("Общее время выполнения", f"{status['agent_stats']['total_execution_time']:.2f}с")
        stats_table.add_row("Общее количество ошибок", str(status['agent_stats']['total_errors']))
        stats_table.add_row("Эскалаций", str(status['agent_stats']['escalations']))
        stats_table.add_row("Записей в истории", str(status['execution_history_count']))
        
        console.print(stats_table)
        
        # Статус компонентов
        components_table = Table(title="[bold blue]Статус компонентов[/bold blue]")
        components_table.add_column("Компонент", style="cyan")
        components_table.add_column("Статус", style="white")
        
        components = status['components_status']
        for name, is_available in components.items():
            status_text = "[green]✓ Доступен[/green]" if is_available else "[red]✗ Недоступен[/red]"
            components_table.add_row(name.replace('_', ' ').title(), status_text)
        
        console.print(components_table)
        
        # Текущее выполнение
        current_exec = status['current_execution']
        if current_exec['is_running']:
            console.print(Panel(
                f"ID задачи: {current_exec['task_id']}\n"
                f"Прогресс: {current_exec['progress']:.1f}%",
                title="[yellow]Текущее выполнение[/yellow]",
                border_style="yellow"
            ))
        else:
            console.print("[dim]Текущее выполнение: Неактивно[/dim]")
        
    except Exception as e:
        console.print(Panel(
            f"[red]Ошибка получения статуса:[/red] {str(e)}",
            title="[red]Ошибка[/red]",
            border_style="red"
        ))
        raise typer.Exit(1)


@app.command()
def history(
    limit: int = typer.Option(
        10, 
        "--limit", "-l",
        help="Количество последних выполнений для показа"
    ),
    server_config: str = typer.Option(
        "config/server_config.yaml", 
        "--server-config", "-s",
        help="Путь к файлу конфигурации сервера"
    ),
    agent_config: str = typer.Option(
        "config/agent_config.yaml", 
        "--agent-config", "-a",
        help="Путь к файлу конфигурации агента"
    )
):
    """Показать историю выполнения задач."""
    try:
        agent = SSHAgent(server_config, agent_config)
        history = agent.get_execution_history(limit)
        
        if history:
            history_table = Table(title=f"[bold blue]История выполнения (последние {len(history)} задач)[/bold blue]")
            history_table.add_column("№", style="dim", width=3)
            history_table.add_column("Задача", style="cyan", width=30)
            history_table.add_column("ID", style="dim", width=10)
            history_table.add_column("Шаги", style="white", width=8)
            history_table.add_column("Ошибки", style="red", width=7)
            history_table.add_column("Время", style="green", width=8)
            history_table.add_column("Статус", style="white", width=8)
            history_table.add_column("Dry-run", style="yellow", width=8)
            
            for i, h in enumerate(history, 1):
                status_icon = "[green]✓[/green]" if h['success'] else "[red]✗[/red]"
                dry_run_icon = "[yellow]Да[/yellow]" if h['is_dry_run'] else "[dim]Нет[/dim]"
                
                history_table.add_row(
                    str(i),
                    h['task_title'][:27] + "..." if len(h['task_title']) > 30 else h['task_title'],
                    h['task_id'][:8] + "...",
                    f"{h['completed_steps']}/{h['total_steps']}",
                    str(h['error_count']),
                    f"{h['duration']:.1f}с",
                    status_icon,
                    dry_run_icon
                )
            
            console.print(history_table)
        else:
            console.print(Panel(
                "История выполнения пуста",
                title="[yellow]История выполнения[/yellow]",
                border_style="yellow"
            ))
            
    except Exception as e:
        console.print(Panel(
            f"[red]Ошибка получения истории:[/red] {str(e)}",
            title="[red]Ошибка[/red]",
            border_style="red"
        ))
        raise typer.Exit(1)


@app.command()
def cleanup(
    days: int = typer.Option(
        7, 
        "--days", "-d",
        help="Количество дней для хранения данных"
    ),
    server_config: str = typer.Option(
        "config/server_config.yaml", 
        "--server-config", "-s",
        help="Путь к файлу конфигурации сервера"
    ),
    agent_config: str = typer.Option(
        "config/agent_config.yaml", 
        "--agent-config", "-a",
        help="Путь к файлу конфигурации агента"
    ),
    confirm: bool = typer.Option(
        False, 
        "--yes", "-y",
        help="Подтвердить очистку без запроса"
    )
):
    """Очистить старые данные."""
    try:
        if not confirm:
            if not Confirm.ask(f"Удалить данные старше {days} дней?"):
                console.print("[yellow]Очистка отменена[/yellow]")
                return
        
        agent = SSHAgent(server_config, agent_config)
        agent.cleanup_old_data(days)
        
        console.print(Panel(
            f"[green]✓ Очистка старых данных завершена[/green]\n"
            f"Удалены данные старше {days} дней",
            title="[green]Очистка данных[/green]",
            border_style="green"
        ))
        
    except Exception as e:
        console.print(Panel(
            f"[red]Ошибка очистки данных:[/red] {str(e)}",
            title="[red]Ошибка[/red]",
            border_style="red"
        ))
        raise typer.Exit(1)


@app.command()
def config(
    action: str = typer.Argument(..., help="Действие: show, validate, edit"),
    server_config: str = typer.Option(
        "config/server_config.yaml", 
        "--server-config", "-s",
        help="Путь к файлу конфигурации сервера"
    ),
    agent_config: str = typer.Option(
        "config/agent_config.yaml", 
        "--agent-config", "-a",
        help="Путь к файлу конфигурации агента"
    )
):
    """Управление конфигурацией."""
    if action == "show":
        _show_config_files(server_config, agent_config)
    elif action == "validate":
        _validate_config_files(server_config, agent_config)
    elif action == "edit":
        _edit_config_files(server_config, agent_config)
    else:
        console.print(f"[red]Неизвестное действие:[/red] {action}")
        console.print("[yellow]Доступные действия: show, validate, edit[/yellow]")
        raise typer.Exit(1)


@app.command()
def init(
    server_config: str = typer.Option(
        "config/server_config.yaml", 
        "--server-config", "-s",
        help="Путь к файлу конфигурации сервера"
    ),
    agent_config: str = typer.Option(
        "config/agent_config.yaml", 
        "--agent-config", "-a",
        help="Путь к файлу конфигурации агента"
    )
):
    """Инициализировать файлы конфигурации SSH Agent."""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Создание server_config.yaml
    server_config_path = Path(server_config)
    if not server_config_path.exists():
        example_path = Path("config/server_config.yaml.example")
        if example_path.exists():
            server_config_path.write_text(example_path.read_text())
            console.print(f"[green]✓ Создан[/green] {server_config_path}")
        else:
            _create_default_server_config(server_config_path)
            console.print(f"[green]✓ Создан[/green] {server_config_path}")
    
    # Создание agent_config.yaml
    agent_config_path = Path(agent_config)
    if not agent_config_path.exists():
        example_path = Path("config/agent_config.yaml.example")
        if example_path.exists():
            agent_config_path.write_text(example_path.read_text())
            console.print(f"[green]✓ Создан[/green] {agent_config_path}")
        else:
            _create_default_agent_config(agent_config_path)
            console.print(f"[green]✓ Создан[/green] {agent_config_path}")
    
    console.print(Panel(
        "[green]✓ Файлы конфигурации созданы успешно![/green]\n\n"
        "[bold]Следующие шаги:[/bold]\n"
        "1. Отредактируйте [cyan]config/server_config.yaml[/cyan] с данными вашего сервера\n"
        "2. Отредактируйте [cyan]config/agent_config.yaml[/cyan] с вашими API ключами\n"
        "3. Запустите [cyan]ssh-agent config validate[/cyan] для проверки конфигурации\n"
        "4. Выполните [cyan]ssh-agent execute 'тестовая задача' --dry-run[/cyan] для проверки",
        title="[green]Инициализация завершена[/green]",
        border_style="green"
    ))


# Вспомогательные функции для интерактивного режима

def _show_interactive_help():
    """Показать справку в интерактивном режиме."""
    console.print(Panel(
        "[bold]Доступные команды:[/bold]\n\n"
        "[cyan]execute <задача>[/cyan] - выполнить задачу на сервере\n"
        "[cyan]dry-run <задача>[/cyan] - показать план выполнения без выполнения\n"
        "[cyan]status[/cyan] - показать статус агента и статистику\n"
        "[cyan]history [количество][/cyan] - показать историю выполнения\n"
        "[cyan]config[/cyan] - показать текущую конфигурацию\n"
        "[cyan]cleanup [дни][/cyan] - очистить старые данные\n"
        "[cyan]help[/cyan] - показать эту справку\n"
        "[cyan]exit[/cyan] - выход из программы\n\n"
        "[bold]Примеры:[/bold]\n"
        "• execute Установить nginx на сервере\n"
        "• dry-run Настроить SSL сертификат\n"
        "• history 5\n"
        "• cleanup 3",
        title="[blue]Справка[/blue]",
        border_style="blue"
    ))


def _show_agent_status(agent: Optional[SSHAgent]):
    """Показать статус агента в интерактивном режиме."""
    if not agent:
        console.print("[yellow]Агент не инициализирован. Выполните команду для инициализации.[/yellow]")
        return
    
    try:
        status = agent.get_agent_status()
        
        console.print(Panel(
            f"[bold]Статистика агента:[/bold]\n"
            f"Задач выполнено: {status['agent_stats']['tasks_executed']}\n"
            f"Задач завершено: {status['agent_stats']['tasks_completed']}\n"
            f"Задач провалено: {status['agent_stats']['tasks_failed']}\n"
            f"Общее время выполнения: {status['agent_stats']['total_execution_time']:.2f}с\n"
            f"Эскалаций: {status['agent_stats']['escalations']}",
            title="[green]Статус агента[/green]",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Ошибка получения статуса:[/red] {e}")


def _show_execution_history(agent: Optional[SSHAgent], command: str):
    """Показать историю выполнения в интерактивном режиме."""
    if not agent:
        console.print("[yellow]Агент не инициализирован. Выполните команду для инициализации.[/yellow]")
        return
    
    try:
        # Парсим количество из команды
        parts = command.split()
        limit = 5
        if len(parts) > 1:
            try:
                limit = int(parts[1])
            except ValueError:
                pass
        
        history = agent.get_execution_history(limit)
        if history:
            history_text = "\n".join([
                f"{i+1}. [cyan]{h['task_title']}[/cyan]\n"
                f"   ID: {h['task_id']}\n"
                f"   Шагов: {h['completed_steps']}/{h['total_steps']} "
                f"{'[green]✓[/green]' if h['success'] else '[red]✗[/red]'}\n"
                f"   Ошибок: {h['error_count']}, Время: {h['duration']:.1f}с"
                for i, h in enumerate(history)
            ])
            
            console.print(Panel(
                f"Последние {len(history)} задач:\n\n{history_text}",
                title="[blue]История выполнения[/blue]",
                border_style="blue"
            ))
        else:
            console.print("[yellow]История выполнения пуста[/yellow]")
    except Exception as e:
        console.print(f"[red]Ошибка получения истории:[/red] {e}")


def _show_current_config():
    """Показать текущую конфигурацию в интерактивном режиме."""
    console.print(Panel(
        f"[bold]Текущая конфигурация:[/bold]\n"
        f"Server config: [cyan]{current_config['server_config_path']}[/cyan]\n"
        f"Agent config: [cyan]{current_config['agent_config_path']}[/cyan]",
        title="[blue]Конфигурация[/blue]",
        border_style="blue"
    ))


def _cleanup_old_data(agent: Optional[SSHAgent], command: str):
    """Очистить старые данные в интерактивном режиме."""
    if not agent:
        console.print("[yellow]Агент не инициализирован. Выполните команду для инициализации.[/yellow]")
        return
    
    try:
        # Парсим количество дней из команды
        parts = command.split()
        days = 7
        if len(parts) > 1:
            try:
                days = int(parts[1])
            except ValueError:
                pass
        
        if Confirm.ask(f"Удалить данные старше {days} дней?"):
            agent.cleanup_old_data(days)
            console.print("[green]✓ Очистка старых данных завершена[/green]")
        else:
            console.print("[yellow]Очистка отменена[/yellow]")
    except Exception as e:
        console.print(f"[red]Ошибка очистки данных:[/red] {e}")


def _execute_dry_run(agent: Optional[SSHAgent], command: str):
    """Выполнить dry-run в интерактивном режиме."""
    if not agent:
        agent = get_agent()
    
    # Извлекаем описание задачи из команды
    task_description = command.replace("dry-run", "").replace("просмотр", "").strip()
    if not task_description:
        console.print("[yellow]Укажите описание задачи для dry-run[/yellow]")
        return
    
    async def _run_dry_run():
        try:
            result = await agent.execute_task(task_description, dry_run=True)
            if result["success"]:
                console.print(f"[green]✓ Dry-run завершен успешно![/green]")
            else:
                console.print(f"[red]✗ Dry-run завершен с ошибками[/red]")
        except Exception as e:
            console.print(f"[red]Ошибка dry-run:[/red] {e}")
    
    asyncio.run(_run_dry_run())


def _execute_task_interactive(agent: Optional[SSHAgent], command: str):
    """Выполнить задачу в интерактивном режиме."""
    if not agent:
        agent = get_agent()
    
    # Извлекаем описание задачи из команды
    task_description = command.replace("execute", "").replace("выполнить", "").strip()
    if not task_description:
        console.print("[yellow]Укажите описание задачи для выполнения[/yellow]")
        return
    
    # Спрашиваем о dry-run
    dry_run = Confirm.ask("Выполнить в режиме dry-run?", default=True)
    
    async def _run_task():
        try:
            result = await agent.execute_task(task_description, dry_run=dry_run)
            if result["success"]:
                console.print(f"[green]✓ Задача выполнена успешно![/green]")
            else:
                console.print(f"[red]✗ Задача завершена с ошибками[/red]")
        except Exception as e:
            console.print(f"[red]Ошибка выполнения задачи:[/red] {e}")
    
    asyncio.run(_run_task())


def _display_detailed_results(step_results: List[Dict[str, Any]]):
    """Отображение подробных результатов выполнения."""
    console.print("\n[bold]Подробные результаты выполнения:[/bold]")
    
    for i, step_result in enumerate(step_results, 1):
        status = "[green]✓[/green]" if step_result["success"] else "[red]✗[/red]"
        console.print(f"\n{status} [bold]Шаг {i}:[/bold] {step_result.get('step_id', 'Unknown')}")
        console.print(f"   Длительность: {step_result.get('duration', 0):.2f}с")
        console.print(f"   Ошибок: {step_result.get('error_count', 0)}")
        
        if step_result.get("subtask_results"):
            for j, subtask in enumerate(step_result["subtask_results"], 1):
                subtask_status = "[green]✓[/green]" if subtask["success"] else "[red]✗[/red]"
                console.print(f"   {subtask_status} Подзадача {j}: {subtask.get('subtask_id', 'Unknown')}")


def _show_config_files(server_config: str, agent_config: str):
    """Показать содержимое файлов конфигурации."""
    try:
        # Server config
        if Path(server_config).exists():
            with open(server_config, 'r', encoding='utf-8') as f:
                server_content = f.read()
            console.print(Panel(
                Syntax(server_content, "yaml", theme="monokai", line_numbers=True),
                title=f"[cyan]Server Config: {server_config}[/cyan]",
                border_style="cyan"
            ))
        else:
            console.print(f"[red]Файл не найден:[/red] {server_config}")
        
        # Agent config
        if Path(agent_config).exists():
            with open(agent_config, 'r', encoding='utf-8') as f:
                agent_content = f.read()
            console.print(Panel(
                Syntax(agent_content, "yaml", theme="monokai", line_numbers=True),
                title=f"[cyan]Agent Config: {agent_config}[/cyan]",
                border_style="cyan"
            ))
        else:
            console.print(f"[red]Файл не найден:[/red] {agent_config}")
            
    except Exception as e:
        console.print(f"[red]Ошибка чтения конфигурации:[/red] {e}")


def _validate_config_files(server_config: str, agent_config: str):
    """Валидация файлов конфигурации."""
    try:
        # Валидация server config
        if Path(server_config).exists():
            server_cfg = ServerConfig.from_yaml(server_config)
            console.print(f"[green]✓ Server config валиден:[/green] {server_config}")
        else:
            console.print(f"[red]✗ Файл не найден:[/red] {server_config}")
        
        # Валидация agent config
        if Path(agent_config).exists():
            agent_cfg = AgentConfig.from_yaml(agent_config)
            console.print(f"[green]✓ Agent config валиден:[/green] {agent_config}")
        else:
            console.print(f"[red]✗ Файл не найден:[/red] {agent_config}")
            
        console.print(Panel(
            "[green]✓ Валидация конфигурации завершена[/green]",
            title="[green]Валидация[/green]",
            border_style="green"
        ))
        
    except Exception as e:
        console.print(Panel(
            f"[red]✗ Ошибка валидации:[/red] {str(e)}",
            title="[red]Ошибка валидации[/red]",
            border_style="red"
        ))


def _edit_config_files(server_config: str, agent_config: str):
    """Редактирование файлов конфигурации."""
    console.print("[yellow]Для редактирования конфигурации используйте ваш любимый редактор:[/yellow]")
    console.print(f"[cyan]Server config:[/cyan] {server_config}")
    console.print(f"[cyan]Agent config:[/cyan] {agent_config}")


def _create_default_server_config(path: Path):
    """Создание конфигурации сервера по умолчанию."""
    default_config = {
        "server": {
            "host": "localhost",
            "port": 22,
            "username": "user",
            "auth_method": "key",
            "key_path": "~/.ssh/id_rsa",
            "timeout": 30,
            "os_type": "ubuntu",
            "forbidden_commands": [
                "rm -rf /",
                "dd if=/dev/zero",
                "mkfs",
                "fdisk",
                "parted"
            ],
            "installed_services": [
                "docker",
                "nginx",
                "postgresql"
            ]
        }
    }
    
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)


def _create_default_agent_config(path: Path):
    """Создание конфигурации агента по умолчанию."""
    default_config = {
        "agents": {
            "taskmaster": {
                "enabled": True,
                "model": "gpt-4",
                "temperature": 0.7
            },
            "task_agent": {
                "model": "gpt-4",
                "temperature": 0.3,
                "max_steps": 10
            },
            "subtask_agent": {
                "model": "gpt-4",
                "temperature": 0.1,
                "max_subtasks": 20
            },
            "executor": {
                "max_retries_per_command": 2,
                "auto_correction_enabled": True,
                "dry_run_mode": False
            },
            "error_handler": {
                "error_threshold_per_step": 4,
                "send_to_planner_after_threshold": True,
                "human_escalation_threshold": 3
            }
        },
        "llm": {
            "api_key": "your-api-key-here",
            "base_url": "https://api.openai.com/v1",
            "max_tokens": 4000,
            "timeout": 60
        },
        "logging": {
            "level": "INFO",
            "file": "logs/ssh_agent.log"
        }
    }
    
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)


def main():
    """Главная точка входа для CLI."""
    app()


if __name__ == "__main__":
    main()
