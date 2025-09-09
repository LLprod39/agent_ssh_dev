"""
Main entry point for SSH Agent with LLM integration.

This module provides the CLI interface and main entry point.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .config.server_config import ServerConfig
from .config.agent_config import AgentConfig
from .agents.ssh_agent import SSHAgent
from .utils.logger import LoggerSetup

console = Console()
app = typer.Typer(help="SSH Agent with LLM Integration")


@app.command()
def execute(
    task: str = typer.Argument(..., help="Task description to execute"),
    server_config: str = typer.Option("config/server_config.yaml", help="Server configuration file"),
    agent_config: str = typer.Option("config/agent_config.yaml", help="Agent configuration file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be executed without doing it")
):
    """Execute a task on the remote server."""
    async def _execute():
        try:
            # Load configurations
            server_cfg = ServerConfig.from_file(server_config)
            agent_cfg = AgentConfig.from_yaml(agent_config)
            
            # Setup logging
            LoggerSetup.setup_logging(
                log_level=agent_cfg.logging.level,
                log_file=agent_cfg.logging.file
            )
            
            # Create and initialize SSH Agent
            agent = SSHAgent(server_cfg, agent_cfg)
            
            # Setup progress callbacks
            def progress_callback(data):
                phase = data.get("phase", "unknown")
                message = data.get("message", "")
                if phase == "planning":
                    console.print(f"[blue]📋 Planning:[/blue] {message}")
                elif phase == "execution":
                    console.print(f"[yellow]⚡ Executing:[/blue] {message}")
                elif phase == "step_execution":
                    step_index = data.get("step_index", 0)
                    step_title = data.get("step_title", "")
                    console.print(f"[cyan]Step {step_index}:[/cyan] {step_title}")
            
            def error_callback(data):
                error_type = data.get("type", "unknown")
                error_msg = data.get("error", "")
                console.print(f"[red]❌ Error ({error_type}):[/red] {error_msg}")
            
            def completion_callback(result):
                if result.success:
                    console.print(Panel(
                        f"✅ Task completed successfully!\n"
                        f"📊 Steps completed: {result.steps_completed}\n"
                        f"⏱️  Duration: {result.total_duration:.2f}s\n"
                        f"🔧 Errors: {result.error_count}",
                        title="Success",
                        border_style="green"
                    ))
                else:
                    console.print(Panel(
                        f"❌ Task failed!\n"
                        f"📊 Steps completed: {result.steps_completed}\n"
                        f"📊 Steps failed: {result.steps_failed}\n"
                        f"⏱️  Duration: {result.total_duration:.2f}s\n"
                        f"🔧 Errors: {result.error_count}",
                        title="Failed",
                        border_style="red"
                    ))
            
            # Register callbacks
            agent.register_progress_callback(progress_callback)
            agent.register_error_callback(error_callback)
            agent.register_completion_callback(completion_callback)
            
            # Initialize agent
            console.print("[blue]🚀 Initializing SSH Agent...[/blue]")
            if not await agent.initialize():
                console.print("[red]❌ Failed to initialize SSH Agent[/red]")
                return
            
            console.print("[green]✅ SSH Agent initialized successfully[/green]")
            
            # Execute task
            console.print(f"[bold blue]🎯 Executing task:[/bold blue] {task}")
            if dry_run:
                console.print("[yellow]🔍 Running in dry-run mode (simulation only)[/yellow]")
            
            result = await agent.execute_task(task, dry_run)
            
            # Show final status
            if result.success:
                console.print(Panel(
                    f"✅ Task completed successfully!\n"
                    f"📊 Steps completed: {result.steps_completed}\n"
                    f"⏱️  Duration: {result.total_duration:.2f}s\n"
                    f"🔧 Errors: {result.error_count}",
                    title="Success",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    f"❌ Task failed!\n"
                    f"📊 Steps completed: {result.steps_completed}\n"
                    f"📊 Steps failed: {result.steps_failed}\n"
                    f"⏱️  Duration: {result.total_duration:.2f}s\n"
                    f"🔧 Errors: {result.error_count}",
                    title="Failed",
                    border_style="red"
                ))
            
            # Cleanup
            await agent.cleanup()
            
        except Exception as e:
            console.print(Panel(
                f"❌ Unexpected error: {str(e)}",
                title="Error",
                border_style="red"
            ))
            console.print_exception()
    
    asyncio.run(_execute())


@app.command()
def interactive(
    server_config: str = typer.Option("config/server_config.yaml", help="Server configuration file"),
    agent_config: str = typer.Option("config/agent_config.yaml", help="Agent configuration file")
):
    """Start interactive mode."""
    async def _interactive():
        try:
            # Load configurations
            server_cfg = ServerConfig.from_file(server_config)
            agent_cfg = AgentConfig.from_yaml(agent_config)
            
            # Setup logging
            LoggerSetup.setup_logging(
                log_level=agent_cfg.logging.level,
                log_file=agent_cfg.logging.file
            )
            
            # Create and initialize SSH Agent
            agent = SSHAgent(server_cfg, agent_cfg)
            
            console.print(Panel(
                "🚀 SSH Agent Interactive Mode\n"
                "Type 'exit' or 'quit' to quit\n"
                "Type 'status' to see agent status\n"
                "Type 'history' to see execution history",
                title="SSH Agent",
                border_style="blue"
            ))
            
            # Initialize agent
            console.print("[blue]🚀 Initializing SSH Agent...[/blue]")
            if not await agent.initialize():
                console.print("[red]❌ Failed to initialize SSH Agent[/red]")
                return
            
            console.print("[green]✅ SSH Agent initialized successfully[/green]")
            
            while True:
                try:
                    task = typer.prompt("Enter task description")
                    
                    if task.lower() in ['exit', 'quit']:
                        break
                    elif task.lower() == 'status':
                        status = agent.get_status()
                        console.print(Panel(
                            f"State: {status['state']}\n"
                            f"Current Task: {status['current_task'] or 'None'}\n"
                            f"Components: {len(status['agent_statuses'])}\n"
                            f"Tasks Executed: {status['stats']['tasks_executed']}",
                            title="Agent Status",
                            border_style="green"
                        ))
                        continue
                    elif task.lower() == 'history':
                        history = agent.get_execution_history(5)
                        if history:
                            console.print(Panel(
                                "\n".join([
                                    f"Task {i+1}: {h['task_id']} - {'✅' if h['success'] else '❌'} "
                                    f"({h['total_duration']:.2f}s)"
                                    for i, h in enumerate(history)
                                ]),
                                title="Recent Execution History",
                                border_style="cyan"
                            ))
                        else:
                            console.print("[yellow]No execution history available[/yellow]")
                        continue
                    elif task.lower().startswith('dry-run '):
                        task_description = task[8:]  # Remove 'dry-run ' prefix
                        console.print("[yellow]🔍 Running in dry-run mode[/yellow]")
                        result = await agent.execute_task(task_description, dry_run=True)
                    else:
                        result = await agent.execute_task(task)
                    
                    # Show result
                    if result.success:
                        console.print(f"[green]✅ Task completed in {result.total_duration:.2f}s[/green]")
                    else:
                        console.print(f"[red]❌ Task failed after {result.total_duration:.2f}s[/red]")
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"[red]Error:[/red] {e}")
            
            # Cleanup
            await agent.cleanup()
            console.print("[green]👋 Goodbye![/green]")
            
        except Exception as e:
            console.print(Panel(
                f"❌ Unexpected error: {str(e)}",
                title="Error",
                border_style="red"
            ))
            console.print_exception()
    
    asyncio.run(_interactive())


@app.command()
def init():
    """Initialize SSH Agent configuration files."""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Copy example files if they don't exist
    server_config = config_dir / "server_config.yaml"
    agent_config = config_dir / "agent_config.yaml"
    
    if not server_config.exists():
        if Path("config/server_config.yaml.example").exists():
            server_config.write_text(
                Path("config/server_config.yaml.example").read_text()
            )
            console.print(f"[green]✅ Created[/green] {server_config}")
        else:
            # Create default server config
            default_server_config = """server:
  host: "example.com"
  port: 22
  username: "user"
  auth_method: "key"  # key, password
  key_path: "/path/to/private/key"
  timeout: 30
  os_type: "ubuntu"  # ubuntu, centos, debian
  forbidden_commands:
    - "rm -rf /"
    - "dd if=/dev/zero"
    - "mkfs"
  installed_services:
    - "docker"
    - "nginx"
    - "postgresql"
"""
            server_config.write_text(default_server_config)
            console.print(f"[green]✅ Created[/green] {server_config}")
    
    if not agent_config.exists():
        if Path("config/agent_config.yaml.example").exists():
            agent_config.write_text(
                Path("config/agent_config.yaml.example").read_text()
            )
            console.print(f"[green]✅ Created[/green] {agent_config}")
        else:
            # Create default agent config
            default_agent_config = """agents:
  taskmaster:
    enabled: true
    model: "gpt-4"
    temperature: 0.7
  
  task_agent:
    model: "gpt-4"
    temperature: 0.3
    max_steps: 10
  
  subtask_agent:
    model: "gpt-4"
    temperature: 0.1
    max_subtasks: 20
  
  executor:
    max_retries_per_command: 2
    auto_correction_enabled: true
    dry_run_mode: false
  
  error_handler:
    error_threshold_per_step: 4
    send_to_planner_after_threshold: true
    human_escalation_threshold: 3

llm:
  api_key: "your-api-key"
  base_url: "https://api.openai.com/v1"
  max_tokens: 4000
  timeout: 60
"""
            agent_config.write_text(default_agent_config)
            console.print(f"[green]✅ Created[/green] {agent_config}")
    
    console.print(Panel(
        "🎉 Configuration files created successfully!\n\n"
        "📝 Please edit the following files:\n"
        "   • config/server_config.yaml - Server connection details\n"
        "   • config/agent_config.yaml - Agent settings and API keys\n\n"
        "🔧 Make sure to:\n"
        "   • Set your actual server host, username, and authentication\n"
        "   • Configure your LLM API key\n"
        "   • Adjust agent parameters as needed",
        title="Initialization Complete",
        border_style="green"
    ))


@app.command()
def status(
    server_config: str = typer.Option("config/server_config.yaml", help="Server configuration file"),
    agent_config: str = typer.Option("config/agent_config.yaml", help="Agent configuration file")
):
    """Show SSH Agent status and statistics."""
    async def _status():
        try:
            # Load configurations
            server_cfg = ServerConfig.from_file(server_config)
            agent_cfg = AgentConfig.from_yaml(agent_config)
            
            # Setup logging
            LoggerSetup.setup_logging(
                log_level=agent_cfg.logging.level,
                log_file=agent_cfg.logging.file
            )
            
            # Create and initialize SSH Agent
            agent = SSHAgent(server_cfg, agent_cfg)
            
            console.print("[blue]🚀 Initializing SSH Agent...[/blue]")
            if not await agent.initialize():
                console.print("[red]❌ Failed to initialize SSH Agent[/red]")
                return
            
            # Get status
            status = agent.get_status()
            agent_stats = agent.get_agent_stats()
            
            # Display status
            console.print(Panel(
                f"State: {status['state']}\n"
                f"Current Task: {status['current_task'] or 'None'}\n"
                f"Current Execution: {status['current_execution'] or 'None'}\n"
                f"Components: {len(status['agent_statuses'])}",
                title="SSH Agent Status",
                border_style="blue"
            ))
            
            # Display component statuses
            console.print("\n[bold]Component Statuses:[/bold]")
            for name, comp_status in status['agent_statuses'].items():
                state_emoji = "✅" if comp_status['state'] == "ready" else "❌"
                console.print(f"  {state_emoji} {name}: {comp_status['state']}")
            
            # Display statistics
            console.print(Panel(
                f"Tasks Executed: {status['stats']['tasks_executed']}\n"
                f"Tasks Successful: {status['stats']['tasks_successful']}\n"
                f"Tasks Failed: {status['stats']['tasks_failed']}\n"
                f"Total Execution Time: {status['stats']['total_execution_time']:.2f}s\n"
                f"Total Errors: {status['stats']['total_errors']}\n"
                f"Agent Initializations: {status['stats']['agent_initializations']}\n"
                f"Agent Errors: {status['stats']['agent_errors']}",
                title="Statistics",
                border_style="green"
            ))
            
            # Display execution history
            history = agent.get_execution_history(5)
            if history:
                console.print("\n[bold]Recent Execution History:[/bold]")
                for i, h in enumerate(history, 1):
                    status_emoji = "✅" if h['success'] else "❌"
                    console.print(f"  {i}. {status_emoji} {h['task_id']} - {h['total_duration']:.2f}s")
            
            # Cleanup
            await agent.cleanup()
            
        except Exception as e:
            console.print(Panel(
                f"❌ Unexpected error: {str(e)}",
                title="Error",
                border_style="red"
            ))
            console.print_exception()
    
    asyncio.run(_status())


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
