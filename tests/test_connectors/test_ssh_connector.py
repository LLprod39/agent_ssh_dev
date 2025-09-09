"""
Тесты для SSH Connector
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import tempfile
import os

from src.connectors.ssh_connector import SSHConnector, SSHConnectionError, SSHCommandError, CommandResult
from src.config.server_config import ServerConfig
from src.utils.credentials_manager import CredentialsManager, KeyringCredentialsManager, SSHKeyManager


class TestSSHConnector:
    """Тесты для SSH Connector"""
    
    @pytest.fixture
    def server_config(self):
        """Фикстура конфигурации сервера"""
        return ServerConfig(
            host="test.example.com",
            port=22,
            username="testuser",
            auth_method="key",
            key_path="/path/to/key",
            timeout=30,
            os_type="ubuntu"
        )
    
    @pytest.fixture
    def ssh_connector(self, server_config):
        """Фикстура SSH Connector"""
        return SSHConnector(server_config, use_credentials_manager=False)
    
    @pytest.fixture
    def mock_ssh_client(self):
        """Фикстура мока SSH клиента"""
        mock_client = Mock()
        mock_client.connect = Mock()
        mock_client.close = Mock()
        mock_client.exec_command = Mock()
        mock_client.open_sftp = Mock()
        return mock_client
    
    def test_ssh_connector_initialization(self, server_config):
        """Тест инициализации SSH Connector"""
        connector = SSHConnector(server_config)
        
        assert connector.config == server_config
        assert connector.connected is False
        assert connector.client is None
        assert connector.sftp is None
        assert connector.stats['connection_attempts'] == 0
    
    def test_ssh_connector_with_credentials_manager(self, server_config):
        """Тест инициализации с менеджером учетных данных"""
        connector = SSHConnector(server_config, use_credentials_manager=True)
        
        assert connector.use_credentials_manager is True
        assert isinstance(connector.credentials_manager, CredentialsManager)
        assert isinstance(connector.keyring_manager, KeyringCredentialsManager)
        assert isinstance(connector.key_manager, SSHKeyManager)
    
    @pytest.mark.asyncio
    async def test_connect_success(self, ssh_connector, mock_ssh_client):
        """Тест успешного подключения"""
        with patch('paramiko.SSHClient', return_value=mock_ssh_client):
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock()
                
                result = await ssh_connector.connect()
                
                assert result is True
                assert ssh_connector.connected is True
                assert ssh_connector.client == mock_ssh_client
                assert ssh_connector.stats['successful_connections'] == 1
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, ssh_connector):
        """Тест неудачного подключения"""
        with patch('paramiko.SSHClient') as mock_ssh_class:
            mock_client = Mock()
            mock_client.connect.side_effect = Exception("Connection failed")
            mock_ssh_class.return_value = mock_client
            
            with pytest.raises(SSHConnectionError):
                await ssh_connector.connect()
            
            assert ssh_connector.connected is False
            assert ssh_connector.stats['failed_connections'] == 1
    
    @pytest.mark.asyncio
    async def test_disconnect(self, ssh_connector, mock_ssh_client):
        """Тест отключения"""
        ssh_connector.client = mock_ssh_client
        ssh_connector.sftp = Mock()
        ssh_connector.connected = True
        ssh_connector.connection_time = Mock()
        
        await ssh_connector.disconnect()
        
        assert ssh_connector.connected is False
        assert ssh_connector.client is None
        assert ssh_connector.sftp is None
        mock_ssh_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, ssh_connector, mock_ssh_client):
        """Тест успешного выполнения команды"""
        # Настройка мока
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"success output"
        mock_stderr.read.return_value = b""
        
        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        ssh_connector.client = mock_ssh_client
        ssh_connector.connected = True
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=CommandResult(
                command="test command",
                exit_code=0,
                stdout="success output",
                stderr=""
            ))
            
            result = await ssh_connector.execute_command("test command")
            
            assert result.success is True
            assert result.exit_code == 0
            assert result.stdout == "success output"
            assert ssh_connector.stats['commands_executed'] == 1
    
    @pytest.mark.asyncio
    async def test_execute_command_failure(self, ssh_connector, mock_ssh_client):
        """Тест неудачного выполнения команды"""
        ssh_connector.client = mock_ssh_client
        ssh_connector.connected = True
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=CommandResult(
                command="test command",
                exit_code=1,
                stdout="",
                stderr="command failed"
            ))
            
            result = await ssh_connector.execute_command("test command")
            
            assert result.success is False
            assert result.exit_code == 1
            assert result.stderr == "command failed"
            assert ssh_connector.stats['commands_failed'] == 1
    
    @pytest.mark.asyncio
    async def test_execute_command_not_connected(self, ssh_connector):
        """Тест выполнения команды без подключения"""
        ssh_connector.connected = False
        
        with pytest.raises(SSHConnectionError):
            await ssh_connector.execute_command("test command")
    
    def test_execute_forbidden_command(self, ssh_connector):
        """Тест выполнения запрещенной команды"""
        ssh_connector.connected = True
        
        with pytest.raises(SSHCommandError):
            ssh_connector.execute_command("rm -rf /", check_forbidden=True)
    
    @pytest.mark.asyncio
    async def test_execute_commands_batch(self, ssh_connector, mock_ssh_client):
        """Тест выполнения нескольких команд"""
        ssh_connector.client = mock_ssh_client
        ssh_connector.connected = True
        
        with patch.object(ssh_connector, 'execute_command') as mock_execute:
            mock_execute.side_effect = [
                CommandResult("cmd1", 0, "output1", ""),
                CommandResult("cmd2", 1, "", "error2"),
                CommandResult("cmd3", 0, "output3", "")
            ]
            
            results = await ssh_connector.execute_commands_batch(["cmd1", "cmd2", "cmd3"])
            
            assert len(results) == 3
            assert results[0].success is True
            assert results[1].success is False
            assert results[2].success is True
    
    @pytest.mark.asyncio
    async def test_upload_file(self, ssh_connector, mock_ssh_client):
        """Тест загрузки файла"""
        ssh_connector.sftp = Mock()
        ssh_connector.connected = True
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file.flush()
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock()
                
                result = await ssh_connector.upload_file(temp_file.name, "/remote/path")
                
                assert result is True
                ssh_connector.sftp.put.assert_called_once()
            
            os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_download_file(self, ssh_connector, mock_ssh_client):
        """Тест скачивания файла"""
        ssh_connector.sftp = Mock()
        ssh_connector.connected = True
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock()
            
            result = await ssh_connector.download_file("/remote/path", "/local/path")
            
            assert result is True
            ssh_connector.sftp.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_connection(self, ssh_connector, mock_ssh_client):
        """Тест проверки соединения"""
        ssh_connector.client = mock_ssh_client
        ssh_connector.connected = True
        
        with patch.object(ssh_connector, 'execute_command') as mock_execute:
            mock_execute.return_value = CommandResult("echo", 0, "connection_test", "")
            
            result = await ssh_connector.check_connection()
            
            assert result is True
            mock_execute.assert_called_once_with("echo 'connection_test'", timeout=5)
    
    def test_get_stats(self, ssh_connector):
        """Тест получения статистики"""
        ssh_connector.connected = True
        ssh_connector.connection_time = Mock()
        ssh_connector.last_activity = Mock()
        
        stats = ssh_connector.get_stats()
        
        assert 'connected' in stats
        assert 'connection_attempts' in stats
        assert 'host' in stats
        assert 'username' in stats
    
    @pytest.mark.asyncio
    async def test_connection_context_manager(self, ssh_connector):
        """Тест контекстного менеджера"""
        with patch.object(ssh_connector, 'connect') as mock_connect:
            with patch.object(ssh_connector, 'disconnect') as mock_disconnect:
                mock_connect.return_value = True
                
                async with ssh_connector.connection_context() as conn:
                    assert conn == ssh_connector
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()
    
    def test_resolve_key_path_from_config(self, server_config):
        """Тест определения пути к ключу из конфигурации"""
        connector = SSHConnector(server_config, use_credentials_manager=False)
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch.object(connector.key_manager, 'validate_key', return_value=True):
                key_path = connector._resolve_key_path()
                assert key_path is not None
    
    def test_resolve_password_from_config(self, server_config):
        """Тест определения пароля из конфигурации"""
        server_config.auth_method = "password"
        server_config.password = "test_password"
        
        connector = SSHConnector(server_config, use_credentials_manager=False)
        
        password = connector._resolve_password()
        assert password == "test_password"
    
    def test_store_credentials_password(self, server_config):
        """Тест сохранения пароля"""
        server_config.auth_method = "password"
        connector = SSHConnector(server_config, use_credentials_manager=True)
        
        with patch.object(connector.keyring_manager, 'store_credentials', return_value=True):
            result = connector.store_credentials(password="test_password")
            assert result is True
    
    def test_store_credentials_key(self, server_config):
        """Тест сохранения пути к ключу"""
        connector = SSHConnector(server_config, use_credentials_manager=True)
        
        with patch.object(connector.credentials_manager, 'store_credentials', return_value=True):
            result = connector.store_credentials(key_path="/path/to/key")
            assert result is True


class TestCommandResult:
    """Тесты для CommandResult"""
    
    def test_command_result_success(self):
        """Тест успешного результата команды"""
        result = CommandResult("test command", 0, "output", "")
        
        assert result.success is True
        assert result.failed is False
        assert result.exit_code == 0
    
    def test_command_result_failure(self):
        """Тест неудачного результата команды"""
        result = CommandResult("test command", 1, "", "error")
        
        assert result.success is False
        assert result.failed is True
        assert result.exit_code == 1
    
    def test_command_result_to_dict(self):
        """Тест преобразования в словарь"""
        result = CommandResult("test command", 0, "output", "")
        result_dict = result.to_dict()
        
        assert result_dict['command'] == "test command"
        assert result_dict['exit_code'] == 0
        assert result_dict['success'] is True
        assert 'timestamp' in result_dict
    
    def test_command_result_str(self):
        """Тест строкового представления"""
        result = CommandResult("test command", 0, "output", "")
        result_str = str(result)
        
        assert "test command" in result_str
        assert "SUCCESS" in result_str
        assert "0" in result_str


class TestSSHConnectorIntegration:
    """Интеграционные тесты для SSH Connector"""
    
    @pytest.mark.asyncio
    async def test_full_connection_workflow(self):
        """Тест полного рабочего процесса подключения"""
        config = ServerConfig(
            host="localhost",
            port=22,
            username="test",
            auth_method="password",
            password="test"
        )
        
        connector = SSHConnector(config, use_credentials_manager=False)
        
        # Мокаем все SSH операции
        with patch('paramiko.SSHClient') as mock_ssh_class:
            mock_client = Mock()
            mock_stdin = Mock()
            mock_stdout = Mock()
            mock_stderr = Mock()
            mock_channel = Mock()
            
            mock_stdout.channel = mock_channel
            mock_channel.recv_exit_status.return_value = 0
            mock_stdout.read.return_value = b"test output"
            mock_stderr.read.return_value = b""
            
            mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
            mock_ssh_class.return_value = mock_client
            
            # Тестируем полный цикл
            await connector.connect()
            assert connector.connected is True
            
            result = await connector.execute_command("echo test")
            assert result.success is True
            
            await connector.disconnect()
            assert connector.connected is False
