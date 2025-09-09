"""
Тесты для CLI интерфейса SSH Agent.
"""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli import app, get_agent, current_config


class TestCLI:
    """Тесты для CLI интерфейса."""
    
    def test_cli_app_creation(self):
        """Тест создания CLI приложения."""
        assert app is not None
        assert app.info.name == "ssh-agent"
    
    def test_current_config_defaults(self):
        """Тест значений конфигурации по умолчанию."""
        assert current_config["server_config_path"] == "config/server_config.yaml"
        assert current_config["agent_config_path"] == "config/agent_config.yaml"
    
    @patch('cli.SSHAgent')
    def test_get_agent_creation(self, mock_ssh_agent):
        """Тест создания агента."""
        mock_instance = MagicMock()
        mock_ssh_agent.return_value = mock_instance
        
        agent = get_agent()
        
        assert agent == mock_instance
        mock_ssh_agent.assert_called_once_with(
            server_config_path="config/server_config.yaml",
            agent_config_path="config/agent_config.yaml"
        )
    
    @patch('cli.SSHAgent')
    def test_get_agent_exception_handling(self, mock_ssh_agent):
        """Тест обработки исключений при создании агента."""
        mock_ssh_agent.side_effect = Exception("Test error")
        
        with pytest.raises(SystemExit) as exc_info:
            get_agent()
        
        assert exc_info.value.code == 1
    
    def test_cli_help_command(self):
        """Тест команды помощи."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "SSH Agent с LLM интеграцией" in result.stdout
    
    def test_cli_init_command(self):
        """Тест команды инициализации."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "init", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Инициализировать файлы конфигурации" in result.stdout
    
    def test_cli_execute_command_help(self):
        """Тест справки команды execute."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "execute", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Выполнить задачу на удаленном сервере" in result.stdout
    
    def test_cli_status_command_help(self):
        """Тест справки команды status."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "status", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Показать статус агента и статистику" in result.stdout
    
    def test_cli_history_command_help(self):
        """Тест справки команды history."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "history", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Показать историю выполнения задач" in result.stdout
    
    def test_cli_cleanup_command_help(self):
        """Тест справки команды cleanup."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "cleanup", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Очистить старые данные" in result.stdout
    
    def test_cli_config_command_help(self):
        """Тест справки команды config."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "config", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Управление конфигурацией" in result.stdout
    
    def test_cli_interactive_command_help(self):
        """Тест справки команды interactive."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "interactive", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "Запустить интерактивный режим" in result.stdout


class TestCLIHelpers:
    """Тесты для вспомогательных функций CLI."""
    
    def test_create_default_server_config(self):
        """Тест создания конфигурации сервера по умолчанию."""
        from cli import _create_default_server_config
        import tempfile
        import yaml
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            _create_default_server_config(temp_path)
            
            assert temp_path.exists()
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            assert 'server' in config
            assert config['server']['host'] == 'localhost'
            assert config['server']['port'] == 22
            assert config['server']['username'] == 'user'
            assert config['server']['auth_method'] == 'key'
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_create_default_agent_config(self):
        """Тест создания конфигурации агента по умолчанию."""
        from cli import _create_default_agent_config
        import tempfile
        import yaml
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            _create_default_agent_config(temp_path)
            
            assert temp_path.exists()
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            assert 'agents' in config
            assert 'llm' in config
            assert 'logging' in config
            
            assert config['agents']['taskmaster']['enabled'] is True
            assert config['llm']['api_key'] == 'your-api-key-here'
            assert config['logging']['level'] == 'INFO'
            
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__])
