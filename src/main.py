"""
Main entry point for SSH Agent with LLM integration.

This module provides the main SSHAgent class and CLI interface.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config.server_config import ServerConfig
from .config.agent_config import AgentConfig
from .connectors.ssh_connector import SSHConnector
from .agents.task_master_integration import TaskMasterIntegration
from .agents.task_agent import TaskAgent
from .agents.subtask_agent import SubtaskAgent
from .agents.executor import Executor
from .agents.error_handler import ErrorHandler
from .utils.logger import LoggerSetup

console = Console()
app = typer.Typer(help="SSH Agent with LLM Integration")


class SSHAgent:
    """
    Main SSH Agent class that coordinates all components.
    """
    
    def __init__(
        self,
        server_config_path: Optional[str] = None,
        agent_config_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize SSH Agent.
        
        Args:
            server_config_path: Path to server configuration file
            agent_config_path: Path to agent configuration file
            config: Optional configuration dictionary
        """
        self.server_config = None
        self.agent_config = None
        self.ssh_connector = None
        self.task_master = None
        self.task_agent = None
        self.subtask_agent = None
        self.executor = None
        self.error_handler = None
        
        # Load configurations
        self._load_configurations(server_config_path, agent_config_path, config)
        
        # Initialize components
        self._initialize_components()
    
    def _load_configurations(
        self,
        server_config_path: Optional[str],
        agent_config_path: Optional[str],
        config: Optional[Dict[str, Any]]
    ):
        """Load configuration from files or dictionary."""
        if config:
            # Load from dictionary
            self.server_config = ServerConfig(**config.get('server', {}))
            self.agent_config = AgentConfig(**config.get('agents', {}))
        else:
            # Load from files
            if server_config_path:
                self.server_config = ServerConfig.from_file(server_config_path)
            else:
                self.server_config = ServerConfig()
            
            if agent_config_path:
                self.agent_config = AgentConfig.from_file(agent_config_path)
            else:
                self.agent_config = AgentConfig()
    
    def _initialize_components(self):
        """Initialize all agent components."""
        # Setup logging
        LoggerSetup.setup_logging(
            log_level=self.agent_config.logging.level,
            log_file=self.agent_config.logging.file
        )
        
        # Initialize SSH connector
        self.ssh_connector = SSHConnector(self.server_config)
        
        # Initialize Task Master integration
        if self.agent_config.taskmaster.enabled:
            self.task_master = TaskMasterIntegration(
                project_path=".",
                config=self.agent_config.taskmaster
            )
        
        # Initialize agents
        self.task_agent = TaskAgent(
            llm_client=None,  # Will be initialized later
            config=self.agent_config.task_agent
        )
        
        self.subtask_agent = SubtaskAgent(
            llm_client=None,  # Will be initialized later
            config=self.agent_config.subtask_agent
        )
        
        self.executor = Executor(
            ssh_connector=self.ssh_connector,
            config=self.agent_config.executor
        )
        
        self.error_handler = ErrorHandler(
            config=self.agent_config.error_handler
        )
    
    async def execute_task(self, task_description: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute a task on the remote server.
        
        Args:
            task_description: Description of the task to execute
            dry_run: If True, only show what would be executed
            
        Returns:
            Dictionary with execution results
        """
        try:
            console.print(f"[bold blue]Executing task:[/bold blue] {task_description}")
            
            # Connect to server
            if not await self.ssh_connector.connect():
                return {"success": False, "error": "Failed to connect to server"}
            
            # Use Task Master to improve the prompt if enabled
            if self.task_master:
                improved_prompt = await self.task_master.improve_prompt(
                    task_description, 
                    {"server": self.server_config.dict()}
                )
                console.print(f"[green]Improved prompt:[/green] {improved_prompt}")
            
            # Plan the task
            steps = await self.task_agent.plan_task(task_description, self.server_config)
            console.print(f"[green]Planned {len(steps)} steps[/green]")
            
            # Execute each step
            results = []
            for step in steps:
                console.print(f"[yellow]Executing step:[/yellow] {step.description}")
                
                # Plan subtasks for this step
                subtasks = await self.subtask_agent.plan_subtasks(step, self.server_config)
                
                # Execute subtasks
                step_result = await self.executor.execute_step(step, subtasks, dry_run)
                results.append(step_result)
                
                # Handle errors if any
                if step_result.get('error_count', 0) > 0:
                    await self.error_handler.handle_step_errors(
                        step.step_id,
                        step_result['error_count'],
                        step_result.get('logs', [])
                    )
            
            return {
                "success": True,
                "steps_completed": len(results),
                "results": results
            }
            
        except Exception as e:
            console.print(f"[red]Error executing task:[/red] {e}")
            return {"success": False, "error": str(e)}
        
        finally:
            # Disconnect from server
            if self.ssh_connector:
                await self.ssh_connector.disconnect()


@app.command()
def execute(
    task: str = typer.Argument(..., help="Task description to execute"),
    server_config: str = typer.Option("config/server_config.yaml", help="Server configuration file"),
    agent_config: str = typer.Option("config/agent_config.yaml", help="Agent configuration file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be executed without doing it")
):
    """Execute a task on the remote server."""
    async def _execute():
        agent = SSHAgent(server_config, agent_config)
        result = await agent.execute_task(task, dry_run)
        
        if result["success"]:
            console.print(Panel(
                f"Task completed successfully!\nSteps completed: {result['steps_completed']}",
                title="Success",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"Task failed: {result.get('error', 'Unknown error')}",
                title="Error",
                border_style="red"
            ))
    
    asyncio.run(_execute())


@app.command()
def interactive():
    """Start interactive mode."""
    console.print(Panel(
        "SSH Agent Interactive Mode\nType 'exit' to quit",
        title="SSH Agent",
        border_style="blue"
    ))
    
    while True:
        try:
            task = typer.prompt("Enter task description")
            if task.lower() in ['exit', 'quit']:
                break
            
            # Execute task
            asyncio.run(SSHAgent().execute_task(task))
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
    
    console.print("[green]Goodbye![/green]")


@app.command()
def init():
    """Initialize SSH Agent configuration files."""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Copy example files if they don't exist
    server_config = config_dir / "server_config.yaml"
    agent_config = config_dir / "agent_config.yaml"
    
    if not server_config.exists():
        server_config.write_text(
            Path("config/server_config.yaml.example").read_text()
        )
        console.print(f"[green]Created[/green] {server_config}")
    
    if not agent_config.exists():
        agent_config.write_text(
            Path("config/agent_config.yaml.example").read_text()
        )
        console.print(f"[green]Created[/green] {agent_config}")
    
    console.print(Panel(
        "Configuration files created successfully!\n"
        "Please edit config/server_config.yaml and config/agent_config.yaml\n"
        "with your actual server details and API keys.",
        title="Initialization Complete",
        border_style="green"
    ))


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
